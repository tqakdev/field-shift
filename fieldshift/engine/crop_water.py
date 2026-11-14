"""Crop coefficients and seasonal irrigation-requirement helpers (FAO-style)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from fieldshift.engine.crops import crop_by_id

# Mid-season Kc (FAO-56 typical). Cover crops use a modest Kc.
CROP_KC: dict[str, float] = {
    "maize": 1.15,
    "soybean": 1.10,
    "winter_wheat": 1.15,
    "spring_wheat": 1.10,
    "barley": 1.10,
    "oats": 1.05,
    "sorghum": 1.00,
    "millet": 0.95,
    "alfalfa": 0.95,
    "red_clover": 0.90,
    "field_pea": 1.00,
    "lentil": 0.95,
    "canola": 1.05,
    "sunflower": 1.05,
    "cereal_rye_cover": 0.90,
    "hairy_vetch_cover": 0.85,
    "radish_cover": 0.80,
    "cotton": 1.15,
    "rice": 1.20,
    "mung_bean": 0.95,
    "pigeon_pea": 0.95,
}

# Extra flooded-culture / seepage demand beyond Kc×ET0 (mm/season).
FLOOD_PONDING_MM: dict[str, float] = {
    "rice": 450.0,
}

# Effective-rain fraction of rain_best (simple FAO approximation).
EFFECTIVE_RAIN_FRAC = 0.80


def crop_kc(crop_id: str) -> float:
    return float(CROP_KC.get(crop_id, 1.0))


def crop_demand_mm(
    crop_id: str,
    et0_monthly: pd.Series,
    season_months: list[int],
) -> float:
    """Σ (Kc × ET0) over season months (mean year if multi-year series)."""
    if et0_monthly.empty or not season_months:
        # fallback to crops.json midpoint water need
        c = crop_by_id(crop_id)
        return float(sum(c["water_need_mm"]) / 2.0)
    kc = crop_kc(crop_id)
    # climatological mean ET0 by calendar month
    by_m = et0_monthly.groupby(et0_monthly.index.month).mean()
    total = 0.0
    for m in season_months:
        if m in by_m.index:
            total += kc * float(by_m.loc[m])
    return total if total > 0 else float(sum(crop_by_id(crop_id)["water_need_mm"]) / 2.0)


def effective_rain_mm(rain_monthly: pd.Series, season_months: list[int]) -> float:
    if rain_monthly.empty or not season_months:
        return 0.0
    by_m = rain_monthly.groupby(rain_monthly.index.month).mean()
    total = sum(float(by_m.loc[m]) for m in season_months if m in by_m.index)
    return EFFECTIVE_RAIN_FRAC * total


def irrigation_requirement_mm(
    crop_id: str,
    features: dict[str, Any],
    season_months: list[int] | None = None,
) -> dict[str, float]:
    """IR = max(0, Kc·ET0_season + ponding − effective rain_season).

    Uses rain_best monthly series when present; otherwise prorates annual
    ``rain_annual_mm`` across the season (12ths). Rice includes flooded-culture
    ponding/seepage on top of Kc×ET0 so IR stays clearly above maize/pulses.
    """
    series = features.get("series", {})
    et0 = series.get("et0", pd.Series(dtype=float))
    rain = series.get("rain", pd.Series(dtype=float))
    mapping = features.get("crop_season_map") or {}
    months = season_months or (mapping.get(crop_id, {}) or {}).get("months")
    if not months:
        from fieldshift.engine.calendar import active_months

        months = sorted(active_months(crop_id))
    demand = crop_demand_mm(crop_id, et0, list(months))
    demand += float(FLOOD_PONDING_MM.get(crop_id, 0.0))
    if not rain.empty:
        rain_eff = effective_rain_mm(rain, list(months))
    else:
        annual = features.get("rain", {}).get("rain_annual_mm") or 0.0
        rain_eff = EFFECTIVE_RAIN_FRAC * float(annual) * (len(months) / 12.0)
    ir = max(0.0, demand - rain_eff)
    return {
        "demand_mm": demand,
        "rain_eff_mm": rain_eff,
        "irrigation_mm": ir,
        "kc": crop_kc(crop_id),
    }
