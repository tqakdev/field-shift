"""Build FieldConditions + monthly profile from tidy tables / engine features."""

from __future__ import annotations

from typing import Any

import pandas as pd

from fieldshift.data.harmonize import climatology_from_tidy, imerg_power_correlation
from fieldshift.engine.calendar import months_label
from fieldshift.models import FieldConditions, FieldFeatures, MonthlySeriesPoint


def _clim_mean(clim: pd.DataFrame, month: int, variable: str) -> float | None:
    sub = clim[(clim["calendar_month"] == month) & (clim["variable"] == variable)]
    if sub.empty or pd.isna(sub["mean"].iloc[0]):
        return None
    return float(sub["mean"].iloc[0])


def monthly_profile_from_tidy(tidy: pd.DataFrame) -> list[MonthlySeriesPoint]:
    """12-month climatology profile for the conditions chart."""
    clim = climatology_from_tidy(tidy)
    out: list[MonthlySeriesPoint] = []
    for m in range(1, 13):
        out.append(
            MonthlySeriesPoint(
                month=m,
                ndvi=_clim_mean(clim, m, "ndvi_s2")
                or _clim_mean(clim, m, "ndvi_modis"),
                soil_moisture=_clim_mean(clim, m, "sm_surface"),
                rain_mm=_clim_mean(clim, m, "rain_best_mm")
                or _clim_mean(clim, m, "rain_mm"),
                water_balance_mm=_clim_mean(clim, m, "water_balance_mm"),
                temperature_c=_clim_mean(clim, m, "power_t2m_c"),
            )
        )
    return out


def field_features_summary(feats: dict[str, Any]) -> FieldFeatures:
    """Map engine feature dict → UI FieldFeatures."""
    bare = feats.get("bare_months") or {}
    stress = feats.get("stress_months") or {}
    frost = feats.get("frost_window") or {}
    rain = feats.get("rain") or {}
    gdd = feats.get("gdd") or {}
    wb = feats.get("water_balance") or {}
    bare_m = list(bare.get("months") or [])
    growing = list(stress.get("growing_season") or [])
    # calendar months from growing stress labels "YYYY-MM"
    stress_months: list[int] = []
    for label in growing:
        try:
            stress_months.append(int(str(label).split("-")[1]))
        except (IndexError, ValueError):
            continue
    stress_months = sorted(set(stress_months))

    last_s = frost.get("last_spring_doy")
    first_a = frost.get("first_autumn_doy")
    if last_s is not None and first_a is not None:
        frost_label = (
            f"Last spring frost ≈ DOY {last_s:.0f}; "
            f"first autumn frost ≈ DOY {first_a:.0f}"
        )
    else:
        frost_label = "Frost window not resolved from daily T2M_MIN"

    heat = gdd.get("heat_days_mean")
    heat_trend = (
        f"≈ {heat:.1f} heat days/year (Tmax > 35 °C)"
        if heat is not None
        else "Heat-day climatology unavailable"
    )
    cov = feats.get("data_coverage", {}).get("per_variable") or []
    through = next(
        (
            r.get("data_through")
            for r in cov
            if r.get("variable") == "ndvi_s2" and r.get("data_through")
        ),
        None,
    )
    coverage_note = (
        f"Multi-source monthly field means; NDVI data through {through}"
        if through
        else "Multi-source monthly field means (NASA / ESA / USGS)"
    )

    return FieldFeatures(
        bare_months=bare_m,
        bare_months_label=str(bare.get("detail") or months_label(bare_m)),
        stress_months=stress_months,
        stress_months_label=(
            f"Growing-season stress months: {months_label(stress_months)}"
            if stress_months
            else "No recurring growing-season stress months flagged"
        ),
        frost_window_label=frost_label,
        frost_free_days=frost.get("frost_free_days"),
        gdd_annual=gdd.get("gdd_annual_mean"),
        heat_days_trend=heat_trend,
        rain_annual_mm=rain.get("rain_annual_mm"),
        rain_cv=rain.get("rain_cv"),
        slope_pct_mean=feats.get("slope_pct_mean"),
        erosion_risk=feats.get("erosion_risk"),
        water_deficit_annual_mm=wb.get("annual_deficit_mm"),
        data_coverage_note=coverage_note,
    )


def build_field_conditions(
    *,
    field_id: str,
    name: str,
    country: str,
    climate_label: str,
    polygon: dict[str, Any],
    tidy: pd.DataFrame,
    feats: dict[str, Any],
    timelapse_url: str | None = None,
    sources_used: list[str] | None = None,
) -> FieldConditions:
    """Assemble the UI FieldConditions payload."""
    return FieldConditions(
        field_id=field_id,
        name=name,
        country=country,
        climate_label=climate_label,
        polygon=polygon,
        monthly_profile=monthly_profile_from_tidy(tidy),
        features=field_features_summary(feats),
        timelapse_url=timelapse_url,
        sources_used=sources_used
        or [
            "Sentinel-2 NDVI",
            "SMAP",
            "IMERG",
            "NASA POWER",
            "ERA5-Land",
            "GRACE/FO",
            "SRTM",
        ],
        us_module=None,
        cross_checks={"imerg_vs_power_rain": imerg_power_correlation(tidy)},
    )


def coverage_payload(feats: dict[str, Any]) -> dict[str, Any]:
    """Serializable coverage + grace detail for demo JSON."""
    return {
        "per_variable": feats.get("data_coverage", {}).get("per_variable") or [],
        "grace_trend": feats.get("grace_trend") or {},
        "phenology": {
            "detail": (feats.get("phenology") or {}).get("detail"),
            "pattern": (feats.get("phenology") or {}).get("pattern"),
            "fallow_months": (feats.get("phenology") or {}).get("fallow_months"),
            "n_seasons": (feats.get("phenology") or {}).get("n_seasons"),
        },
        "feature_data_gaps": feats.get("feature_data_gaps") or [],
    }
