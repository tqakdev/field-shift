"""Render `source: <dataset>` captions under numbers."""

from __future__ import annotations

import streamlit as st


def source_caption(dataset: str) -> None:
    """Show a small source caption under a metric or chart value.

    Parameters
    ----------
    dataset:
        Dataset name or Earth Engine ID / access string shown to the user.
    """
    st.caption(f"source: {dataset}")
