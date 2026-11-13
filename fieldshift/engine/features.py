"""Derive field-level climate/soil features from tidy monthly + POWER daily tables.

Pure Python — no Earth Engine / network.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from fieldshift.engine.phenology import (
    bare_from_phenology,
    detect_seasons_from_ndvi,
    map_crops_to_seasons,
)


def _series(tidy: pd.DataFrame, variable: str) -> pd.Series:
    sub = tidy[tidy["variable"] == variable][["month", "value"]].dropna()
    if sub.empty:
        return pd.Series(dtype=float)
    s = sub.set_index("month")["value"].astype(float)
    s.index = pd.PeriodIndex(s.index.astype(str), freq="M")
    return s.sort_index()


def _climatology_z(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    cal = series.index.month
    means = series.groupby(cal).transform("mean")
    stds = series.groupby(cal).transform("std").replace(0, np.nan)
    return (series - means) / stds


def frost_window(daily: pd.DataFrame) -> dict[str, Any]:
    """Average last spring / first autumn frost from daily T2M_MIN ≤ 0 °C."""
    if daily.empty or "T2M_MIN" not in daily.columns:
        return {
            "last_spring_doy": None,
            "first_autumn_doy": None,
            "frost_free_days": None,
        }
    work = daily.copy()
    idx = work.index.tz_convert(None) if work.index.tz is not None else work.index
    work.index = idx
    work["year"] = work.index.year
    work["doy"] = work.index.dayofyear
    springs, autumns = [], []
    for _year, g in work.groupby("year"):
        cold = g[g["T2M_MIN"] <= 0]
        if cold.empty:
            continue
        spring = cold[cold["doy"] <= 180]
        autumn = cold[cold["doy"] >= 180]
        if not spring.empty:
            springs.append(int(spring["doy"].max()))
        if not autumn.empty:
            autumns.append(int(autumn["doy"].min()))
    last_s = float(np.mean(springs)) if springs else None
    first_a = float(np.mean(autumns)) if autumns else None
    ffd = (first_a - last_s) if last_s is not None and first_a is not None else None
    return {
        "last_spring_doy": last_s,
        "first_autumn_doy": first_a,
        "frost_free_days": ffd,
        "n_years": len(set(work["year"])),
    }


def gdd_and_heat(daily: pd.DataFrame, base_c: float = 10.0) -> dict[str, Any]:
    """GDD from daily T2M; heat days from daily T2M_MAX > 35 °C."""
    if daily.empty or "T2M" not in daily.columns:
        return {"gdd_annual_mean": None, "heat_days_mean": None, "gdd_trend": None}
    work = daily.copy()
    idx = work.index.tz_convert(None) if work.index.tz is not None else work.index
    work.index = idx
    t = work["T2M"]
    gdd = (t - base_c).clip(lower=0)
    heat = (work["T2M_MAX"] > 35).astype(int) if "T2M_MAX" in work.columns else 0
    annual_gdd = gdd.groupby(work.index.year).sum()
    annual_heat = (
        heat.groupby(work.index.year).sum()
        if isinstance(heat, pd.Series)
        else pd.Series(dtype=float)
    )
    trend = None
    if len(annual_gdd) >= 3:
        x = np.arange(len(annual_gdd), dtype=float)
        trend = float(np.polyfit(x, annual_gdd.values.astype(float), 1)[0])
    return {
        "gdd_annual_mean": float(annual_gdd.mean()) if len(annual_gdd) else None,
        "heat_days_mean": float(annual_heat.mean()) if len(annual_heat) else None,
        "gdd_trend_per_year": trend,
        "years": [int(y) for y in annual_gdd.index],
    }


def rain_stats(rain: pd.Series) -> dict[str, Any]:
    if rain.empty:
        return {"rain_annual_mm": None, "rain_cv": None, "extreme_rain_months": []}
    annual = rain.groupby(rain.index.year).sum()
    cv = float(annual.std() / annual.mean()) if annual.mean() else None
    thr = float(rain.quantile(0.95)) if len(rain) else None
    extreme = (
        [str(p) for p in rain[rain >= thr].index.astype(str)] if thr is not None else []
    )
    return {
        "rain_annual_mm": float(annual.mean()),
        "rain_cv": cv,
        "extreme_rain_months": extreme[:24],
        "extreme_threshold_mm": thr,
    }


def water_balance_stats(wb: pd.Series) -> dict[str, Any]:
    if wb.empty:
        return {"annual_deficit_mm": None, "monthly_mean": {}}
    annual = wb.groupby(wb.index.year).sum()
    return {
        "annual_balance_mm": float(annual.mean()),
        "annual_deficit_mm": float(min(0.0, annual.mean())),
        "monthly_mean": {
            int(m): float(v) for m, v in wb.groupby(wb.index.month).mean().items()
        },
    }


def erosion_risk(slope_pct: float | None, extreme_n: int, bare_n: int) -> float:
    s = 0.0 if slope_pct is None else min(1.0, max(0.0, slope_pct / 15.0))
    e = min(1.0, extreme_n / 10.0)
    b = min(1.0, bare_n / 6.0)
    return float(0.4 * s + 0.3 * e + 0.3 * b)


def linear_trend_cm_per_yr(series: pd.Series) -> float | None:
    if len(series.dropna()) < 6:
        return None
    y = series.dropna().astype(float)
    x = np.arange(len(y), dtype=float)
    slope_per_step = float(np.polyfit(x, y.values, 1)[0])
    if isinstance(y.index, pd.PeriodIndex):
        return slope_per_step * 12.0
    return slope_per_step


def data_coverage(tidy: pd.DataFrame) -> dict[str, Any]:
    from fieldshift.data.harmonize import variable_coverage

    cov = variable_coverage(tidy)
    return {"per_variable": cov.to_dict(orient="records")}


def growing_season_mask(ndvi: pd.Series, t2m: pd.Series) -> dict[int, bool]:
    """Calendar month is growing-season if clim NDVI > 0.4 or mean T2M > 5 °C."""
    out: dict[int, bool] = {}
    for m in range(1, 13):
        ndvi_m = ndvi[ndvi.index.month == m]
        t_m = t2m[t2m.index.month == m] if not t2m.empty else pd.Series(dtype=float)
        ndvi_ok = float(ndvi_m.mean()) > 0.4 if len(ndvi_m) else False
        t_ok = float(t_m.mean()) > 5.0 if len(t_m) else False
        out[m] = bool(ndvi_ok or t_ok)
    return out


def compute_features(
    tidy: pd.DataFrame,
    daily: pd.DataFrame | None = None,
    *,
    static: dict[str, float] | None = None,
    current_rotation: list[str] | None = None,
) -> dict[str, Any]:
    """Build the feature dict consumed by candidates / scoring / anomalies."""
    daily = daily if daily is not None else pd.DataFrame()
    static = static or {}
    rotation = current_rotation or ["maize", "soybean"]

    ndvi_source = "Sentinel-2 NDVI"
    ndvi = _series(tidy, "ndvi_s2")
    if ndvi.empty:
        ndvi = _series(tidy, "ndvi_modis")
        ndvi_source = "MODIS NDVI"
    sm = _series(tidy, "sm_surface")
    rain = _series(tidy, "rain_best_mm")
    rain_source = "rain_best (POWER recent / IMERG long record)"
    if rain.empty:
        rain = _series(tidy, "rain_mm")
        rain_source = "IMERG rain_mm"
    wb = _series(tidy, "water_balance_mm")
    et0 = _series(tidy, "et0_mm")
    grace = _series(tidy, "grace_lwe_cm")
    # Mean of daily max/min (from POWER monthly aggregates), not monthly extremes
    t2m_mean = _series(tidy, "power_t2m_c")
    t2m_max_mean = _series(tidy, "power_t2m_max_c")
    t2m_min_mean = _series(tidy, "power_t2m_min_c")

    phenology = detect_seasons_from_ndvi(ndvi, source_label=ndvi_source)
    crop_season_map = map_crops_to_seasons(rotation, phenology)
    bare = bare_from_phenology(phenology, rotation, ndvi)
    frost = frost_window(daily)
    gdd = gdd_and_heat(daily)
    rain_s = rain_stats(rain)
    rain_s["source"] = rain_source
    rain_s["period"] = (
        f"{rain.index.min()} → {rain.index.max()}" if not rain.empty else None
    )
    wb_s = water_balance_stats(wb)

    gs = growing_season_mask(ndvi, t2m_mean)
    ndvi_z = _climatology_z(ndvi)
    sm_z = _climatology_z(sm)
    stress_growing: list[str] = []
    stress_offseason: list[str] = []
    for idx in ndvi_z.index:
        nz = ndvi_z.loc[idx]
        sz = sm_z.loc[idx] if idx in sm_z.index else np.nan
        hot = False
        if idx in t2m_max_mean.index and t2m_max_mean.loc[idx] > 35:
            hot = True
        if not (pd.notna(nz) and nz < -1 and ((pd.notna(sz) and sz < -1) or hot)):
            continue
        label = str(idx)
        if gs.get(int(idx.month), False):
            stress_growing.append(label)
        else:
            stress_offseason.append(label)

    slope = static.get("slope_pct", _static_from_tidy(tidy, "slope_pct"))
    elev = static.get("elevation_m", _static_from_tidy(tidy, "elevation_m"))
    erisk = erosion_risk(
        slope,
        len(rain_s.get("extreme_rain_months") or []),
        len(bare.get("months") or []),
    )

    data_gaps: list[str] = []
    if bare.get("phenology_fallow") and not bare.get("ndvi_confirmed_ok"):
        data_gaps.append(
            f"NDVI did not confirm phenology fallow "
            f"{bare.get('detail', '')}"
        )
    if bare.get("source") == "crops.json":
        data_gaps.append("Fallow window fell back to crops.json calendar")

    return {
        "bare_months": bare,
        "phenology": phenology,
        "crop_season_map": crop_season_map,
        "stress_months": {
            "growing_season": stress_growing,
            "off_season": stress_offseason,
            "n_growing": len(stress_growing),
            "n_off_season": len(stress_offseason),
        },
        "growing_season_months": [m for m, ok in gs.items() if ok],
        "frost_window": frost,
        "gdd": gdd,
        "rain": rain_s,
        "water_balance": wb_s,
        "et0_annual_mm": float(et0.groupby(et0.index.year).sum().mean())
        if not et0.empty
        else None,
        "slope_pct_mean": slope,
        "elevation_m": elev,
        "erosion_risk": erisk,
        "soil_moisture_trend": linear_trend_cm_per_yr(sm),
        "grace_trend_cm_per_yr": linear_trend_cm_per_yr(grace),
        "data_coverage": data_coverage(tidy),
        "feature_data_gaps": data_gaps,
        "current_rotation": rotation,
        "series": {
            "ndvi": ndvi,
            "sm_surface": sm,
            "rain": rain,
            "water_balance": wb,
            "et0": et0,
            "t2m_mean": t2m_mean,
            "t2m_max_mean_daily": t2m_max_mean,
            "t2m_min_mean_daily": t2m_min_mean,
        },
        "temp_labels": {
            "t2m": "mean of daily T2M (°C)",
            "tmax": "mean of daily T2M_MAX (°C) — not monthly extreme",
            "tmin": "mean of daily T2M_MIN (°C) — frost uses daily T2M_MIN",
        },
    }


def _static_from_tidy(tidy: pd.DataFrame, variable: str) -> float | None:
    sub = tidy[tidy["variable"] == variable]["value"].dropna()
    if sub.empty:
        return None
    return float(sub.iloc[0])
