import streamlit as st

from config import STYLE


def inject_styles() -> None:
    css = """
    <style>
    html, body, .stMarkdown, p, label {{
        font-weight: {weight};
    }}
    h1, h2, h3, h4 {{
        font-weight: {heading};
        letter-spacing: 0;
    }}
    [data-testid="stMetric"], [data-testid="stExpander"], .stAlert {{
        border-radius: {radius};
        border: 1px solid {border};
        box-shadow: none;
    }}
    [data-testid="stMetric"] {{
        padding: 12px 14px;
    }}
    [data-testid="stMetricValue"] {{
        font-weight: {weight};
    }}
    .stButton > button, .stDownloadButton > button {{
        border-radius: {radius};
        box-shadow: none;
        font-weight: {heading};
    }}
    [data-baseweb="select"] > div, [data-baseweb="input"] > div, .stTextArea textarea {{
        border-radius: {radius};
        box-shadow: none;
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 2px;
        padding: 3px;
        background: {tab_surface};
        border: 1px solid {border};
        border-radius: {tab_radius};
        width: fit-content;
    }}
    .stTabs [data-baseweb="tab"] {{
        height: 34px;
        padding: 0 14px;
        border-radius: {tab_radius};
        font-weight: {weight};
        background: transparent;
    }}
    .stTabs [aria-selected="true"] {{
        background: {tab_active};
        border: 1px solid {border};
        font-weight: {heading};
    }}
    .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{
        display: none;
    }}
    section[data-testid="stSidebar"] {{
        border-right: 1px solid {border};
    }}
    </style>
    """.format(
        weight=STYLE["font_weight"],
        heading=STYLE["heading_weight"],
        radius=STYLE["card_radius"],
        tab_radius=STYLE["tab_radius"],
        border=STYLE["border"],
        tab_surface=STYLE["tab_surface"],
        tab_active=STYLE["tab_active"],
    )
    st.markdown(css, unsafe_allow_html=True)