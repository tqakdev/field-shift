"""Harmonize multi-source field extractions onto a common field × month table.

Why "field × month"? Datasets in §4 span ~10 m (Sentinel-2) to ~3° mascons (GRACE).
The only unit that can hold all of them without false precision is the mean (or median)
over the farmer's polygon for each calendar month. Temporal alignment is month-start
``YYYY-MM``. Spatial alignment is the field geometry itself.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# variable → (unit, source label)
VARIABLE_META: dict[str, tuple[str, str]] = {
    "ndvi_s2": ("1", "Sentinel-2 NDVI"),
    "ndvi_landsat": ("1", "Landsat 8/9 NDVI"),
    "ndvi_modis": ("1", "MODIS MOD13Q1 NDVI"),
    "sm_surface": ("m3/m3", "SMAP L4 sm_surface"),
    "sm_rootzone": ("m3/m3", "SMAP L4 sm_rootzone"),
    "rain_mm": ("mm/month", "GPM IMERG V07 monthly"),
    "era5_precip_mm": ("mm/month", "ERA5-Land total_precipitation_sum"),
    "era5_evap_mm": ("mm/month", "ERA5-Land total_evaporation_sum"),
    "era5_pet_mm": ("mm/month", "ERA5-Land potential_evaporation_sum"),
    "era5_t2m_c": ("deg_C", "ERA5-Land temperature_2m"),
    "era5_soil_water": ("m3/m3", "ERA5-Land volumetric_soil_water_layer_1"),
    "grace_lwe_cm": ("cm", "GRACE/FO Mascon CRI lwe_thickness"),
    "elevation_m": ("m", "SRTM"),
    "slope_pct": ("percent", "SRTM slope"),
    "slope_deg": ("deg", "SRTM slope"),
    "power_t2m_c": ("deg_C", "NASA POWER T2M"),
    "power_t2m_max_c": ("deg_C", "NASA POWER T2M_MAX"),
    "power_t2m_min_c": ("deg_C", "NASA POWER T2M_MIN"),
    "power_rain_mm": ("mm/month", "NASA POWER PRECTOTCORR"),
    "power_rh2m_pct": ("percent", "NASA POWER RH2M"),
    "power_srad": ("MJ/m2/day", "NASA POWER ALLSKY_SFC_SW_DWN"),
    "water_balance_mm": ("mm/month", "IMERG rain − ERA5 PET"),
}


def power_monthly_to_tidy(monthly: pd.DataFrame) -> pd.DataFrame:
    """Convert POWER monthly wide table to tidy rows."""
    if monthly.empty:
        return pd.DataFrame(columns=["month", "variable", "value", "unit", "source", "n_obs"])
    mapping = {
        "T2M": "power_t2m_c",
        "T2M_MAX": "power_t2m_max_c",
        "T2M_MIN": "power_t2m_min_c",
        "PRECTOTCORR": "power_rain_mm",
        "RH2M": "power_rh2m_pct",
        "ALLSKY_SFC_SW_DWN": "power_srad",
    }
    rows: list[dict[str, Any]] = []
    for period, row in monthly.iterrows():
        month = str(period)
        for col, var in mapping.items():
            if col not in monthly.columns:
                continue
            unit, source = VARIABLE_META[var]
            val = row[col]
            rows.append(
                {
                    "month": month,
                    "variable": var,
                    "value": float(val) if pd.notna(val) else np.nan,
                    "unit": unit,
                    "source": source,
                    "n_obs": 1 if pd.notna(val) else 0,
                }
            )
    return pd.DataFrame(rows)


def ee_partial_to_tidy(partial: pd.DataFrame) -> pd.DataFrame:
    """Attach unit/source/n_obs to a partial EE table (month, variable, value)."""
    if partial is None or partial.empty:
        return pd.DataFrame(columns=["month", "variable", "value", "unit", "source", "n_obs"])
    rows: list[dict[str, Any]] = []
    for _, row in partial.iterrows():
        var = str(row["variable"])
        if var.endswith("_n_obs"):
            continue
        unit, source = VARIABLE_META.get(var, ("unknown", var))
        val = row["value"]
        rows.append(
            {
                "month": str(row["month"]),
                "variable": var,
                "value": float(val) if pd.notna(val) else np.nan,
                "unit": unit,
                "source": source,
                "n_obs": 0 if pd.isna(val) else 1,
            }
        )
    return pd.DataFrame(rows)


def add_water_balance(tidy: pd.DataFrame) -> pd.DataFrame:
    """Add water_balance_mm = IMERG rain − |ERA5 PET| per month when both exist."""
    if tidy.empty:
        return tidy
    rain = tidy[tidy["variable"] == "rain_mm"][["month", "value"]].rename(
        columns={"value": "rain"}
    )
    pet = tidy[tidy["variable"] == "era5_pet_mm"][["month", "value"]].rename(
        columns={"value": "pet"}
    )
    merged = rain.merge(pet, on="month", how="inner")
    if merged.empty:
        return tidy
    # ERA5 PET is often negative (atmospheric demand); use magnitude for deficit math
    merged["value"] = merged["rain"] - merged["pet"].abs()
    unit, source = VARIABLE_META["water_balance_mm"]
    extra = pd.DataFrame(
        {
            "month": merged["month"],
            "variable": "water_balance_mm",
            "value": merged["value"],
            "unit": unit,
            "source": source,
            "n_obs": 1,
        }
    )
    return pd.concat([tidy, extra], ignore_index=True)


def harmonize(
    ee_tables: dict[str, pd.DataFrame],
    power_monthly: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build tidy field×month table + climatology (mean/std by calendar month).

    Parameters
    ----------
    ee_tables:
        Output of ``extract_ee_field`` (ignores ``_window`` key).
    power_monthly:
        Optional POWER monthly wide DataFrame.

    Returns
    -------
    tidy, climatology
        ``tidy`` columns: month, variable, value, unit, source, n_obs.
        ``climatology`` columns: calendar_month (1–12), variable, mean, std, n.
    """
    parts = [
        ee_partial_to_tidy(df)
        for key, df in ee_tables.items()
        if key != "_window" and isinstance(df, pd.DataFrame)
    ]
    if power_monthly is not None:
        parts.append(power_monthly_to_tidy(power_monthly))
    tidy = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(
        columns=["month", "variable", "value", "unit", "source", "n_obs"]
    )
    tidy = add_water_balance(tidy)

    # Climatology: only real YYYY-MM months
    clim_src = tidy[tidy["month"].str.match(r"^\d{4}-\d{2}$", na=False)].copy()
    if clim_src.empty:
        climatology = pd.DataFrame(
            columns=["calendar_month", "variable", "mean", "std", "n"]
        )
        return tidy, climatology

    clim_src["calendar_month"] = clim_src["month"].str[5:7].astype(int)
    climatology = (
        clim_src.groupby(["calendar_month", "variable"], as_index=False)
        .agg(mean=("value", "mean"), std=("value", "std"), n=("value", "count"))
    )
    return tidy, climatology
