import pandas as pd
import streamlit as st

from config import (
    BENCHMARK_ANN_HIDDEN,
    BENCHMARK_BIT_LENGTH,
    BENCHMARK_BUDGET,
    BENCHMARK_TOLERANCE,
    BENCHMARK_TRIALS_SPEC,
    RESULTS_DIR,
    TEXTS,
)
from modules.evaluation.benchmark import (
    NAME_REJECTION,
    NAME_URANDOM,
    build_ai_generators,
    build_baseline_generators,
    report_to_tables,
    run_benchmark,
)
from modules.experiment.storage import save_result
from ui.charts import rate_with_interval, show


def _rate_rows(report: dict, rate_key: str, ci_key: str) -> list:
    return [
        {
            "name": name,
            "rate": report["summary"][name][rate_key],
            "low": report["summary"][name][ci_key][0],
            "high": report["summary"][name][ci_key][1],
        }
        for name in report["arms"]
    ]


def render_benchmark_report(report: dict) -> None:
    selection = report.get("selection", {})
    message = selection.get("message", "")
    basis = selection.get("basis")
    if basis == "statistical_winner":
        st.success(message)
    elif basis == "efficiency_tiebreak":
        st.warning(message)
    elif message:
        st.error(message)
    if selection.get("power_note"):
        st.caption(selection["power_note"])

    tables = report_to_tables(report)
    st.markdown("**%s**" % TEXTS["benchmark_rates"])
    left, right = st.columns(2)
    with left:
        show(rate_with_interval(_rate_rows(report, "rate_indep", "ci_indep"), "Uji independen"))
    with right:
        show(rate_with_interval(_rate_rows(report, "rate_all", "ci_all"), "Semua tes"))

    st.markdown("**%s**" % TEXTS["benchmark_summary"])
    st.table(pd.DataFrame(tables["summary"]))
    st.markdown("**%s**" % TEXTS["benchmark_indep"])
    st.table(pd.DataFrame(tables["comparison_indep"]))
    with st.expander(TEXTS["benchmark_all"]):
        st.table(pd.DataFrame(tables["comparison_all"]))
    for note in report.get("notes", []):
        st.caption(note)


def render_benchmark_panel() -> None:
    st.subheader(TEXTS["benchmark_header"])
    st.caption(TEXTS["benchmark_intro"])
    low, high, default, step = BENCHMARK_TRIALS_SPEC
    n_trials = st.slider(TEXTS["benchmark_trials"], low, high, default, step, key="benchmark_trials")

    if st.button(TEXTS["benchmark_run"], type="primary", key="benchmark_run"):
        generators = build_ai_generators(
            BENCHMARK_BIT_LENGTH, BENCHMARK_BUDGET, BENCHMARK_TOLERANCE, BENCHMARK_ANN_HIDDEN
        )
        generators.update(
            build_baseline_generators(BENCHMARK_BIT_LENGTH, BENCHMARK_BUDGET, BENCHMARK_TOLERANCE)
        )
        bar = st.progress(0.0, text=TEXTS["benchmark_progress"])
        report = run_benchmark(
            generators,
            references=[NAME_URANDOM, NAME_REJECTION],
            n_trials=int(n_trials),
            progress=lambda fraction: bar.progress(min(max(fraction, 0.0), 1.0)),
        )
        bar.empty()
        report["kind"] = "benchmark"
        report["config"] = {
            "bit_length": BENCHMARK_BIT_LENGTH,
            "budget": BENCHMARK_BUDGET,
            "tolerance_sigma": BENCHMARK_TOLERANCE,
            "ann_hidden": BENCHMARK_ANN_HIDDEN,
            "n_trials": int(n_trials),
        }
        st.session_state["benchmark"] = report
        st.session_state["benchmark_path"] = save_result(report, "benchmark", RESULTS_DIR)

    report = st.session_state.get("benchmark")
    if report:
        st.caption(TEXTS["experiment_saved"] % st.session_state.get("benchmark_path", RESULTS_DIR))
        render_benchmark_report(report)
    else:
        st.info(TEXTS["benchmark_none"])