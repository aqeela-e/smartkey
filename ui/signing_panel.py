import hashlib
import time

import pandas as pd
import streamlit as st

from config import AI_LABELS, TEXTS, UPLOAD_TYPES
from modules.crypto.key_generator import CryptoKeyGenerator
from modules.evaluation.document_test import TAMPER_MODES, tamper
from modules.evaluation.metrics import Evaluator
from modules.experiment.runner import build_ai, build_ai_kwargs


def _read_message():
    uploaded = st.file_uploader(TEXTS["sign_upload"], type=UPLOAD_TYPES, key="single_upload")
    typed = st.text_area(TEXTS["sign_text"], key="single_text")
    if uploaded is not None:
        return uploaded.name, uploaded.getvalue()
    if typed:
        return "teks", typed.encode("utf-8")
    return None, None


def _sign(config: dict, name: str, message: bytes) -> None:
    generator = build_ai(config["ai_choice"])
    kwargs = build_ai_kwargs(
        config["ai_params"],
        config["bit_length"],
        config["tolerance_sigma"],
        config["random_state"],
    )
    seed, ai_metrics = generator.generate(**kwargs)
    evaluation = Evaluator.evaluate_seed(seed, ai_metrics)

    crypto_gen = CryptoKeyGenerator(config["crypto_choice"])
    key_size = config["key_size"]

    start = time.perf_counter()
    private_key, public_key = crypto_gen.generate_keys(seed, key_size)
    keygen_ms = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    signature = crypto_gen.sign(private_key, message)
    sign_ms = (time.perf_counter() - start) * 1000

    st.session_state["single"] = {
        "ai": config["ai_choice"],
        "algorithm": crypto_gen.algorithm,
        "key_size": key_size,
        "document_name": name,
        "document_size": len(message),
        "document_sha256": hashlib.sha256(message).hexdigest(),
        "seed_hex": seed.hex(),
        "derived_seed_hex": crypto_gen.derive_seed(seed, key_size).hex(),
        "ai_kwargs": kwargs,
        "evaluation": evaluation,
        "signature": signature,
        "public_key": public_key,
        "public_key_export": crypto_gen.export_public_key(public_key),
        "crypto_gen": crypto_gen,
        "keygen_ms": keygen_ms,
        "sign_ms": sign_ms,
        "verify_ms": None,
        "verifications": [],
        "tamper_results": [],
    }


def _verify(message: bytes) -> bool:
    state = st.session_state["single"]
    start = time.perf_counter()
    valid = state["crypto_gen"].verify(state["public_key"], message, state["signature"])
    state["verify_ms"] = (time.perf_counter() - start) * 1000
    state["verifications"].append(
        {"document_sha256": hashlib.sha256(message).hexdigest(), "valid": bool(valid)}
    )
    return bool(valid)


def _tamper_cases(message: bytes) -> pd.DataFrame:
    state = st.session_state["single"]
    cases = [(TEXTS["tamper_original"], message, True)]
    cases += [(mode, tamper(message, mode), False) for mode in TAMPER_MODES]
    rows = []
    for label, data, expected in cases:
        valid = state["crypto_gen"].verify(state["public_key"], data, state["signature"])
        rows.append(
            {
                TEXTS["tamper_col_case"]: label,
                TEXTS["tamper_col_valid"]: bool(valid),
                TEXTS["tamper_col_expected"]: expected,
            }
        )
    state["tamper_results"] = rows
    return pd.DataFrame(rows)


def render_signing_panel(config: dict) -> None:
    st.subheader(TEXTS["sign_header"])
    name, message = _read_message()
    if message is None:
        st.info(TEXTS["sign_no_input"])
        return

    st.caption(TEXTS["sign_hash"])
    st.code(hashlib.sha256(message).hexdigest())

    if st.button(TEXTS["sign_button"], type="primary", key="sign_button"):
        with st.spinner(TEXTS["sign_spinner"]):
            _sign(config, name, message)
        state = st.session_state["single"]
        st.success(TEXTS["sign_done"] % (AI_LABELS[state["ai"]], state["algorithm"]))

    state = st.session_state.get("single")
    if not state:
        return

    with st.expander(TEXTS["sign_signature"]):
        st.code(state["signature"].hex())

    verify_col, tamper_col = st.columns(2)
    with verify_col:
        if st.button(TEXTS["verify_button"], key="verify_button"):
            if _verify(message):
                st.success(TEXTS["verify_ok"])
            else:
                st.error(TEXTS["verify_fail"])
    with tamper_col:
        if st.button(TEXTS["tamper_button"], key="tamper_button"):
            st.caption(TEXTS["tamper_title"])
            st.table(_tamper_cases(message))