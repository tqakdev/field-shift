"""Assign farmer-facing tiers to scored strategy cards."""

from __future__ import annotations

from fieldshift.engine.thresholds import (
    BEST_FIT_MIN_DELTA,
    NOT_SUITABLE_TOTAL_DELTA,
    WORTH_CONSIDERING_OF_BEST,
)
from fieldshift.models import PriorityWeights, StrategyCard

TIER_LABELS = {
    "best_fit": "Best fit for your priorities",
    "worth_considering": "Worth considering",
    "baseline": "Your rotation today",
    "not_suitable": "Not suitable here",
}

TIER_ICONS = {
    "best_fit": "✓",
    "worth_considering": "◇",
    "baseline": "◎",
    "not_suitable": "✗",
}


def _highest_weight_key(weights: PriorityWeights) -> str:
    w = weights.model_dump()
    return max(w, key=lambda k: w[k])


def assign_tiers(
    cards: list[StrategyCard],
    *,
    weights: PriorityWeights | None = None,
) -> list[StrategyCard]:
    """Mutate/return cards with tier, tier_label, tier_reason filled.

    Rules (see thresholds.py):
    - baseline: id == current
    - not_suitable: hard constraints OR total < current − NOT_SUITABLE_TOTAL_DELTA
    - best_fit: at most one — highest suitable total, beats current by ≥ BEST_FIT_MIN_DELTA,
      confidence medium/high
    - worth_considering: suitable and within WORTH_CONSIDERING_OF_BEST of best, OR beats
      current on the user's highest-weighted criterion
    """
    weights = weights or PriorityWeights()
    top_key = _highest_weight_key(weights)

    baseline = next((c for c in cards if c.id == "current"), None)
    current_total = baseline.scores.total if baseline else 0.0
    current_crit = float(getattr(baseline.scores, top_key)) if baseline else 0.0

    # First pass: baseline + hard/soft not-suitable
    for card in cards:
        if card.id == "current":
            card.tier = "baseline"
            card.tier_label = f"{TIER_ICONS['baseline']} {TIER_LABELS['baseline']}"
            card.tier_reason = "This is the rotation you said you grow today."
            continue
        if card.unsuitable_reasons:
            card.tier = "not_suitable"
            card.tier_label = f"{TIER_ICONS['not_suitable']} {TIER_LABELS['not_suitable']}"
            card.tier_reason = "; ".join(card.unsuitable_reasons)
            continue
        delta = card.delta_vs_current.get("total", card.scores.total - current_total)
        if delta < -NOT_SUITABLE_TOTAL_DELTA:
            card.tier = "not_suitable"
            card.tier_label = f"{TIER_ICONS['not_suitable']} {TIER_LABELS['not_suitable']}"
            card.tier_reason = (
                f"Overall score is {abs(delta):.2f} below your current rotation "
                f"(threshold {NOT_SUITABLE_TOTAL_DELTA:.2f})."
            )
            continue
        # provisional — refined below
        card.tier = "worth_considering"

    suitable = [
        c
        for c in cards
        if c.id != "current" and c.tier != "not_suitable"
    ]
    best: StrategyCard | None = None
    if suitable:
        ranked = sorted(suitable, key=lambda c: c.scores.total, reverse=True)
        candidate = ranked[0]
        delta = candidate.delta_vs_current.get(
            "total", candidate.scores.total - current_total
        )
        if (
            delta >= BEST_FIT_MIN_DELTA
            and candidate.confidence in ("medium", "high")
        ):
            best = candidate
            best.tier = "best_fit"
            best.tier_label = f"{TIER_ICONS['best_fit']} {TIER_LABELS['best_fit']}"
            best.tier_reason = (
                f"Highest overall for your priorities "
                f"({best.scores.total:.2f}, {delta:+.2f} vs today)."
            )

    best_total = best.scores.total if best else (
        max((c.scores.total for c in suitable), default=current_total)
    )

    for card in cards:
        if card.tier in ("baseline", "not_suitable", "best_fit"):
            continue
        delta = card.delta_vs_current.get("total", card.scores.total - current_total)
        crit = float(getattr(card.scores, top_key))
        near_best = abs(card.scores.total - best_total) <= WORTH_CONSIDERING_OF_BEST
        beats_top_criterion = crit > current_crit + 1e-9
        card.tier = "worth_considering"
        card.tier_label = (
            f"{TIER_ICONS['worth_considering']} {TIER_LABELS['worth_considering']}"
        )
        top_label = top_key.replace("_", " ")
        if near_best and beats_top_criterion:
            card.tier_reason = f"Near the best option, and stronger on {top_label}."
        elif near_best:
            card.tier_reason = (
                f"Within {WORTH_CONSIDERING_OF_BEST:.2f} of the best suitable option."
            )
        elif beats_top_criterion:
            card.tier_reason = (
                f"Stronger than today on {top_label} (your top priority)."
            )
        elif delta > 0:
            card.tier_reason = (
                f"Slightly better overall than today ({delta:+.2f})."
            )
        else:
            card.tier_reason = (
                "Passes your farm constraints; review evidence before changing."
            )

    return cards


def recommendation_sentence(cards: list[StrategyCard]) -> str:
    """One plain sentence for the recommendation banner."""
    best = next((c for c in cards if c.tier == "best_fit"), None)
    baseline = next((c for c in cards if c.tier == "baseline"), None)
    if best is None:
        return (
            "Your current rotation is already a good fit for your priorities "
            "— no alternative clearly beats it under these settings."
        )
    delta = best.delta_vs_current.get("total")
    delta_bit = f" ({delta:+.2f} vs today)" if delta is not None else ""
    base_name = baseline.name if baseline else "your current rotation"
    return (
        f"{best.name} is the best fit for your priorities{delta_bit}, "
        f"ahead of {base_name}."
    )
