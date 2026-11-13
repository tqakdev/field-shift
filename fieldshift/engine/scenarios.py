"""What-if rain multiplier and temperature offset → adjusted features + re-score."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fieldshift.models import ScenarioParams


def apply_scenario(features: dict[str, Any], scenario: ScenarioParams) -> dict[str, Any]:
    """Return a shallow-adjusted feature dict (does not mutate the original).

    rain_mult scales rain_annual_mm and water-balance annual figures.
    temp_offset increases heat_days_mean (~4 days per °C) and shortens frost-free
    days (~5 days per °C) as a simple proxy.
    """
    out = {k: deepcopy(v) for k, v in features.items() if k != "series"}
    # Keep series for IR / phenology scoring; scale rain copy when needed.
    series = dict(features.get("series") or {})
    if scenario.rain_mult != 1.0 and "rain" in series and series["rain"] is not None:
        series = {**series, "rain": series["rain"] * scenario.rain_mult}
    out["series"] = series

    rain = dict(out.get("rain") or {})
    if rain.get("rain_annual_mm") is not None:
        rain["rain_annual_mm"] = float(rain["rain_annual_mm"]) * scenario.rain_mult
    out["rain"] = rain

    wb = dict(out.get("water_balance") or {})
    if wb.get("annual_balance_mm") is not None:
        wb["annual_balance_mm"] = float(wb["annual_balance_mm"]) * scenario.rain_mult
    if wb.get("annual_deficit_mm") is not None:
        wb["annual_deficit_mm"] = float(wb["annual_deficit_mm"]) * scenario.rain_mult
    out["water_balance"] = wb

    gdd = dict(out.get("gdd") or {})
    if gdd.get("heat_days_mean") is not None:
        gdd["heat_days_mean"] = float(gdd["heat_days_mean"]) + 4.0 * scenario.temp_offset
    out["gdd"] = gdd

    frost = dict(out.get("frost_window") or {})
    if frost.get("frost_free_days") is not None:
        frost["frost_free_days"] = max(
            0.0, float(frost["frost_free_days"]) - 5.0 * scenario.temp_offset
        )
    out["frost_window"] = frost
    return out
