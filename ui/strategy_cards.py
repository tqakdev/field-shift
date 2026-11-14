"""Strategy card rendering — flat Streamlit-demo style."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st
from fieldshift.engine.card_copy import (
    SCORE_KEYS,
    farmer_comparison_sentence,
    format_delta_label,
    rotation_title_line,
    top_criterion_diffs,
)
from fieldshift.models import ScoreSet, StrategyCard

from ui.charts import scores_bar
from ui.source_caption import source_caption
from ui.theme import PRIMARY, SCORE_COLORS

_TIER_ORDER = ("baseline", "best_fit", "worth_considering", "not_suitable")


def render_score_legend() -> None:
    st.caption(
        "Scores are **0–100**. Higher is better. "
        "Cards are grouped by tier (icon + label — not colour alone)."
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

| Band | Score (0–100) |
|------|----------------|
| **Strong** | 75–100 |
| **Good** | 55–74 |
| **Fair** | 35–54 |
| **Weak** | 0–34 |

| Criterion | What it measures |
|-----------|------------------|
| **Water** | Crop water needs vs rainfall + irrigation |
| **Soil health** | Cover, legumes, and diversity |
| **Erosion** | Protection when soil would otherwise be bare |
| **Pest break** | Changing plant families |
| **Climate fit** | Frost-free season and heat |
| **Income** | Relative price tier × yield potential |

**Delta display:** if the overall change vs your rotation is smaller than
**0.02**, the card shows “About the same as yours” instead of a signed delta.
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

    baseline = next((c for c in cards if c.tier == "baseline"), None)
    baseline_scores = baseline.scores if baseline else None

    by_tier: dict[str, list[StrategyCard]] = {t: [] for t in _TIER_ORDER}
    for card in cards:
        tier = card.tier or "worth_considering"
        by_tier.setdefault(tier, []).append(card)

    for tier in ("baseline", "best_fit", "worth_considering"):
        group = by_tier.get(tier) or []
        if not group:
            continue
        label = group[0].tier_label or tier
        st.markdown(f"##### {label}")
        _render_row(
            group,
            baseline_scores=baseline_scores,
            show_climate_delta=show_climate_delta,
            allow_expanders=True,
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
            _render_row(
                bad,
                baseline_scores=baseline_scores,
                show_climate_delta=show_climate_delta,
                allow_expanders=False,
            )


def _render_row(
    cards: list[StrategyCard],
    *,
    baseline_scores: ScoreSet | None,
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
                    baseline_scores=baseline_scores,
                    show_climate_delta=show_climate_delta,
                    allow_expanders=allow_expanders,
                )


def _top3_html(diffs: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for d in diffs:
        sign = "+" if d["delta"] >= 0 else ""
        delta_s = f"{sign}{d['delta']:.2f}"
        if d["direction"] == "better":
            verb = f"better ({delta_s})"
        elif d["direction"] == "worse":
            verb = f"lower ({delta_s})"
        else:
            verb = "similar (0.00)"
        color = SCORE_COLORS.get(d["key"], PRIMARY)
        parts.append(
            f"""
<div class="fs-diff">
  <div class="fs-diff-top">
    <span class="fs-diff-name">{html.escape(d['label'])}: {html.escape(verb)}</span>
    <span class="fs-diff-band">{html.escape(d['band'])} · {d['pct']}</span>
  </div>
  <div class="fs-diff-track">
    <div class="fs-diff-fill" style="width:{d['pct']}%;background:{color};"></div>
  </div>
</div>
            """
        )
    return '<div class="fs-diff-list">' + "".join(parts) + "</div>"


def _render_one_card(
    card: StrategyCard,
    *,
    baseline_scores: ScoreSet | None,
    show_climate_delta: bool,
    allow_expanders: bool = True,
) -> None:
    delta = card.delta_vs_current.get("total")
    total_pct = int(round(max(0.0, min(1.0, card.scores.total)) * 100))
    tier = card.tier or "worth_considering"
    title = rotation_title_line(card.sequence)

    diffs = top_criterion_diffs(card.scores, baseline_scores, n=3)
    if tier == "baseline":
        sentence = "This is the rotation you said you grow today."
    else:
        sentence = farmer_comparison_sentence(diffs, overall_delta=delta)

    if tier == "baseline":
        delta_html = ""
    else:
        delta_text, delta_tone = format_delta_label(delta)
        delta_cls = {"up": "up", "down": "down", "neutral": "flat"}[delta_tone]
        arrow = "↑ " if delta_tone == "up" else ("↓ " if delta_tone == "down" else "")
        delta_html = (
            f'<div class="fs-card-delta {delta_cls}">'
            f"{arrow}{html.escape(delta_text)}</div>"
        )

    conf = (card.confidence or "medium").lower()
    conf_icons = {"high": "●●●", "medium": "●●○", "low": "●○○"}
    conf_icon = conf_icons.get(conf, "●●○")

    badge = ""
    if tier == "best_fit":
        badge = '<span class="fs-best-badge">Best fit</span>'

    climate_bit = ""
    if show_climate_delta and delta is not None and tier != "baseline":
        climate_bit = (
            f'<p class="fs-card-note">Climate scenario applied · '
            f"change {delta:+.2f}</p>"
        )

    flags = ""
    if card.unsuitable_reasons:
        flags = (
            '<div class="fs-strat-flags">'
            + "".join(
                f'<div class="bad">✗ {html.escape(r)}</div>'
                for r in card.unsuitable_reasons
            )
            + "</div>"
        )
    elif card.soft_notes:
        flags = (
            '<div class="fs-strat-flags">'
            + "".join(f"<div>· {html.escape(n)}</div>" for n in card.soft_notes)
            + "</div>"
        )

    with st.container(border=True):
        st.markdown(
            f"""
<div class="fs-strat">
  {badge}
  <p class="fs-strat-title">{html.escape(title)}</p>
  <p class="fs-tier-reason">{html.escape(sentence)}</p>
  {flags}
  <div class="fs-overall">
    <div>
      <div class="fs-overall-label">Overall</div>
      <div class="fs-overall-num">{total_pct}</div>
    </div>
    {delta_html}
  </div>
  {climate_bit}
  {"" if tier == "baseline" else _top3_html(diffs)}
  <p class="fs-conf">{conf_icon} Confidence: {html.escape(conf)}</p>
  <div class="fs-card-spacer" aria-hidden="true"></div>
</div>
            """,
            unsafe_allow_html=True,
        )

        def _details() -> None:
            st.caption("All criteria (0–100)")
            st.plotly_chart(
                scores_bar(card.scores, height=160),
                use_container_width=True,
                config={"displayModeBar": False},
            )
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
            with st.expander("Why, evidence and risks", expanded=False):
                _details()
        else:
            st.caption(card.why)


__all__ = ["SCORE_KEYS", "render_strategy_cards", "render_score_legend"]
