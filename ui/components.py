"""Reusable Field Shift UI building blocks (advisory-report look)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from ui.theme import ALERT, LEAF, MUTED, SCORE_COLORS, SOIL, WHEAT


def hero(
    title: str,
    promise: str,
    *,
    sub: str | None = None,
    mode_label: str = "Demo",
    live: bool = False,
) -> None:
    """Top-of-page hero with promise line and mode pill."""
    pill_class = "fs-mode-pill" if live else "fs-mode-pill demo"
    sub_html = f'<p class="fs-hero-sub">{sub}</p>' if sub else ""
    st.markdown(
        f"""
<div class="fs-hero">
  <div class="fs-title">{title}</div>
  <p class="fs-hero-promise">{promise}</p>
  {sub_html}
  <span class="{pill_class}">{mode_label}</span>
</div>
        """,
        unsafe_allow_html=True,
    )


def section(title: str, subtitle: str | None = None, *, step: int | None = None) -> None:
    """Numbered section header with optional subtitle."""
    step_html = f'<span class="fs-step">{step}</span>' if step is not None else ""
    st.markdown(
        f'<div class="fs-section">{step_html}'
        f'<span class="fs-section-title">{title}</span></div>',
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(f'<p class="fs-section-sub">{subtitle}</p>', unsafe_allow_html=True)


def fact_chips(chips: list[dict[str, str]]) -> None:
    """Render a row of fact chips. Each chip: label, value, optional help/source."""
    cols = st.columns(len(chips) if chips else 1)
    for col, chip in zip(cols, chips, strict=False):
        with col:
            help_txt = chip.get("help")
            st.markdown(
                f"""
<div class="fs-chip">
  <p class="fs-chip-label">{chip.get("label", "")}</p>
  <p class="fs-chip-value">{chip.get("value", "")}</p>
</div>
                """,
                unsafe_allow_html=True,
            )
            if help_txt:
                st.caption(help_txt)


def recommendation_banner(text: str) -> None:
    """One-sentence top recommendation callout."""
    st.markdown(
        f'<div class="fs-banner"><strong>Top pick for you:</strong> {text}</div>',
        unsafe_allow_html=True,
    )


def confidence_badge(level: str) -> None:
    """Accessible confidence badge (color + text label)."""
    level = (level or "medium").lower()
    icons = {"high": "●●●", "medium": "●●○", "low": "●○○"}
    icon = icons.get(level, "●●○")
    st.markdown(
        f'<span class="fs-badge {level}" title="Confidence: {level}">'
        f"{icon} {level} confidence</span>",
        unsafe_allow_html=True,
    )


def season_pills(sequence: list[Any]) -> None:
    """Render rotation sequence as season pills."""
    parts: list[str] = []
    for slot in sequence:
        crop = getattr(slot, "crop_id", None) or (
            slot.get("crop_id") if isinstance(slot, dict) else "?"
        )
        months = getattr(slot, "months", None) or (
            slot.get("months") if isinstance(slot, dict) else ""
        )
        name = str(crop).replace("_", " ").title()
        label = f"{name} {months}".strip() if months else name
        parts.append(f'<span class="fs-pill">{label}</span>')
    st.markdown(
        '<div class="fs-pills">' + " → ".join(parts) + "</div>",
        unsafe_allow_html=True,
    )


def weights_bar(weights: dict[str, float]) -> None:
    """Tiny horizontal bar of live priority weights."""
    import plotly.graph_objects as go

    labels = {
        "water": "💧 Water",
        "soil_health": "🌱 Soil",
        "erosion": "🛡 Erosion",
        "pest_break": "🐛 Pest",
        "climate_fit": "🌤 Climate",
        "income": "💰 Income",
    }
    keys = list(weights.keys())
    fig = go.Figure(
        go.Bar(
            x=[weights[k] for k in keys],
            y=[labels.get(k, k) for k in keys],
            orientation="h",
            marker_color=[SCORE_COLORS.get(k, LEAF) for k in keys],
            text=[f"{weights[k]:.1f}" for k in keys],
            textposition="auto",
        )
    )
    fig.update_layout(
        height=180,
        margin={"l": 80, "r": 20, "t": 10, "b": 10},
        xaxis={"range": [0, 2.2], "title": None},
        yaxis={"autorange": "reversed"},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def demo_field_card(
    *,
    name: str,
    climate: str,
    country: str,
    rotation: str,
    thumb_path: str | None,
    button_key: str,
) -> bool:
    """Home-page demo picker card. Returns True if Open clicked."""
    st.markdown('<div class="fs-card demo-pick">', unsafe_allow_html=True)
    if thumb_path:
        st.image(thumb_path, use_container_width=True)
    st.subheader(name)
    st.caption(f"{climate} · {country}")
    st.write(f"**Rotation:** {rotation}")
    clicked = st.button("Open", key=button_key, use_container_width=True, type="primary")
    st.markdown("</div>", unsafe_allow_html=True)
    return clicked


# Re-export tokens for charts
__all__ = [
    "ALERT",
    "LEAF",
    "MUTED",
    "SCORE_COLORS",
    "SOIL",
    "WHEAT",
    "confidence_badge",
    "demo_field_card",
    "fact_chips",
    "hero",
    "recommendation_banner",
    "season_pills",
    "section",
    "weights_bar",
]
