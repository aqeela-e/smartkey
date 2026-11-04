import pandas as pd
import streamlit as st

from config import REASON_LABELS, STATUS_LABELS, TEXTS
from modules.evaluation.confusion import add_outcome, confusion_metrics, empty_counts
from modules.evaluation.document_test import TAMPER_MODES, tamper
from modules.signing import (
    STATUS_INVALID,
    STATUS_UNSIGNED,
    STATUS_VALID,
    check_signature,
    expand_uploads,
    read_package,
    verify_package,
)
from modules.signing.package import PackageError
from ui.charts import confusion_heatmap, ring_chart, show


def _expanded(uploads):
    for upload in uploads:
        for name, data in expand_uploads(upload.name, upload.getvalue()):
            yield name, data


def _verify_uploads(uploads, repository) -> list:
    rows = []
    for name, data in _expanded(uploads):
        outcome = verify_package(data, repository.find_key)
        repository.add_verification(name, outcome)
        rows.append(
            {
                TEXTS["verify_col_name"]: name,
                TEXTS["verify_col_status"]: STATUS_LABELS[outcome["status"]],
                TEXTS["verify_col_reason"]: REASON_LABELS[outcome["reason"]],
                TEXTS["verify_col_algo"]: outcome["algorithm"] or "-",
                TEXTS["verify_col_key"]: (
                    "-"
                    if outcome["key_registered"] is None
                    else TEXTS["verify_yes"] if outcome["key_registered"] else TEXTS["verify_no"]
                ),
                "_status": outcome["status"],
                "_registered": outcome["key_registered"],
            }
        )
    return rows


def _tamper_counts(uploads) -> dict:
    counts = empty_counts()
    for _, data in _expanded(uploads):
        try:
            package = read_package(data)
        except PackageError:
            continue
        document = package["document"]
        if not check_signature(package, document):
            continue
        add_outcome(counts, True, check_signature(package, document))
        for mode in TAMPER_MODES:
            add_outcome(counts, False, check_signature(package, tamper(document, mode)))
    return counts


def _render_summary(rows: list) -> None:
    statuses = [r["_status"] for r in rows]
    valid = statuses.count(STATUS_VALID)
    invalid = statuses.count(STATUS_INVALID)
    unsigned = statuses.count(STATUS_UNSIGNED)

    left, right = st.columns([2, 1])
    with left:
        row = st.columns(3)
        row[0].metric(TEXTS["verify_valid"], valid)
        row[1].metric(TEXTS["verify_invalid"], invalid)
        row[2].metric(TEXTS["verify_unsigned"], unsigned)
    with right:
        show(ring_chart(valid, len(rows), TEXTS["verify_valid"]))

    if any(r["_registered"] is False for r in rows):
        st.warning(TEXTS["verify_warn_unregistered"])

    visible = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    st.dataframe(pd.DataFrame(visible), hide_index=True)


def render_verify_panel(repository) -> None:
    st.subheader(TEXTS["verify_header"])
    st.caption(TEXTS["verify_intro"])
    uploads = st.file_uploader(
        TEXTS["verify_upload"], accept_multiple_files=True, key="verify_upload"
    )

    if st.button(TEXTS["verify_button"], type="primary", key="verify_button"):
        if not uploads:
            st.warning(TEXTS["verify_none"])
        else:
            st.session_state["verify_rows"] = _verify_uploads(uploads, repository)
            st.session_state.pop("verify_tamper", None)

    rows = st.session_state.get("verify_rows")
    if not rows:
        return
    _render_summary(rows)

    st.divider()
    st.caption(TEXTS["verify_tamper_note"])
    if st.button(TEXTS["verify_tamper_button"], key="verify_tamper_button") and uploads:
        st.session_state["verify_tamper"] = _tamper_counts(uploads)

    counts = st.session_state.get("verify_tamper")
    if counts:
        labels = [TEXTS["label_valid"], TEXTS["label_invalid"]]
        left, right = st.columns(2)
        with left:
            show(confusion_heatmap(counts, TEXTS["verify_tamper_title"], labels, labels))
        with right:
            metrics = confusion_metrics(counts)
            st.table(
                pd.DataFrame(
                    [
                        {"Metrik": k, "Nilai": "%.4f" % metrics[k]}
                        for k in ("accuracy", "precision", "recall", "specificity", "f1")
                    ]
                )
            )