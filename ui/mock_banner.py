"""Visible MOCK DATA banner for scaffold / placeholder paths."""

from __future__ import annotations

import streamlit as st


def show_mock_banner() -> None:
    """Render a high-visibility banner when serving labelled mock data."""
    st.warning(
        "**MOCK DATA** — placeholder round numbers for the Streamlit scaffold. "
        "Not real NASA results.",
        icon="⚠️",
    )
