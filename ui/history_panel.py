import os

import pandas as pd
import streamlit as st

from config import AI_LABELS, HISTORY_SECTIONS, REASON_LABELS, STATUS_LABELS, TEXTS
from modules.experiment.storage import to_json
from ui.benchmark_panel import render_benchmark_report
from ui.experiment_panel import render_detector_result, render_experiment_result


def _render_payload(kind: str, payload: dict) -> None:
    if kind == "experiment":
        render_experiment_result(payload)
    elif kind == "benchmark":
        render_benchmark_report(payload)
    elif kind == "detector":
        render_detector_result(payload)


def _results_section(repository) -> None:
    items = repository.list_results(limit=100)
    if not items:
        st.caption(TEXTS["history_none"])
        return
    chosen = st.selectbox(
        TEXTS["history_pick"],
        items,
        format_func=lambda i: "#%d | %s | %s | %s" % (i["id"], i["kind"], i["created_at"], i["summary"]),
        key="history_pick",
    )
    if st.button(TEXTS["history_show"], key="history_show"):
        st.session_state["history_payload"] = {
            "id": chosen["id"],
            "kind": chosen["kind"],
            "payload": repository.load_result(chosen["id"]),
        }
    shown = st.session_state.get("history_payload")
    if shown:
        st.download_button(
            TEXTS["history_json"],
            to_json(shown["payload"]),
            file_name="smartkey_%s_%d.json" % (shown["kind"], shown["id"]),
            mime="application/json",
            key="history_json",
        )
        _render_payload(shown["kind"], shown["payload"])


def _packages_section(repository) -> None:
    batches = repository.list_batches(limit=100)
    if not batches:
        st.caption(TEXTS["history_none"])
        return
    st.dataframe(pd.DataFrame(batches).drop(columns=["package_path"]), hide_index=True)
    chosen = st.selectbox(
        TEXTS["history_pick_batch"],
        batches,
        format_func=lambda b: "#%d | %s | %s | %d dokumen | %s" % (
            b["id"], b["kind"], b["algorithm"], b["doc_count"], b["created_at"]
        ),
        key="history_batch",
    )
    path = chosen["package_path"]
    if os.path.exists(path):
        with open(path, "rb") as handle:
            st.download_button(
                TEXTS["history_download_pkg"],
                handle.read(),
                file_name=os.path.basename(path),
                mime="application/zip",
                key="history_download_pkg",
            )
    else:
        st.warning(TEXTS["history_missing"])
    st.markdown("**%s**" % TEXTS["history_docs"])
    st.dataframe(
        pd.DataFrame(repository.list_signed_documents(chosen["id"], 200)),
        hide_index=True,
    )


def _verifications_section(repository) -> None:
    rows = repository.list_verifications(limit=500)
    if not rows:
        st.caption(TEXTS["history_none"])
        return
    frame = pd.DataFrame(rows)
    frame["status"] = frame["status"].map(STATUS_LABELS)
    frame["reason"] = frame["reason"].map(REASON_LABELS)
    st.dataframe(frame, hide_index=True)


def _keys_section(repository) -> None:
    rows = repository.list_keys()
    if not rows:
        st.caption(TEXTS["history_none"])
        return
    frame = pd.DataFrame(rows)
    frame["ai"] = frame["ai"].map(lambda v: AI_LABELS.get(v, v))
    st.dataframe(frame, hide_index=True)


def render_history_panel(repository) -> None:
    st.subheader(TEXTS["history_header"])
    counts = repository.counts()
    columns = st.columns(len(counts))
    for column, (name, value) in zip(columns, counts.items()):
        column.metric(name, value)

    section = st.radio(TEXTS["history_section"], HISTORY_SECTIONS, horizontal=True, label_visibility="collapsed", key="history_section")
    if section == HISTORY_SECTIONS[0]:
        _results_section(repository)
    elif section == HISTORY_SECTIONS[1]:
        _packages_section(repository)
    elif section == HISTORY_SECTIONS[2]:
        _verifications_section(repository)
    else:
        _keys_section(repository)
    st.caption(TEXTS["history_sensitive"])