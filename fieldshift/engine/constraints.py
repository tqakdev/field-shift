"""Farm constraint checks — hard exclusions and soft penalties."""

from __future__ import annotations

from typing import Any

from fieldshift.engine.crops import crop_by_id
from fieldshift.engine.thresholds import (
    BUDGET_LOW_COVER_PENALTY,
    HAY_FORAGE_MIN,
    LABOR_LOW_COVER_PENALTY,
    MARKET_NO_BUYER_BLOCKS_CASH,
    ROW_CROP_IDS,
    SMALL_GRAIN_IDS,
)
from fieldshift.models import FarmConstraints


def sequence_has_legume(sequence: list[str]) -> bool:
    return any(bool(crop_by_id(c).get("nitrogen_fixing")) for c in sequence)


def evaluate_constraints(
    sequence: list[str],
    constraints: FarmConstraints,
    *,
    livestock: bool = False,
) -> dict[str, Any]:
    """Return hard unsuitable reasons and soft penalty amount + notes.

    Soft penalties reduce the displayed total but do not alone force Not suitable.
    """
    hard: list[str] = []
    soft_notes: list[str] = []
    soft_penalty = 0.0

    ids = set(sequence)
    covers = [c for c in sequence if crop_by_id(c)["type"] == "cover"]
    cash = [c for c in sequence if crop_by_id(c)["type"] != "cover"]

    # Machinery
    if constraints.has_small_grain_harvest is False and ids & SMALL_GRAIN_IDS:
        hard.append("Needs small-grain harvest equipment you said you don't have")
    if constraints.has_row_crop_planter is False and ids & ROW_CROP_IDS:
        hard.append("Needs a row-crop planter you said you don't have")
    needs_hay = any(
        float(crop_by_id(c).get("forage_value") or 0) >= HAY_FORAGE_MIN for c in sequence
    )
    if constraints.has_hay_forage_equipment is False and needs_hay and not livestock:
        # With livestock, forage can be grazed without hay kit
        hard.append("Needs hay/forage equipment (or livestock grazing) for forage crops")

    # Market access — cash crops only
    if MARKET_NO_BUYER_BLOCKS_CASH:
        for cid in cash:
            access = constraints.market_access.get(cid, "unknown")
            if access == "no_market":
                # On-farm forage/cover exception already excludes covers from cash
                hard.append(
                    f"No local market for {crop_by_id(cid)['name']} "
                    "(and it is not an on-farm forage/cover use)"
                )

    # Soft: budget / labor for new covers
    if covers:
        if constraints.budget_new_seed == "low":
            soft_penalty += BUDGET_LOW_COVER_PENALTY
            soft_notes.append(
                f"Low seed budget (−{BUDGET_LOW_COVER_PENALTY:.2f} soft penalty for cover seed)"
            )
        if constraints.labor == "low":
            soft_penalty += LABOR_LOW_COVER_PENALTY
            soft_notes.append(
                f"Low labor (−{LABOR_LOW_COVER_PENALTY:.2f} soft penalty for managing cover)"
            )

    return {
        "unsuitable": bool(hard),
        "reasons": hard,
        "soft_penalty": float(soft_penalty),
        "soft_notes": soft_notes,
    }
