import os
import sys

import streamlit as st

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import APP_TITLE, DATABASE_PATH, PAGE_LAYOUT, TEXTS
from modules.db import Repository
from ui import (
    inject_styles,
    render_benchmark_panel,
    render_dashboard,
    render_experiment_panel,
    render_history_panel,
    render_sidebar,
    render_signing_panel,
    render_verify_panel,
)


@st.cache_resource
def get_repository() -> Repository:
    return Repository(DATABASE_PATH)


def main():
    st.set_page_config(page_title=APP_TITLE, layout=PAGE_LAYOUT)
    inject_styles()
    repository = get_repository()
    st.title(TEXTS["title"])
    st.caption(TEXTS["subtitle"])

    config = render_sidebar()
    tabs = st.tabs(
        [
            TEXTS["tab_sign"],
            TEXTS["tab_verify"],
            TEXTS["tab_experiment"],
            TEXTS["tab_benchmark"],
            TEXTS["tab_dashboard"],
            TEXTS["tab_history"],
        ]
    )
    with tabs[0]:
        render_signing_panel(config, repository)
    with tabs[1]:
        render_verify_panel(repository)
    with tabs[2]:
        render_experiment_panel(config, repository)
    with tabs[3]:
        render_benchmark_panel(repository)
    with tabs[4]:
        render_dashboard()
    with tabs[5]:
        render_history_panel(repository)


if __name__ == "__main__":
    main()