import os
import sys

import streamlit as st

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import APP_TITLE, PAGE_LAYOUT, TEXTS
from ui import (
    inject_styles,
    render_benchmark_panel,
    render_dashboard,
    render_experiment_panel,
    render_output_panel,
    render_sidebar,
    render_signing_panel,
)


def main():
    st.set_page_config(page_title=APP_TITLE, layout=PAGE_LAYOUT)
    inject_styles()
    st.title(TEXTS["title"])
    st.caption(TEXTS["subtitle"])

    config = render_sidebar()
    tabs = st.tabs(
        [
            TEXTS["tab_sign"],
            TEXTS["tab_experiment"],
            TEXTS["tab_benchmark"],
            TEXTS["tab_dashboard"],
            TEXTS["tab_export"],
        ]
    )
    with tabs[0]:
        render_signing_panel(config)
    with tabs[1]:
        render_experiment_panel(config)
    with tabs[2]:
        render_benchmark_panel()
    with tabs[3]:
        render_dashboard()
    with tabs[4]:
        render_output_panel()


if __name__ == "__main__":
    main()