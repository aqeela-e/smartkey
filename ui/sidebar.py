import streamlit as st

from config import (
    AI_LABELS,
    AI_PARAM_SPECS,
    BIT_LENGTH_OPTIONS,
    CRYPTO_ALGORITHMS,
    CRYPTO_DEFAULT_KEY_SIZE,
    CRYPTO_KEY_SIZES,
    DEFAULT_BIT_LENGTH,
    REPRODUCTION_SEED_DEFAULT,
    TEXTS,
    TOLERANCE_SPEC,
)


def _slider(spec):
    key, label, minimum, maximum, default, step = spec
    return key, st.sidebar.slider(label, minimum, maximum, default, step, key="ai_" + key)


def render_sidebar() -> dict:
    st.sidebar.header(TEXTS["sidebar_title"])

    st.sidebar.subheader(TEXTS["sidebar_ai"])
    ai_choice = st.sidebar.selectbox(
        TEXTS["sidebar_ai"],
        list(AI_LABELS),
        format_func=lambda k: AI_LABELS[k],
        label_visibility="collapsed",
        key="ai_choice",
    )

    st.sidebar.subheader(TEXTS["sidebar_ai_param"])
    raw = dict(_slider(spec) for spec in AI_PARAM_SPECS[ai_choice])
    ai_params = dict(raw)
    if ai_choice == "ANN":
        layers = tuple(v for v in (ai_params.pop("hidden_1"), ai_params.pop("hidden_2")) if v > 0)
        ai_params["hidden_layers"] = layers

    bit_length = st.sidebar.selectbox(
        TEXTS["sidebar_bit_length"],
        BIT_LENGTH_OPTIONS,
        index=BIT_LENGTH_OPTIONS.index(DEFAULT_BIT_LENGTH),
        key="bit_length",
    )
    low, high, default, step = TOLERANCE_SPEC
    tolerance_sigma = st.sidebar.slider(
        TEXTS["sidebar_tolerance"], low, high, default, step, key="tolerance_sigma"
    )

    reproduce = st.sidebar.checkbox(
        TEXTS["sidebar_repro"], value=False, help=TEXTS["sidebar_repro_help"], key="reproduce"
    )
    random_state = None
    if reproduce:
        random_state = int(
            st.sidebar.number_input(
                TEXTS["sidebar_repro_seed"], min_value=0, value=REPRODUCTION_SEED_DEFAULT, step=1, key="repro_seed"
            )
        )

    st.sidebar.subheader(TEXTS["sidebar_crypto"])
    crypto_choice = st.sidebar.selectbox(
        TEXTS["sidebar_crypto_choice"], CRYPTO_ALGORITHMS, key="crypto_choice"
    )
    key_sizes = {}
    with st.sidebar.expander(TEXTS["sidebar_key_sizes"], expanded=False):
        for algorithm in CRYPTO_ALGORITHMS:
            sizes = CRYPTO_KEY_SIZES[algorithm]
            key_sizes[algorithm] = st.selectbox(
                TEXTS["sidebar_key_size"] % algorithm,
                sizes,
                index=sizes.index(CRYPTO_DEFAULT_KEY_SIZE[algorithm]),
                key="key_size_" + algorithm,
            )
    if crypto_choice == "ElGamal":
        st.sidebar.caption(TEXTS["elgamal_warning"])

    return {
        "ai_choice": ai_choice,
        "ai_params": ai_params,
        "bit_length": int(bit_length),
        "tolerance_sigma": float(tolerance_sigma),
        "random_state": random_state,
        "crypto_choice": crypto_choice,
        "key_sizes": key_sizes,
        "key_size": key_sizes[crypto_choice],
    }