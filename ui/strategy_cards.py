"""Strategy card rendering — compact, scannable mission cards."""

from __future__ import annotations

import html

import streamlit as st
from fieldshift.models import StrategyCard

from ui.components import season_pills
from ui.explainers import (
    format_score_line,
    score_band,
)
from ui.source_caption import source_caption
from ui.theme import SCORE_COLORS

_SCORE_KEYS = (
    "water",
    "soil_health",
    "erosion",
    "pest_break",
    "climate_fit",
    "income",
)


def _score_grid_html(card: StrategyCard) -> str:
    """2-column compact score grid — label · bar · value; meaning via title tooltip."""
    cells: list[str] = []
    for key in _SCORE_KEYS:
        val = float(getattr(card.scores, key))
        row = format_score_line(key, val)
        color = SCORE_COLORS.get(key, "#0B3D91")
        tip = html.escape(f"{row['orientation']} {row['detail']}")
        band_cls = row["band"].lower().replace(" ", "-")
        cells.append(
            f"""
<div class="fs-sc" title="{tip}">
  <div class="fs-sc-top">
    <span class="fs-sc-name">{html.escape(row['label'])}</span>
    <span class="fs-sc-val">{html.escape(row['display'])}</span>
  </div>
  <div class="fs-sc-track">
    <div class="fs-sc-fill" style="width:{row['pct']}%;background:{color};"></div>
  </div>
  <span class="fs-sc-band fs-band-{band_cls}">{html.escape(row['band'])}</span>
</div>
            """
        )
    return '<div class="fs-sc-grid">' + "".join(cells) + "</div>"


def render_score_legend() -> None:
    """Orientation once above the grid — keeps cards short."""
    st.caption(
        "Scores are **0–1** (also shown as %). Higher is better. "
        "Hover any bar for what that criterion means. "
        "Bands: Strong ≥0.75 · Good ≥0.55 · Fair ≥0.35 · Needs attention below."
    )
    with st.expander("What each score means", expanded=False):
        st.markdown(
            """
| Criterion | What it measures |
|-----------|------------------|
| **Water** | Crop water needs vs rainfall + your irrigation access |
| **Soil health** | Cover crops, legumes, rotation diversity |
| **Erosion** | Protection when soil would otherwise be bare |
| **Pest break** | Changing plant families to break pest/disease cycles |
| **Climate fit** | Match to frost-free season and heat |
| **Income** | Relative harvest/market proxy — not a farm budget |
| **Overall** | Weighted mix using *your* priority sliders |

**vs your rotation** = how this option compares to what you grow today.
            """
        )


def render_strategy_cards(
    cards: list[StrategyCard],
    *,
    show_climate_delta: bool = False,
) -> None:
    """Render strategy cards in a compact responsive grid."""
    if not cards:
        st.info("No strategies available.")
        return

    render_score_legend()

    n = len(cards)
    # Prefer 2-wide rows so cards stay readable; 3-wide gets too narrow + tall
    if n == 3:
        rows = [cards[:2], cards[2:]]
    elif n >= 4:
        rows = [cards[i : i + 2] for i in range(0, n, 2)]
    else:
        rows = [cards]

    for row in rows:
        cols = st.columns(len(row), gap="medium")
        for col, card in zip(cols, row, strict=True):
            with col:
                _render_one_card(card, show_climate_delta=show_climate_delta)


def _render_one_card(card: StrategyCard, *, show_climate_delta: bool) -> None:
    is_baseline = card.id == "current"
    delta = card.delta_vs_current.get("total")
    band, _ = score_band(card.scores.total)
    total = card.scores.total
    role = "YOUR ROTATION TODAY" if is_baseline else f"OPTION · {band.upper()}"

    delta_html = ""
    if delta is not None:
        sign = "+" if delta >= 0 else ""
        cls = "up" if delta > 0.005 else ("down" if delta < -0.005 else "flat")
        delta_html = (
            f'<span class="fs-card-delta {cls}">{sign}{delta:.2f} vs yours</span>'
        )

    climate_bit = ""
    if show_climate_delta and delta is not None:
        climate_bit = (
            f'<p class="fs-card-note">Climate scenario applied · '
            f"delta {delta:+.2f}</p>"
        )

    with st.container(border=True):
        st.markdown(
            f"""
<div class="fs-strat">
  <p class="fs-strat-role">{html.escape(role)}</p>
  <p class="fs-strat-title">{html.escape(card.name)}</p>
</div>
            """,
            unsafe_allow_html=True,
        )
        season_pills(card.sequence)

        conf = (card.confidence or "medium").lower()
        conf_icons = {"high": "●●●", "medium": "●●○", "low": "●○○"}
        conf_icon = conf_icons.get(conf, "●●○")

        st.markdown(
            f"""
<div class="fs-strat-summary">
  <div class="fs-strat-score">
    <span class="fs-strat-score-num">{total:.2f}</span>
    <span class="fs-strat-score-label">overall · {html.escape(band)}</span>
  </div>
  <div class="fs-strat-meta">
    {delta_html}
    <span class="fs-badge {html.escape(conf)}">{conf_icon} {html.escape(conf)}</span>
  </div>
</div>
{climate_bit}
            """,
            unsafe_allow_html=True,
        )
        st.markdown(_score_grid_html(card), unsafe_allow_html=True)

        with st.expander("Why · evidence · risks", expanded=False):
            st.markdown("**Why this option**")
            st.write(card.why)
            if card.evidence:
                st.markdown("**Evidence**")
                for item in card.evidence:
                    st.markdown(f"• {item.text}")
                    source_caption(
                        item.source, getattr(item, "data_through", None)
                    )
            if card.benefits:
                st.markdown("**Benefits**")
                for b in card.benefits:
                    st.write(f"• {b}")
            if card.data_gaps:
                st.markdown("**Data gaps**")
                for g in card.data_gaps:
                    st.write(f"• {g}")
            if card.risks_for_local_review:
                st.markdown("**Risks to check locally**")
                for r in card.risks_for_local_review:
                    st.write(f"• {r}")
            source_caption("Field Shift scoring engine")
