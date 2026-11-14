"""Render `source: <dataset>` captions under numbers."""

from __future__ import annotations

import streamlit as st

from ui.glossary import SOURCE_LABELS


def _friendly_dataset(dataset: str) -> str:
    """Replace internal ids with farmer-facing labels; never show raw underscores."""
    key = dataset.strip()
    if key in SOURCE_LABELS:
        return SOURCE_LABELS[key]
    # Map known fragments inside longer strings
    out = dataset
    for raw, label in SOURCE_LABELS.items():
        if raw in out:
            out = out.replace(raw, label)
    return out.replace("_", " ")


def source_caption(dataset: str, data_through: str | None = None) -> None:
    """Show a small muted source caption under a metric or chart value."""
    label = _friendly_dataset(dataset)
    if data_through:
        st.caption(f"source: {label} · data through {data_through}")
    else:
        st.caption(f"source: {label}")
