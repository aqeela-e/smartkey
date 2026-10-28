import pandas as pd
import streamlit as st

from config import (
    AI_LABELS,
    CRYPTO_ALGORITHMS,
    DETECTOR_SAMPLES_SPEC,
    EXPERIMENT_SOURCES,
    EXPERIMENT_TRIALS_SPEC,
    MAX_FILES_PER_FORMAT,
    RESULTS_DIR,
    SYNTHETIC_PER_FORMAT_SPEC,
    TEXTS,
    UPLOAD_TYPES,
)
from modules.evaluation.confusion import confusion_metrics, randomness_detector_confusion
from modules.evaluation.document_test import (
    TAMPER_MODES,
    load_folder,
    synthetic_documents,
)
from modules.experiment.runner import build_ai_kwargs, run_experiment
from modules.experiment.storage import save_result
from ui.charts import confusion_heatmap, convergence_plot, grouped_bars, ring_chart, show

METRIC_COLUMNS = ("accuracy", "precision", "recall", "specificity", "f1")


def _gather_documents(source: str, limit: int):
    if source == EXPERIMENT_SOURCES[0]:
        files = st.file_uploader(
            TEXTS["experiment_upload"],
            type=UPLOAD_TYPES,
            accept_multiple_files=True,
            key="experiment_upload",
        )
        return lambda: [(f.name, f.getvalue()) for f in (files or [])]
    if source == EXPERIMENT_SOURCES[1]:
        path = st.text_input(TEXTS["experiment_folder"], key="experiment_folder")
        return lambda: load_folder(path, limit) if path else []
    low, high, default, step = SYNTHETIC_PER_FORMAT_SPEC
    count = st.number_input(
        TEXTS["experiment_synthetic"], min_value=low, max_value=high, value=default, step=step,
        key="experiment_synthetic",
    )
    return lambda: synthetic_documents(int(count))


def _render_experiment(result: dict) -> None:
    summary = result["summary"]
    docs = result["documents"]
    quality = result["seed_quality"]
    labels = [TEXTS["label_valid"], TEXTS["label_invalid"]]

    row = st.columns(4)
    row[0].metric(TEXTS["experiment_docs"], docs["total"])
    row[1].metric(TEXTS["experiment_trials"], result["config"]["n_trials"])
    row[2].metric("Akurasi verifikasi", "%.2f%%" % (result["verification_metrics"]["accuracy"] * 100))
    row[3].metric("Seed lolos semua tes", "%d/%d" % (quality["pass_all"], quality["n"]))

    st.markdown("**%s**" % TEXTS["experiment_confusion"])
    columns = st.columns(len(summary))
    for column, (algorithm, data) in zip(columns, summary.items()):
        with column:
            show(confusion_heatmap(data["confusion"], "%s %d" % (algorithm, data["key_size"]), labels, labels))

    metric_rows = []
    for algorithm, data in summary.items():
        row_data = {"Algoritma": algorithm}
        row_data.update({m: "%.4f" % data["metrics"][m] for m in METRIC_COLUMNS})
        row_data.update({k: data["confusion"][k] for k in ("TP", "FN", "FP", "TN")})
        row_data["Signature (byte)"] = data["signature_bytes"]
        metric_rows.append(row_data)
    st.table(pd.DataFrame(metric_rows))

    st.markdown("**%s**" % TEXTS["experiment_timing"])
    timing = {
        algorithm: {
            "keygen": data["timing"]["keygen_ms_mean"],
            "sign": data["timing"]["sign_ms_mean"],
            "verify": data["timing"]["verify_ms_mean"],
        }
        for algorithm, data in summary.items()
    }
    left, right = st.columns(2)
    with left:
        show(grouped_bars(timing, TEXTS["experiment_timing"]))
    with right:
        st.table(
            pd.DataFrame(
                [
                    {
                        "Algoritma": a,
                        "keygen rata-rata (ms)": "%.2f" % d["timing"]["keygen_ms_mean"],
                        "sign median (ms)": "%.3f" % d["timing"]["sign_ms_median"],
                        "verify median (ms)": "%.3f" % d["timing"]["verify_ms_median"],
                    }
                    for a, d in summary.items()
                ]
            )
        )

    st.markdown("**%s**" % TEXTS["experiment_format"])
    format_rows = []
    for algorithm, data in summary.items():
        for label, item in data["by_format"].items():
            format_rows.append(
                {
                    "Algoritma": algorithm,
                    "Format": label,
                    "Dokumen": docs["per_format"][label],
                    "Akurasi": "%.4f" % item["metrics"]["accuracy"],
                    "FP": item["confusion"]["FP"],
                    "FN": item["confusion"]["FN"],
                }
            )
    st.table(pd.DataFrame(format_rows))

    st.markdown("**%s**" % TEXTS["experiment_seed"])
    ring_col, curve_col = st.columns(2)
    with ring_col:
        show(ring_chart(quality["pass_all"], quality["n"], TEXTS["dashboard_ring"]))
    with curve_col:
        curve = result["trials"][0]["convergence_penalty"]
        if curve:
            show(convergence_plot({result["config"]["ai"]: curve}))
            st.caption(TEXTS["experiment_curve"])
    st.table(
        pd.DataFrame(
            [
                {
                    "Entropi rata-rata": "%.3f" % quality["entropy_mean"],
                    "Entropi ternormalisasi": "%.3f" % quality["normalized_entropy_mean"],
                    "NIST pass rate": "%.1f%%" % (quality["nist_pass_rate_mean"] * 100),
                    "p-value minimum rata-rata": "%.4f" % quality["min_p_value_mean"],
                    "Waktu AI rata-rata (ms)": "%.2f" % quality["ai_time_ms_mean"],
                }
            ]
        )
    )


def _render_detector(result: dict) -> None:
    labels_actual = [TEXTS["label_random"], TEXTS["label_defective"]]
    labels_pred = [TEXTS["label_passed"], TEXTS["label_failed"]]
    left, right = st.columns(2)
    with left:
        show(confusion_heatmap(result["confusion"], TEXTS["detector_header"], labels_actual, labels_pred))
    with right:
        metrics = result["metrics"]
        st.table(
            pd.DataFrame(
                [{"Metrik": k, "Nilai": "%.4f" % metrics[k]} for k in METRIC_COLUMNS]
            )
        )
    st.markdown("**%s**" % TEXTS["detector_defect"])
    st.table(
        pd.DataFrame(
            [
                {"Jenis cacat": name, "Seed": d["n"], "Terdeteksi": d["detected"]}
                for name, d in result["per_defect"].items()
            ]
        )
    )


def render_experiment_panel(config: dict) -> None:
    st.subheader(TEXTS["experiment_header"])
    st.caption(TEXTS["experiment_intro"])

    source = st.radio(TEXTS["experiment_source"], EXPERIMENT_SOURCES, horizontal=True, key="experiment_source")
    limit = st.number_input(
        TEXTS["experiment_limit"], min_value=1, max_value=MAX_FILES_PER_FORMAT,
        value=MAX_FILES_PER_FORMAT, step=1, key="experiment_limit",
    )
    collect = _gather_documents(source, int(limit))

    low, high, default, step = EXPERIMENT_TRIALS_SPEC
    n_trials = st.slider(TEXTS["experiment_trials"], low, high, default, step, key="experiment_trials")
    modes = st.multiselect(TEXTS["experiment_modes"], TAMPER_MODES, default=list(TAMPER_MODES), key="experiment_modes")
    if "ElGamal" in CRYPTO_ALGORITHMS:
        st.caption(TEXTS["elgamal_warning"])

    if st.button(TEXTS["experiment_run"], type="primary", key="experiment_run"):
        documents = collect()
        if not documents or not modes:
            st.warning(TEXTS["experiment_none"])
        else:
            kwargs = build_ai_kwargs(
                config["ai_params"], config["bit_length"], config["tolerance_sigma"], None
            )
            bar = st.progress(0.0, text=TEXTS["experiment_running"])
            result = run_experiment(
                documents,
                config["ai_choice"],
                kwargs,
                config["key_sizes"],
                int(n_trials),
                tamper_modes=tuple(modes),
                limit_per_format=int(limit),
                random_state_base=config["random_state"],
                progress=lambda fraction: bar.progress(min(max(fraction, 0.0), 1.0)),
            )
            bar.empty()
            st.session_state["experiment"] = result
            st.session_state["experiment_path"] = save_result(result, "experiment", RESULTS_DIR)

    result = st.session_state.get("experiment")
    if result:
        st.caption(
            "%s | %s" % (AI_LABELS[result["config"]["ai"]], TEXTS["experiment_saved"] % st.session_state.get("experiment_path", RESULTS_DIR))
        )
        _render_experiment(result)

    st.divider()
    st.subheader(TEXTS["detector_header"])
    st.caption(TEXTS["detector_intro"])
    low, high, default, step = DETECTOR_SAMPLES_SPEC
    samples = st.slider(TEXTS["detector_samples"], low, high, default, step, key="detector_samples")
    if st.button(TEXTS["detector_run"], key="detector_run"):
        detector = randomness_detector_confusion(int(samples), config["bit_length"])
        detector["kind"] = "detector"
        st.session_state["detector"] = detector
        save_result(detector, "detector", RESULTS_DIR)
    if st.session_state.get("detector"):
        _render_detector(st.session_state["detector"])