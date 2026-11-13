"""Detect green seasons and fallow gaps from monthly NDVI climatology.

Primary source for fallow / season windows (crops.json calendars are fallback only).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from fieldshift.engine.calendar import active_months, months_label, plant_harvest_months
from fieldshift.engine.crops import crop_by_id

GREEN_THRESH = 0.45
FALLOW_THRESH = 0.35

# Canonical dual-cropping windows when warm + cool peaks are detected.
KHARIF_MONTHS = [6, 7, 8, 9, 10]  # Jun–Oct
RABI_MONTHS = [11, 12, 1, 2, 3, 4]  # Nov–Apr


def monthly_ndvi_climatology(ndvi: pd.Series) -> dict[int, float]:
    """Mean NDVI by calendar month (1–12)."""
    if ndvi.empty:
        return {}
    return {int(m): float(v) for m, v in ndvi.groupby(ndvi.index.month).mean().items()}


def _expand_from_peak(
    peak: int, clim: dict[int, float], *, floor: float
) -> list[int]:
    """Grow a season left/right from peak while NDVI ≥ floor (circular)."""
    run = [peak]
    # left
    m = peak
    for _ in range(11):
        m = 12 if m == 1 else m - 1
        if clim.get(m, 0.0) >= floor:
            run.insert(0, m)
        else:
            break
    # right
    m = peak
    for _ in range(11):
        m = 1 if m == 12 else m + 1
        if clim.get(m, 0.0) >= floor:
            run.append(m)
        else:
            break
    # unique preserving order
    seen: set[int] = set()
    out: list[int] = []
    for x in run:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _local_peaks(clim: dict[int, float], thresh: float) -> list[int]:
    """Calendar months that are local maxima and ≥ thresh."""
    peaks = []
    for m in range(1, 13):
        v = clim.get(m, 0.0)
        if v < thresh:
            continue
        prev_m = 12 if m == 1 else m - 1
        next_m = 1 if m == 12 else m + 1
        if v >= clim.get(prev_m, 0.0) and v >= clim.get(next_m, 0.0):
            peaks.append(m)
    # If no strict local max, take absolute max months above thresh
    if not peaks:
        above = [m for m in range(1, 13) if clim.get(m, 0.0) >= thresh]
        if above:
            peaks = [max(above, key=lambda m: clim.get(m, 0.0))]
    return peaks


def detect_seasons_from_ndvi(
    ndvi: pd.Series,
    *,
    green_thresh: float = GREEN_THRESH,
    fallow_thresh: float = FALLOW_THRESH,
    source_label: str = "Sentinel-2 NDVI",
) -> dict[str, Any]:
    """Detect 1–2 green seasons (peaks ≥ green_thresh) and fallow troughs (< fallow_thresh).

    Seasons expand from each peak while NDVI ≥ fallow_thresh. When a warm-peak and
    cool-peak pair is found, months snap to canonical kharif (Jun–Oct) / rabi
    (Nov–Apr) so dual rice–wheat systems get agronomically useful windows.
    Fallow prefers the deepest inter-season trough (often May–Jun).
    """
    clim = monthly_ndvi_climatology(ndvi)
    if len(clim) < 6:
        return {
            "seasons": [],
            "fallow_months": [],
            "climatology": clim,
            "source": source_label,
            "detail": "insufficient NDVI climatology for phenology",
            "n_seasons": 0,
        }

    mx = max(clim.values()) if clim else 0.0
    # Adaptive peak gate: mixed pixels may never reach 0.45; still detect relative peaks.
    peak_thresh = green_thresh
    if mx < green_thresh and mx >= fallow_thresh + 0.05:
        peak_thresh = max(fallow_thresh + 0.05, float(mx) * 0.90)

    peaks = _local_peaks(clim, peak_thresh)
    # Also take warm-half / cool-half maxima when both clear a trough floor —
    # needed for rice–wheat systems whose S2 mean NDVI stays below 0.45.
    warm_m = max(range(5, 11), key=lambda m: clim.get(m, 0.0))
    cool_m = max([11, 12, 1, 2, 3, 4], key=lambda m: clim.get(m, 0.0))
    for m in (warm_m, cool_m):
        if clim.get(m, 0.0) >= fallow_thresh and m not in peaks:
            peaks.append(m)

    raw_seasons: list[dict[str, Any]] = []
    for peak in peaks:
        run = _expand_from_peak(peak, clim, floor=fallow_thresh)
        if not run:
            continue
        raw_seasons.append(
            {
                "months": run,
                "peak_month": peak,
                "peak_ndvi": clim.get(peak, 0.0),
                "mean_ndvi": float(np.mean([clim[m] for m in run if m in clim])),
                "label": None,
            }
        )
    # Deduplicate heavily overlapping runs (keep stronger)
    raw_seasons.sort(key=lambda s: s["mean_ndvi"], reverse=True)
    seasons: list[dict[str, Any]] = []
    for s in raw_seasons:
        overlap = False
        for kept in seasons:
            if len(set(s["months"]) & set(kept["months"])) >= 3:
                overlap = True
                break
        if not overlap:
            seasons.append(s)
        if len(seasons) >= 2:
            break

    warm = [s for s in seasons if 5 <= s["peak_month"] <= 10]
    cool = [s for s in seasons if s["peak_month"] >= 11 or s["peak_month"] <= 4]
    # If only one expanded run but both halves have green, force dual season
    if (not warm or not cool) and clim.get(warm_m, 0.0) >= fallow_thresh and clim.get(
        cool_m, 0.0
    ) >= fallow_thresh:
        warm = [
            {
                "months": _expand_from_peak(warm_m, clim, floor=fallow_thresh),
                "peak_month": warm_m,
                "peak_ndvi": clim.get(warm_m, 0.0),
                "mean_ndvi": clim.get(warm_m, 0.0),
                "label": None,
            }
        ]
        cool = [
            {
                "months": _expand_from_peak(cool_m, clim, floor=fallow_thresh),
                "peak_month": cool_m,
                "peak_ndvi": clim.get(cool_m, 0.0),
                "mean_ndvi": clim.get(cool_m, 0.0),
                "label": None,
            }
        ]
        seasons = warm + cool

    if len(warm) >= 1 and len(cool) >= 1:
        # Dual cropping: snap to canonical windows
        w, c = warm[0], cool[0]
        w["label"] = "kharif"
        w["months"] = list(KHARIF_MONTHS)
        w["mean_ndvi"] = float(np.mean([clim[m] for m in w["months"] if m in clim]))
        c["label"] = "rabi"
        c["months"] = list(RABI_MONTHS)
        c["mean_ndvi"] = float(np.mean([clim[m] for m in c["months"] if m in clim]))
        seasons = [w, c]
        # Inter-season trough: months not in either season with NDVI < fallow_thresh
        occupied = set(KHARIF_MONTHS) | set(RABI_MONTHS)
        # Prefer May–Jun gap (after rabi, before kharif)
        gap = [m for m in (5, 6) if clim.get(m, 1.0) < fallow_thresh or m not in occupied]
        # Also any other true trough outside seasons
        troughs = [
            m
            for m in range(1, 13)
            if m not in occupied and clim.get(m, 1.0) < fallow_thresh
        ]
        fallow_months = sorted(set(gap) | set(troughs)) or [5, 6]
    elif len(seasons) == 1:
        pm = seasons[0]["peak_month"]
        seasons[0]["label"] = "summer" if 4 <= pm <= 9 else "winter"
        fallow_months = sorted(
            m for m in range(1, 13) if clim.get(m, 1.0) < fallow_thresh
        )
        if not fallow_months:
            vals = np.array([clim.get(m, 0.0) for m in range(1, 13)])
            thr = float(np.quantile(vals, 0.25))
            fallow_months = [m for m in range(1, 13) if clim.get(m, 0.0) <= thr]
    else:
        for s in seasons:
            pm = s["peak_month"]
            s["label"] = "summer" if 4 <= pm <= 9 else "winter"
        fallow_months = sorted(
            m for m in range(1, 13) if clim.get(m, 1.0) < fallow_thresh
        )
        if not fallow_months and clim:
            vals = np.array([clim.get(m, 0.0) for m in range(1, 13)])
            thr = float(np.quantile(vals, 0.25))
            fallow_months = [m for m in range(1, 13) if clim.get(m, 0.0) <= thr]

    detail = (
        f"Seasons detected from {source_label}: "
        + ", ".join(
            f"{s['label']} {months_label(s['months'])} (peak {s['peak_ndvi']:.2f})"
            for s in seasons
        )
    )
    if fallow_months:
        detail += f"; fallow {months_label(fallow_months)}"

    return {
        "seasons": seasons,
        "fallow_months": fallow_months,
        "climatology": clim,
        "source": source_label,
        "detail": detail,
        "n_seasons": len(seasons),
        "green_thresh": green_thresh,
        "fallow_thresh": fallow_thresh,
    }


def map_crops_to_seasons(
    rotation: list[str],
    phenology: dict[str, Any],
) -> dict[str, Any]:
    """Assign each cash/forage crop to a detected season (or crops.json fallback)."""
    seasons = phenology.get("seasons") or []
    mapping: dict[str, dict[str, Any]] = {}
    for cid in rotation:
        c = crop_by_id(cid)
        if c["type"] == "cover":
            continue
        preferred = set(active_months(cid))
        best = None
        best_ov = -1
        for s in seasons:
            ov = len(preferred & set(s["months"]))
            label = s.get("label") or ""
            bonus = 0
            if c["season"] == "warm" and label in {"kharif", "summer"}:
                bonus = 2
            if c["season"] == "cool" and label in {"rabi", "winter"}:
                bonus = 2
            # Explicit rice → kharif, winter wheat → rabi
            if cid == "rice" and label == "kharif":
                bonus += 3
            if "wheat" in cid and "spring" not in cid and label == "rabi":
                bonus += 3
            score = ov + bonus
            if score > best_ov:
                best_ov = score
                best = s
        if best is not None and best_ov > 0:
            mapping[cid] = {
                "season_label": best["label"],
                "months": list(best["months"]),
                "source": "ndvi_phenology",
            }
        else:
            plant, harvest = plant_harvest_months(c)
            _ = (plant, harvest)
            mapping[cid] = {
                "season_label": "fallback",
                "months": sorted(preferred),
                "source": "crops.json",
            }
    return mapping


def bare_from_phenology(
    phenology: dict[str, Any],
    rotation: list[str],
    ndvi: pd.Series,
    *,
    freq: float = 0.6,
) -> dict[str, Any]:
    """Primary fallow = phenology troughs; fallback = crops.json calendar gaps."""
    from fieldshift.engine.calendar import fallow_months_from_rotation

    ph_fallow = list(phenology.get("fallow_months") or [])
    calendar = fallow_months_from_rotation(rotation)
    source = phenology.get("source") or "NDVI"

    confirmed = []
    rows = []
    n_years = 0
    if not ndvi.empty and ph_fallow:
        for m in ph_fallow:
            vals = ndvi[ndvi.index.month == m]
            if vals.empty:
                continue
            by_year = vals.groupby(vals.index.year).median()
            n_years = max(n_years, int(len(by_year)))
            bare_years = int((by_year < FALLOW_THRESH).sum())
            share = float((by_year < FALLOW_THRESH).mean())
            rows.append(
                {
                    "month": m,
                    "years_bare": bare_years,
                    "n_years": int(len(by_year)),
                    "years_bare_frac": share,
                }
            )
            if share >= freq:
                confirmed.append(m)

    used_phenology = bool(ph_fallow)
    if confirmed:
        months = confirmed
        yrs = min(r["years_bare"] for r in rows if r["month"] in confirmed)
        detail = (
            f"{months_label(months)} bare in {yrs} of {n_years} years "
            f"({source})"
        )
        ndvi_confirmed = confirmed
        ndvi_ok = True
    elif ph_fallow:
        months = ph_fallow
        detail = (
            f"Phenology fallow {months_label(ph_fallow)} "
            f"(NDVI < {FALLOW_THRESH} not confirmed in ≥{int(freq * 100)}% of years)"
        )
        ndvi_confirmed = []
        ndvi_ok = False
    else:
        months = calendar
        detail = f"Rotation fallow {months_label(calendar)} (crops.json fallback)"
        ndvi_confirmed = []
        ndvi_ok = False
        used_phenology = False

    return {
        "months": months,
        "calendar_fallow": calendar,
        "phenology_fallow": ph_fallow,
        "ndvi_confirmed": ndvi_confirmed,
        "ndvi_confirmed_ok": ndvi_ok,
        "rows": rows,
        "detail": detail,
        "ndvi_threshold": FALLOW_THRESH,
        "source": source if used_phenology else "crops.json",
        "evidence_line": (
            f"Seasons detected from {source}"
            if used_phenology
            else "Fallow from crops.json calendar (NDVI phenology unavailable)"
        ),
    }
