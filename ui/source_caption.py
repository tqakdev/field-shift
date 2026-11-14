"""Render `source: <dataset>` captions under numbers."""

from __future__ import annotations

import streamlit as st


def source_caption(dataset: str, data_through: str | None = None) -> None:
    """Show a small source caption under a metric or chart value.

    Parameters
    ----------
    dataset:
        Dataset name or Earth Engine ID / access string shown to the user.
    data_through:
        Optional "Month Year" end of the series used for this number.
    """
    if data_through:
        st.caption(f"source: {dataset} · data through {data_through}")
    else:
        st.caption(f"source: {dataset}")
