import pandas as pd
import streamlit as st

from config import NIST_COLUMNS, TEXTS
from modules.evaluation.convergence import penalty_curve
from ui.charts import convergence_plot, radar_chart, ring_chart, show

RADAR_LABELS = (
    ("entropy_p_value", "Entropi"),
    ("diff_entropy_p_value", "Selisih"),
)


def _radar_values(evaluation: dict) -> dict:
    values = {label: evaluation.get(key, 0.0) for key, label in RADAR_LABELS}
    for name, result in evaluation.get("nist_results", {}).items():
        values[name.replace(" Test", "")] = result["p_value"]
    return values


def render_dashboard() -> None:
    st.subheader(TEXTS["dashboard_header"])
    state = st.session_state.get("single")
    if not state:
        st.info(TEXTS["dashboard_none"])
        return

    evaluation = state["evaluation"]

    row = st.columns(4)
    row[0].metric(TEXTS["metric_time"], "%.2f ms" % evaluation.get("time_ms", 0.0))
    row[1].metric(
        TEXTS["metric_entropy"],
        "%.3f / %.3f" % (evaluation["entropy_shannon"], evaluation["entropy_max_bits"]),
        help=TEXTS["metric_entropy_help"],
    )
    row[2].metric(TEXTS["metric_normalized"], "%.3f" % evaluation["normalized_entropy"])
    row[3].metric(TEXTS["metric_nist"], "%.1f%%" % (evaluation["nist_pass_rate"] * 100))

    timing = st.columns(3)
    timing[0].metric(TEXTS["metric_keygen"], "%.2f ms" % state["keygen_ms"])
    timing[1].metric(TEXTS["metric_sign"], "%.2f ms" % state["sign_ms"])
    verify_ms = state.get("verify_ms")
    timing[2].metric(TEXTS["metric_verify"], "-" if verify_ms is None else "%.3f ms" % verify_ms)

    st.markdown("**%s**" % TEXTS["dashboard_nist"])
    rows = [
        {
            NIST_COLUMNS[0]: name,
            NIST_COLUMNS[1]: "%.4f" % result["p_value"],
            NIST_COLUMNS[2]: TEXTS["test_pass"] if result["passed"] else TEXTS["test_fail"],
        }
        for name, result in evaluation["nist_results"].items()
    ]
    rows.append(
        {
            NIST_COLUMNS[0]: "Entropi byte",
            NIST_COLUMNS[1]: "%.4f" % evaluation["entropy_p_value"],
            NIST_COLUMNS[2]: TEXTS["test_pass"] if evaluation["entropy_passed"] else TEXTS["test_fail"],
        }
    )
    rows.append(
        {
            NIST_COLUMNS[0]: "Entropi selisih",
            NIST_COLUMNS[1]: "%.4f" % evaluation["diff_entropy_p_value"],
            NIST_COLUMNS[2]: TEXTS["test_pass"] if evaluation["diff_entropy_passed"] else TEXTS["test_fail"],
        }
    )
    st.table(pd.DataFrame(rows))

    ring_col, radar_col, curve_col = st.columns(3)
    with ring_col:
        show(ring_chart(evaluation["tests_passed"], evaluation["tests_total"], TEXTS["dashboard_ring"]))
    with radar_col:
        show(radar_chart(_radar_values(evaluation), TEXTS["dashboard_radar"]))
    with curve_col:
        curve = penalty_curve(evaluation)
        if curve:
            show(convergence_plot({state["ai"]: curve}))
            st.caption(TEXTS["dashboard_curve"])

    st.caption(TEXTS["dashboard_note"])
    if evaluation.get("entropy_source_secure") is False:
        st.warning(TEXTS["dashboard_insecure"] % evaluation["entropy_source"])
    elif "entropy_source" in evaluation:
        st.caption(TEXTS["dashboard_source"] % evaluation["entropy_source"])