"""Strategy card rendering — tiered, scannable mission cards."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st
from fieldshift.models import StrategyCard

from ui.explainers import format_score_line
from ui.source_caption import source_caption
from ui.theme import PRIMARY, SCORE_COLORS

_SCORE_KEYS = (
    "water",
    "soil_health",
    "erosion",
    "pest_break",
    "climate_fit",
    "income",
)

# Baseline first so the current farm situation is always visible.
_TIER_ORDER = ("baseline", "best_fit", "worth_considering", "not_suitable")
_TIER_CSS = {
    "best_fit": "fs-tier-best",
    "worth_considering": "fs-tier-worth",
    "baseline": "fs-tier-base",
    "not_suitable": "fs-tier-bad",
}


def _score_grid_html(card: StrategyCard) -> str:
    cells: list[str] = []
    for key in _SCORE_KEYS:
        val = float(getattr(card.scores, key))
        row = format_score_line(key, val)
        color = SCORE_COLORS.get(key, PRIMARY)
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


def _pills_html(sequence: list[Any]) -> str:
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
        parts.append(f'<span class="fs-pill">{html.escape(label)}</span>')
    return '<div class="fs-pills">' + "".join(parts) + "</div>"


def _flags_html(card: StrategyCard) -> str:
    lines: list[str] = []
    for r in card.unsuitable_reasons or []:
        lines.append(f'<div class="bad">✗ {html.escape(r)}</div>')
    for n in card.soft_notes or []:
        lines.append(f"<div>· {html.escape(n)}</div>")
    # Keep a reserved band so peer cards stay level even with no flags.
    body = "".join(lines) if lines else "&nbsp;"
    return f'<div class="fs-strat-flags">{body}</div>'


def render_score_legend() -> None:
    st.caption(
        "Scores are **0–1** (also shown as %). Higher is better. "
        "Cards are grouped by tier (icon + label — not color alone). "
        "Hover any bar for what that criterion means."
    )
    with st.expander("What each score and tier means", expanded=False):
        st.markdown(
            """
| Tier | Meaning |
|------|---------|
| **✓ Best fit** | Highest overall, beats your rotation by ≥0.02, passes constraints |
| **◇ Worth considering** | Passes constraints; near the best or wins on your top priority |
| **◎ Your rotation today** | Baseline you entered |
| **✗ Not suitable here** | Fails a hard constraint or is clearly weaker than today |

| Criterion | What it measures |
|-----------|------------------|
| **Water** | Crop water needs vs rainfall + irrigation |
| **Soil health** | Cover, legumes, diversity (+ N-fertilizer context) |
| **Erosion** | Protection when soil would otherwise be bare |
| **Pest break** | Changing plant families |
| **Climate fit** | Frost-free season and heat |
| **Income** | Relative price tier × yield potential, adjusted for market access |

**Income tooltip formula:** mean(market_tier of cash crops) − cover seed cost
+ livestock forage bonus + buyer lift. Not a farm budget.
            """
        )


def render_strategy_cards(
    cards: list[StrategyCard],
    *,
    show_climate_delta: bool = False,
) -> None:
    """Render cards grouped by tier."""
    if not cards:
        st.info("No strategies available.")
        return

    render_score_legend()

    by_tier: dict[str, list[StrategyCard]] = {t: [] for t in _TIER_ORDER}
    for card in cards:
        tier = card.tier or "worth_considering"
        by_tier.setdefault(tier, []).append(card)

    for tier in ("baseline", "best_fit", "worth_considering"):
        group = by_tier.get(tier) or []
        if not group:
            continue
        label = group[0].tier_label or tier
        st.markdown(f"**{label}**")
        _render_row(
            group, show_climate_delta=show_climate_delta, allow_expanders=True
        )

    bad = by_tier.get("not_suitable") or []
    if bad:
        with st.expander(
            f"Show options we don't recommend ({len(bad)})",
            expanded=False,
        ):
            st.caption(
                "These fail a hard farm constraint or score clearly below "
                "your current rotation for your priorities."
            )
            # Streamlit forbids nested expanders — inline details instead.
            _render_row(
                bad,
                show_climate_delta=show_climate_delta,
                allow_expanders=False,
            )


def _render_row(
    cards: list[StrategyCard],
    *,
    show_climate_delta: bool,
    allow_expanders: bool = True,
) -> None:
    n = len(cards)
    rows = [cards[i : i + 2] for i in range(0, n, 2)] if n > 2 else [cards]
    for row in rows:
        cols = st.columns(len(row), gap="medium")
        for col, card in zip(cols, row, strict=True):
            with col:
                _render_one_card(
                    card,
                    show_climate_delta=show_climate_delta,
                    allow_expanders=allow_expanders,
                )


def _render_one_card(
    card: StrategyCard,
    *,
    show_climate_delta: bool,
    allow_expanders: bool = True,
) -> None:
    delta = card.delta_vs_current.get("total")
    total = card.scores.total
    tier = card.tier or "worth_considering"
    tier_cls = _TIER_CSS.get(tier, "fs-tier-worth")
    role = html.escape(card.tier_label or tier.replace("_", " ").title())
    reason = html.escape(card.tier_reason or "")

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

    conf = (card.confidence or "medium").lower()
    conf_icons = {"high": "●●●", "medium": "●●○", "low": "●○○"}
    conf_icon = conf_icons.get(conf, "●●○")

    with st.container(border=True):
        # One HTML block for chrome + pills + scores so paired cards share rhythm.
        # Overall label has no Strong/Good/Fair — tiers already carry that meaning.
        st.markdown(
            f"""
<div class="fs-strat {tier_cls}">
  <p class="fs-strat-role">{role}</p>
  <p class="fs-strat-title">{html.escape(card.name)}</p>
  <p class="fs-tier-reason">{reason}</p>
</div>
{_pills_html(card.sequence)}
{_flags_html(card)}
<div class="fs-strat-summary">
  <div class="fs-strat-score">
    <span class="fs-strat-score-num">{total:.2f}</span>
    <span class="fs-strat-score-label">Overall</span>
  </div>
  <div class="fs-strat-meta">
    {delta_html}
    <span class="fs-badge {html.escape(conf)}">{conf_icon} {html.escape(conf)}</span>
  </div>
</div>
{climate_bit}
{_score_grid_html(card)}
<div class="fs-card-spacer" aria-hidden="true"></div>
            """,
            unsafe_allow_html=True,
        )

        def _details() -> None:
            st.markdown("**Why this option**")
            st.write(card.why)
            if card.benefits:
                st.markdown("**Benefits**")
                for b in card.benefits:
                    st.write(f"• {b}")
            if card.evidence:
                st.markdown("**Evidence**")
                for item in card.evidence:
                    st.markdown(f"• {item.text}")
                    source_caption(
                        item.source, getattr(item, "data_through", None)
                    )
            if card.data_gaps:
                st.markdown("**Data gaps**")
                for g in card.data_gaps:
                    st.write(f"• {g}")
            if card.risks_for_local_review:
                st.markdown("**Risks to check locally**")
                for r in card.risks_for_local_review:
                    st.write(f"• {r}")
            source_caption("Field Shift scoring engine")

        if allow_expanders:
            with st.expander("Why · evidence · risks", expanded=False):
                _details()
        else:
            st.caption(card.why)
