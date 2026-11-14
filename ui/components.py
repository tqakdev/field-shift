"""Reusable Field Shift UI building blocks (NASA mission-report look)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from ui.theme import EARTH, MUTED, NASA_BLUE, SCORE_COLORS


def hero(
    title: str,
    promise: str,
    *,
    sub: str | None = None,
    mode_label: str = "Demo",
    live: bool = False,
    eyebrow: str = "NASA Space Apps · Earth Science",
) -> None:
    """Top-of-page hero with NASA-style accent bar and mode pill."""
    pill_class = "fs-mode-pill" if live else "fs-mode-pill demo"
    sub_html = f'<p class="fs-hero-sub">{sub}</p>' if sub else ""
    st.markdown(
        f"""
<div class="fs-hero">
  <p class="fs-eyebrow">{eyebrow}</p>
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
    clean = title.lstrip()
    step_html = (
        f'<span class="fs-step">{step:02d}</span>&nbsp;' if step is not None else ""
    )
    st.markdown(
        f'<div class="fs-section">{step_html}'
        f'<span class="fs-section-title">{clean}</span></div>',
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(f'<p class="fs-section-sub">{subtitle}</p>', unsafe_allow_html=True)


def fact_chips(chips: list[dict[str, str]]) -> None:
    """Render fact chips with value + plain-language meaning.

    Each chip: label, value, optional meaning (orientation), help/source.
    """
    cols = st.columns(len(chips) if chips else 1)
    for col, chip in zip(cols, chips, strict=False):
        with col:
            meaning = chip.get("meaning") or ""
            meaning_html = (
                f'<p class="fs-chip-meaning">{meaning}</p>' if meaning else ""
            )
            st.markdown(
                f"""
<div class="fs-chip">
  <p class="fs-chip-label">{chip.get("label", "")}</p>
  <p class="fs-chip-value">{chip.get("value", "")}</p>
  {meaning_html}
</div>
                """,
                unsafe_allow_html=True,
            )
            if chip.get("help"):
                st.caption(chip["help"])


def recommendation_banner(text: str) -> None:
    """One-sentence top recommendation callout."""
    st.markdown(
        f'<div class="fs-banner"><strong>Recommended strategy — </strong>{text}</div>',
        unsafe_allow_html=True,
    )


def confidence_badge(level: str) -> None:
    """Accessible confidence badge (color + text + density marks)."""
    level = (level or "medium").lower()
    icons = {"high": "●●●", "medium": "●●○", "low": "●○○"}
    icon = icons.get(level, "●●○")
    st.markdown(
        f'<span class="fs-badge {level}" title="Confidence: {level}">'
        f"{icon} {level}</span>",
        unsafe_allow_html=True,
    )


def season_pills(sequence: list[Any]) -> None:
    """Render rotation sequence as season pills with arrows."""
    parts: list[str] = []
    for i, slot in enumerate(sequence):
        crop = getattr(slot, "crop_id", None) or (
            slot.get("crop_id") if isinstance(slot, dict) else "?"
        )
        months = getattr(slot, "months", None) or (
            slot.get("months") if isinstance(slot, dict) else ""
        )
        name = str(crop).replace("_", " ").title()
        label = f"{name} {months}".strip() if months else name
        if i:
            parts.append('<span class="fs-pill-arrow">→</span>')
        parts.append(f'<span class="fs-pill">{label}</span>')
    st.markdown('<div class="fs-pills">' + "".join(parts) + "</div>", unsafe_allow_html=True)


def weights_bar(weights: dict[str, float]) -> None:
    """Tiny horizontal bar of live priority weights."""
    import plotly.graph_objects as go

    labels = {
        "water": "Water",
        "soil_health": "Soil",
        "erosion": "Erosion",
        "pest_break": "Pest",
        "climate_fit": "Climate",
        "income": "Income",
    }
    keys = list(weights.keys())
    fig = go.Figure(
        go.Bar(
            x=[weights[k] for k in keys],
            y=[labels.get(k, k) for k in keys],
            orientation="h",
            marker_color=[SCORE_COLORS.get(k, NASA_BLUE) for k in keys],
            text=[f"{weights[k]:.1f}" for k in keys],
            textposition="outside",
            cliponaxis=False,
        )
    )
    fig.update_layout(
        height=170,
        margin={"l": 70, "r": 36, "t": 8, "b": 8},
        xaxis={"range": [0, 2.35], "title": None, "gridcolor": "#EEF2F7"},
        yaxis={"autorange": "reversed"},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        font={"family": "IBM Plex Sans, sans-serif", "size": 12, "color": "#0B1220"},
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def demo_field_cards(
    cards: list[dict[str, Any]],
) -> str | None:
    """Render equal-height demo cards; return clicked field id or None.

    Each card dict: id, name, climate, country, rotation, thumb_path.
    Layout uses aligned rows (thumbs → copy → buttons) so buttons share a baseline.
    """
    if not cards:
        return None

    n = len(cards)
    # Row 1 — thumbnails (fixed aspect)
    cols = st.columns(n, gap="medium")
    for col, card in zip(cols, cards, strict=True):
        with col:
            thumb = card.get("thumb_path")
            if thumb:
                st.image(thumb, use_container_width=True)
            else:
                st.markdown(
                    '<div style="aspect-ratio:5/4;background:#EEF2F7;'
                    'border:1px solid #D5DCE6;"></div>',
                    unsafe_allow_html=True,
                )

    # Row 2 — copy with equal min-heights via CSS classes
    cols = st.columns(n, gap="medium")
    for col, card in zip(cols, cards, strict=True):
        with col:
            st.markdown(
                f"""
<div class="fs-demo-copy">
  <p class="fs-demo-card-title">{card["name"]}</p>
  <p class="fs-demo-card-meta">{card["climate"]} · {card["country"]}</p>
  <p class="fs-demo-card-rot">Rotation · {card["rotation"]}</p>
</div>
                """,
                unsafe_allow_html=True,
            )

    # Row 3 — buttons on one baseline
    clicked: str | None = None
    cols = st.columns(n, gap="medium")
    for col, card in zip(cols, cards, strict=True):
        with col:
            if st.button(
                "Open field report",
                key=f"demo-{card['id']}",
                use_container_width=True,
                type="primary",
            ):
                clicked = card["id"]
    return clicked


# Back-compat alias used nowhere critical
def demo_field_card(**kwargs: Any) -> bool:
    """Deprecated single-card helper — prefer demo_field_cards()."""
    result = demo_field_cards(
        [
            {
                "id": kwargs.get("button_key", "x").replace("demo-", ""),
                "name": kwargs.get("name", ""),
                "climate": kwargs.get("climate", ""),
                "country": kwargs.get("country", ""),
                "rotation": kwargs.get("rotation", ""),
                "thumb_path": kwargs.get("thumb_path"),
            }
        ]
    )
    return result is not None


__all__ = [
    "EARTH",
    "MUTED",
    "NASA_BLUE",
    "SCORE_COLORS",
    "confidence_badge",
    "demo_field_card",
    "demo_field_cards",
    "fact_chips",
    "hero",
    "recommendation_banner",
    "season_pills",
    "section",
    "weights_bar",
]
