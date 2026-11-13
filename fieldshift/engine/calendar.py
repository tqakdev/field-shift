"""Crop active-month calendars derived from crops.json season / type.

plant_month / harvest_month may be set explicitly on a crop; otherwise defaults
by season/type are used (conservative Midwestern temperate defaults).
"""

from __future__ import annotations

from typing import Any

from fieldshift.engine.crops import crop_by_id

# Defaults: (plant_month, harvest_month) inclusive active growing season
_DEFAULTS: dict[str, tuple[int, int]] = {
    "warm_cash": (5, 10),
    "cool_cash": (4, 8),
    "winter_cereal": (9, 7),  # Sep–Jul (wraps year)
    "cover": (10, 4),  # Oct–Apr
    "forage": (4, 10),
}


def plant_harvest_months(crop: dict[str, Any]) -> tuple[int, int]:
    if crop.get("plant_month") and crop.get("harvest_month"):
        return int(crop["plant_month"]), int(crop["harvest_month"])
    if crop["type"] == "cover":
        return _DEFAULTS["cover"]
    if crop["type"] == "forage":
        return _DEFAULTS["forage"]
    if "winter" in crop["id"] or (
        crop["season"] == "cool" and "wheat" in crop["id"] and "spring" not in crop["id"]
    ):
        return _DEFAULTS["winter_cereal"]
    if crop["season"] == "cool":
        return _DEFAULTS["cool_cash"]
    return _DEFAULTS["warm_cash"]


def active_months(crop_id: str) -> set[int]:
    """Set of calendar months (1–12) when the crop typically occupies the field."""
    c = crop_by_id(crop_id)
    plant, harvest = plant_harvest_months(c)
    if plant <= harvest:
        return set(range(plant, harvest + 1))
    # wraps year (e.g. Sep–Jul)
    return set(range(plant, 13)) | set(range(1, harvest + 1))


def fallow_months_from_rotation(rotation: list[str]) -> list[int]:
    """Months available for cover between cash/forage crops.

    Unoccupied months, plus each cash crop's harvest month (cover seeding window).
    Cover crops in ``rotation`` are ignored when computing baseline occupancy.
    """
    occupied: set[int] = set()
    harvest: set[int] = set()
    for cid in rotation:
        c = crop_by_id(cid)
        if c["type"] == "cover":
            continue
        occupied |= active_months(cid)
        _plant, harv = plant_harvest_months(c)
        harvest.add(harv)
    # free months + harvest months (planting into residue after harvest)
    free = {m for m in range(1, 13) if m not in occupied} | harvest
    return sorted(free)


def months_label(months: list[int]) -> str:
    if not months:
        return "none"
    ms = sorted(set(int(m) for m in months))
    # Contiguous runs on a circular calendar → "May–Jun, Nov–Dec"
    if not ms:
        return "none"
    # Find a break to unwrap
    start_i = 0
    for i in range(len(ms) - 1):
        if ms[i + 1] - ms[i] > 1:
            start_i = i + 1
            break
    order = ms[start_i:] + ms[:start_i]
    runs: list[list[int]] = [[order[0]]]
    for m in order[1:]:
        prev = runs[-1][-1]
        if m == prev + 1 or (prev == 12 and m == 1):
            runs[-1].append(m)
        else:
            runs.append([m])
    parts = []
    for run in runs:
        a = __import__("pandas").Timestamp(2020, run[0], 1).strftime("%b")
        if len(run) == 1:
            parts.append(a)
        else:
            b = __import__("pandas").Timestamp(2020, run[-1], 1).strftime("%b")
            parts.append(f"{a}–{b}")
    return ", ".join(parts)


def cover_fits_window(crop_id: str, window_months: list[int]) -> bool:
    """Cover fits if it substantially overlaps the fallow window (≥3 months or ≥50%)."""
    if not window_months:
        return False
    win = set(window_months)
    active = active_months(crop_id)
    inter = active & win
    if len(inter) >= 3:
        return True
    if active and len(inter) / len(active) >= 0.5:
        return True
    # Seed month in window is enough for short confirmed troughs
    plant, _ = plant_harvest_months(crop_by_id(crop_id))
    return plant in win
