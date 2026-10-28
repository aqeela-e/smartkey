import streamlit as st

from config import RESULTS_DIR, TEXTS
from modules.experiment.storage import list_results, to_json


def _single_report(state: dict) -> dict:
    return {
        "kind": "single_signature",
        "ai": state["ai"],
        "ai_kwargs": state["ai_kwargs"],
        "algorithm": state["algorithm"],
        "key_size": state["key_size"],
        "document": {
            "name": state["document_name"],
            "size_bytes": state["document_size"],
            "sha256": state["document_sha256"],
        },
        "seed_hex": state["seed_hex"],
        "derived_seed_hex": state["derived_seed_hex"],
        "public_key": state["public_key_export"],
        "signature_hex": state["signature"].hex(),
        "timing_ms": {
            "keygen": state["keygen_ms"],
            "sign": state["sign_ms"],
            "verify": state["verify_ms"],
        },
        "evaluation": state["evaluation"],
        "verifications": state["verifications"],
        "tamper_results": state["tamper_results"],
    }


def render_output_panel() -> None:
    st.subheader(TEXTS["export_header"])
    single = st.session_state.get("single")
    experiment = st.session_state.get("experiment")
    benchmark = st.session_state.get("benchmark")

    if not (single or experiment or benchmark):
        st.write(TEXTS["export_none"])

    columns = st.columns(4)
    if single:
        with columns[0]:
            st.download_button(
                TEXTS["export_single"],
                to_json(_single_report(single)),
                file_name="smartkey_signature_report.json",
                mime="application/json",
                key="download_single",
            )
        with columns[1]:
            st.download_button(
                TEXTS["export_sig"],
                single["signature"],
                file_name="document.sig",
                mime="application/octet-stream",
                key="download_sig",
            )
    if experiment:
        with columns[2]:
            st.download_button(
                TEXTS["export_experiment"],
                to_json(experiment),
                file_name="smartkey_experiment_report.json",
                mime="application/json",
                key="download_experiment",
            )
    if benchmark:
        with columns[3]:
            st.download_button(
                TEXTS["export_benchmark"],
                to_json(benchmark),
                file_name="smartkey_benchmark_report.json",
                mime="application/json",
                key="download_benchmark",
            )

    st.markdown("**%s**" % TEXTS["export_history"])
    names = list_results(RESULTS_DIR)
    if names:
        st.table({"Berkas": names})
    else:
        st.caption(TEXTS["export_history_none"])
    st.caption(TEXTS["export_sensitive"])