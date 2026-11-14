"""Season slots for the rotation builder (from NDVI phenology)."""

from __future__ import annotations

from typing import Any

from fieldshift.engine.crops import crop_by_id, load_crops
from fieldshift.engine.scoring import score_climate_fit

CLIMATE_FIT_UI_MIN = 0.35


def rotation_slots_from_features(
    features: dict[str, Any],
    *,
    max_cash: int = 4,
    cycle_years: int = 1,
) -> list[dict[str, Any]]:
    """Build cash season slots (+ cover gaps) from NDVI phenology.

    Phenology yields 1–2 seasons/year. ``cycle_years`` repeats those seasons
    so a multi-year rotation can hold up to ``max_cash`` cash crops. Each bare
    / fallow gap gets an optional cover slot.
    """
    ph = features.get("phenology") or {}
    seasons = list(ph.get("seasons") or [])
    bare = list((features.get("bare_months") or {}).get("months") or [])
    fallow = list(ph.get("fallow_months") or bare)
    slots: list[dict[str, Any]] = []

    year_seasons: list[dict[str, Any]]
    if seasons:
        year_seasons = seasons[:2]
    else:
        year_seasons = [
            {"label": "main_season", "months": list(range(5, 11))},
        ]

    cycle_years = max(1, min(int(cycle_years), 4))
    cash_i = 0
    for year in range(cycle_years):
        if cash_i >= max_cash:
            break
        for s in year_seasons:
            if cash_i >= max_cash:
                break
            months = list(s.get("months") or [])
            label = str(s.get("label") or f"season_{cash_i + 1}")
            year_bit = f" · Y{year + 1}" if cycle_years > 1 else ""
            slots.append(
                {
                    "kind": "cash",
                    "id": f"cash_{cash_i}",
                    "label": f"{label.replace('_', ' ').title()}{year_bit}",
                    "months": months,
                }
            )
            cash_i += 1
        gap = fallow or bare
        if gap:
            slots.append(
                {
                    "kind": "cover",
                    "id": f"cover_{year}",
                    "label": (
                        f"Cover in bare window{year_bit}"
                        if cycle_years > 1
                        else "Cover in bare window"
                    ),
                    "months": list(gap),
                    "optional": True,
                }
            )

    if not any(s["kind"] == "cash" for s in slots):
        slots.insert(
            0,
            {
                "kind": "cash",
                "id": "cash_0",
                "label": "Main season",
                "months": list(range(5, 11)),
            },
        )
    return slots


def crops_for_slot(
    slot: dict[str, Any],
    features: dict[str, Any],
    *,
    always_allow: list[str] | None = None,
) -> list[dict[str, Any]]:
    """List crops with enabled flag + reason for UI pickers."""
    months = slot.get("months") or None
    want_cover = slot.get("kind") == "cover"
    allow = set(always_allow or [])
    out: list[dict[str, Any]] = []
    for c in load_crops():
        cid = c["id"]
        is_cover = c.get("type") == "cover"
        if want_cover and not is_cover:
            out.append(
                {
                    "id": cid,
                    "name": c["name"],
                    "enabled": False,
                    "reason": "Cash crop — use a main-season slot",
                }
            )
            continue
        if not want_cover and is_cover:
            out.append(
                {
                    "id": cid,
                    "name": c["name"],
                    "enabled": False,
                    "reason": "Cover crop — use the bare-window slot",
                }
            )
            continue
        try:
            fit = score_climate_fit([cid], features, season_months=months)
        except Exception:  # noqa: BLE001
            fit = 0.0
        if cid in allow or fit >= CLIMATE_FIT_UI_MIN:
            out.append(
                {
                    "id": cid,
                    "name": c["name"],
                    "enabled": True,
                    "reason": (
                        f"Climate fit {fit:.2f}"
                        if fit >= CLIMATE_FIT_UI_MIN
                        else "Kept because it is in your current rotation"
                    ),
                    "climate_fit": fit,
                }
            )
        else:
            out.append(
                {
                    "id": cid,
                    "name": c["name"],
                    "enabled": False,
                    "reason": f"Weak climate fit for this slot ({fit:.2f})",
                }
            )
    out.sort(key=lambda r: (not r["enabled"], r["name"]))
    return out


def default_rotation_for_slots(
    slots: list[dict[str, Any]],
    preferred: list[str],
) -> list[str]:
    """Map preferred crop ids onto cash slots; drop extras."""
    cash_slots = [s for s in slots if s.get("kind") == "cash"]
    n = max(1, len(cash_slots))
    cash = [c for c in preferred if crop_by_id(c)["type"] != "cover"]
    if not cash:
        cash = ["maize"]
    while len(cash) < n:
        cash.append(cash[-1])
    return cash[:n]
