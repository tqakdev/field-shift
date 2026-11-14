"""Field Shift — Streamlit entrypoint with explicit navigation routes."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Field Shift",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui.theme import inject_theme  # noqa: E402

inject_theme()

home = st.Page("views/home.py", title="Home", icon="🌾", default=True)
field = st.Page("views/field.py", title="Field", icon="🗺️", url_path="field")
how = st.Page(
    "views/how_it_works.py",
    title="How it works",
    icon="📖",
    url_path="how-it-works",
)

pg = st.navigation([home, field, how])
pg.run()
