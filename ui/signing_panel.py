import mimetypes
import os

import pandas as pd
import streamlit as st

from config import (
    MAX_FILES_PER_FORMAT,
    PACKAGES_DIR,
    SIGN_SOURCES,
    TEXTS,
    UPLOAD_TYPES,
)
from modules.evaluation.document_test import load_folder
from modules.experiment.runner import build_ai_kwargs
from modules.signing import sign_documents


def _collector(source: str):
    if source == SIGN_SOURCES[0]:
        files = st.file_uploader(
            TEXTS["sign_upload"], type=UPLOAD_TYPES, accept_multiple_files=True, key="sign_upload"
        )
        return lambda: [(f.name, f.getvalue()) for f in (files or [])]
    if source == SIGN_SOURCES[1]:
        text = st.text_area(TEXTS["sign_text"], key="sign_text")
        return lambda: [("teks.txt", text.encode("utf-8"))] if text else []
    path = st.text_input(TEXTS["sign_folder"], key="sign_folder")
    limit = st.number_input(
        TEXTS["sign_limit"],
        min_value=1,
        max_value=MAX_FILES_PER_FORMAT,
        value=MAX_FILES_PER_FORMAT,
        step=1,
        key="sign_limit",
    )
    return lambda: load_folder(path, int(limit)) if path else []


def _download_name(result: dict) -> str:
    base = os.path.basename(result["package_path"])
    if result["kind"] == "single":
        return base.split("_", 1)[1]
    return "signed_documents.zip"


def _download_mime(result: dict) -> str:
    if result["kind"] != "single":
        return "application/zip"
    guessed, _ = mimetypes.guess_type(_download_name(result))
    return guessed or "application/octet-stream"


def _render_result(result: dict, repository) -> None:
    st.success(
        TEXTS["sign_done"] % (result["doc_count"], result["algorithm"], result["key_size"])
    )
    st.caption(TEXTS["sign_key_info"] % (result["key_id"], result["batch_id"]))
    st.caption(TEXTS["sign_saved"] % result["package_path"])

    if os.path.exists(result["package_path"]):
        with open(result["package_path"], "rb") as handle:
            payload = handle.read()
        label = (
            TEXTS["sign_download_single"]
            if result["kind"] == "single"
            else TEXTS["sign_download_batch"]
        )
        st.download_button(
            label,
            payload,
            file_name=_download_name(result),
            mime=_download_mime(result),
            type="primary",
            key="sign_download",
        )
    if result.get("standard_pdf_count"):
        st.info(TEXTS["sign_standard_pdf"] % result["standard_pdf_count"])
    elif result.get("pdf_count"):
        st.caption(TEXTS["sign_standard_note"])
    st.caption(TEXTS["sign_next"])

    rows = repository.list_signed_documents(result["batch_id"], 50)
    st.markdown("**%s**" % TEXTS["sign_records"])
    st.dataframe(
        pd.DataFrame(rows).rename(
            columns={
                "name": TEXTS["sign_col_name"],
                "format": TEXTS["sign_col_format"],
                "size_bytes": TEXTS["sign_col_size"],
                "sha256": TEXTS["sign_col_sha"],
                "signature_preview": TEXTS["sign_col_signature"],
            }
        ),
        hide_index=True,
    )


def render_signing_panel(config: dict, repository) -> None:
    st.subheader(TEXTS["sign_header"])
    st.caption(TEXTS["sign_intro"])

    source = st.radio(TEXTS["sign_source"], SIGN_SOURCES, horizontal=True, key="sign_source")
    collect = _collector(source)

    if st.button(TEXTS["sign_button"], type="primary", key="sign_button"):
        documents = collect()
        if not documents:
            st.warning(TEXTS["sign_no_input"])
        else:
            kwargs = build_ai_kwargs(
                config["ai_params"],
                config["bit_length"],
                config["tolerance_sigma"],
                config["random_state"],
            )
            bar = st.progress(0.0, text=TEXTS["sign_running"])
            result = sign_documents(
                documents,
                config["ai_choice"],
                kwargs,
                config["crypto_choice"],
                config["key_size"],
                repository,
                PACKAGES_DIR,
                progress=lambda fraction: bar.progress(min(max(fraction, 0.0), 1.0)),
            )
            bar.empty()
            st.session_state["sign_result"] = result
            st.session_state["single"] = result

    result = st.session_state.get("sign_result")
    if result:
        _render_result(result, repository)