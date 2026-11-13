"""Harmonize multi-source field extractions onto a common field × month table.

Why "field × month"? Datasets in §4 span ~10 m (Sentinel-2) to ~3° mascons (GRACE).
The only unit that can hold all of them without false precision is the mean (or median)
over the farmer's polygon for each calendar month. Temporal alignment is month-start
``YYYY-MM``. Spatial alignment is the field geometry itself.

Each variable keeps its own available date range (IMERG GEE lag must not truncate S2/ERA5/
POWER). Climatology uses all valid years per variable. Recent rain prefers NASA POWER
PRECTOTCORR; IMERG is the long record + cross-check.
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
    "era5_pet_mm": ("mm/month", "ERA5-Land |PET| cross-check only"),
    "era5_t2m_c": ("deg_C", "ERA5-Land temperature_2m"),
    "era5_soil_water": ("m3/m3", "ERA5-Land volumetric_soil_water_layer_1"),
    "grace_lwe_cm": ("cm", "GRACE/FO Mascon CRI lwe_thickness"),
    "elevation_m": ("m", "SRTM"),
    "slope_pct": ("percent", "SRTM slope"),
    "slope_deg": ("deg", "SRTM slope"),
    "power_t2m_c": ("deg_C", "NASA POWER T2M (mean)"),
    "power_t2m_max_c": ("deg_C", "NASA POWER mean of daily T2M_MAX"),
    "power_t2m_min_c": ("deg_C", "NASA POWER mean of daily T2M_MIN"),
    "power_rain_mm": ("mm/month", "NASA POWER PRECTOTCORR"),
    "power_rh2m_pct": ("percent", "NASA POWER RH2M"),
    "power_srad": ("MJ/m2/day", "NASA POWER ALLSKY_SFC_SW_DWN"),
    "rain_best_mm": ("mm/month", "POWER recent / IMERG long record"),
    "et0_mm": ("mm/month", "FAO-56 ET0 from NASA POWER (positive)"),
    "water_balance_mm": ("mm/month", "rain_best − FAO-56 ET0"),
}

RECENT_RAIN_MONTHS = 24


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


def _month_period(month: str) -> pd.Period:
    return pd.Period(str(month)[:7], freq="M")


def build_rain_best(tidy: pd.DataFrame, recent_months: int = RECENT_RAIN_MONTHS) -> pd.DataFrame:
    """Prefer POWER rain in the last ``recent_months``; IMERG for the long record.

    For older months: IMERG if present else POWER.
    For recent months: POWER if present else IMERG.
    """
    cols = ["month", "variable", "value", "unit", "source", "n_obs"]
    if tidy.empty:
        return pd.DataFrame(columns=cols)

    imerg = tidy[tidy["variable"] == "rain_mm"][["month", "value"]].rename(
        columns={"value": "imerg"}
    )
    power = tidy[tidy["variable"] == "power_rain_mm"][["month", "value"]].rename(
        columns={"value": "power"}
    )
    if imerg.empty and power.empty:
        return pd.DataFrame(columns=cols)

    merged = imerg.merge(power, on="month", how="outer")
    if merged.empty:
        return pd.DataFrame(columns=cols)

    latest = max(_month_period(m) for m in merged["month"])
    cutoff = latest - (recent_months - 1)

    rows: list[dict[str, Any]] = []
    unit, _ = VARIABLE_META["rain_best_mm"]
    for _, row in merged.iterrows():
        m = str(row["month"])
        period = _month_period(m)
        imerg_v = row["imerg"] if "imerg" in row and pd.notna(row["imerg"]) else np.nan
        power_v = row["power"] if "power" in row and pd.notna(row["power"]) else np.nan
        if period >= cutoff:
            if pd.notna(power_v):
                val, src = float(power_v), "NASA POWER PRECTOTCORR (recent)"
            elif pd.notna(imerg_v):
                val, src = float(imerg_v), "GPM IMERG V07 (fallback)"
            else:
                val, src = np.nan, VARIABLE_META["rain_best_mm"][1]
        else:
            if pd.notna(imerg_v):
                val, src = float(imerg_v), "GPM IMERG V07 monthly"
            elif pd.notna(power_v):
                val, src = float(power_v), "NASA POWER PRECTOTCORR (gap fill)"
            else:
                val, src = np.nan, VARIABLE_META["rain_best_mm"][1]
        rows.append(
            {
                "month": m,
                "variable": "rain_best_mm",
                "value": val,
                "unit": unit,
                "source": src,
                "n_obs": 0 if pd.isna(val) else 1,
            }
        )
    return pd.DataFrame(rows)


def make_era5_pet_positive(tidy: pd.DataFrame) -> pd.DataFrame:
    """Store ERA5 PET as positive mm (cross-check only; not used for water balance)."""
    if tidy.empty:
        return tidy
    mask = tidy["variable"] == "era5_pet_mm"
    if not mask.any():
        return tidy
    out = tidy.copy()
    out.loc[mask, "value"] = out.loc[mask, "value"].abs()
    unit, source = VARIABLE_META["era5_pet_mm"]
    out.loc[mask, "unit"] = unit
    out.loc[mask, "source"] = source
    return out


def add_water_balance(tidy: pd.DataFrame) -> pd.DataFrame:
    """water_balance_mm = rain_best − FAO-56 ET0 (positive). Falls back to |ERA5 PET|."""
    if tidy.empty:
        return tidy
    rain = tidy[tidy["variable"] == "rain_best_mm"][["month", "value"]]
    if rain.empty:
        rain = tidy[tidy["variable"] == "rain_mm"][["month", "value"]]
    rain = rain.rename(columns={"value": "rain"})
    et0 = tidy[tidy["variable"] == "et0_mm"][["month", "value"]].rename(
        columns={"value": "et0"}
    )
    if et0.empty:
        et0 = tidy[tidy["variable"] == "era5_pet_mm"][["month", "value"]].rename(
            columns={"value": "et0"}
        )
        et0["et0"] = et0["et0"].abs()
        source = "rain_best − |ERA5 PET| (ET0 unavailable)"
    else:
        source = VARIABLE_META["water_balance_mm"][1]
    merged = rain.merge(et0, on="month", how="inner")
    if merged.empty:
        return tidy
    merged["value"] = merged["rain"] - merged["et0"].abs()
    unit, _ = VARIABLE_META["water_balance_mm"]
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


def imerg_power_correlation(tidy: pd.DataFrame) -> dict[str, Any]:
    """Pearson r of monthly IMERG vs POWER rain over overlapping valid months."""
    imerg = tidy[tidy["variable"] == "rain_mm"][["month", "value"]].rename(
        columns={"value": "imerg"}
    )
    power = tidy[tidy["variable"] == "power_rain_mm"][["month", "value"]].rename(
        columns={"value": "power"}
    )
    merged = imerg.merge(power, on="month", how="inner").dropna()
    if len(merged) < 3:
        return {"r": None, "n_months": int(len(merged)), "note": "insufficient overlap"}
    r = float(merged["imerg"].corr(merged["power"]))
    return {"r": r, "n_months": int(len(merged)), "note": "IMERG vs POWER monthly rain"}


def variable_coverage(tidy: pd.DataFrame) -> pd.DataFrame:
    """Per-variable start/end of valid data + data_through label for UI."""
    cols = [
        "variable",
        "unit",
        "source",
        "start",
        "end",
        "n_valid",
        "n_gaps",
        "data_through",
    ]
    if tidy.empty:
        return pd.DataFrame(columns=cols)
    work = tidy[tidy["month"].astype(str).str.match(r"^\d{4}-\d{2}$", na=False)].copy()
    rows: list[dict[str, Any]] = []
    for var, g in work.groupby("variable"):
        valid = g[g["value"].notna()]
        unit = str(g["unit"].iloc[0]) if len(g) else ""
        source = str(g["source"].iloc[0]) if len(g) else ""
        if valid.empty:
            rows.append(
                {
                    "variable": var,
                    "unit": unit,
                    "source": source,
                    "start": None,
                    "end": None,
                    "n_valid": 0,
                    "n_gaps": int(len(g)),
                    "data_through": "no data",
                }
            )
            continue
        start = str(valid["month"].min())
        end = str(valid["month"].max())
        # "data through October 2025"
        end_ts = pd.Timestamp(end + "-01")
        data_through = end_ts.strftime("%B %Y")
        rows.append(
            {
                "variable": var,
                "unit": unit,
                "source": source,
                "start": start,
                "end": end,
                "n_valid": int(len(valid)),
                "n_gaps": int(g["value"].isna().sum()),
                "data_through": data_through,
            }
        )
    return pd.DataFrame(rows).sort_values("variable").reset_index(drop=True)


def climatology_from_tidy(tidy: pd.DataFrame) -> pd.DataFrame:
    """Mean/std per calendar month using all available years per variable."""
    clim_src = tidy[tidy["month"].astype(str).str.match(r"^\d{4}-\d{2}$", na=False)].copy()
    clim_src = clim_src[clim_src["value"].notna()]
    if clim_src.empty:
        return pd.DataFrame(columns=["calendar_month", "variable", "mean", "std", "n", "unit"])
    clim_src["calendar_month"] = clim_src["month"].str[5:7].astype(int)
    clim = (
        clim_src.groupby(["calendar_month", "variable"], as_index=False)
        .agg(mean=("value", "mean"), std=("value", "std"), n=("value", "count"))
    )
    unit_map = (
        clim_src.groupby("variable")["unit"].first().to_dict() if "unit" in clim_src.columns else {}
    )
    clim["unit"] = clim["variable"].map(unit_map)
    return clim


def harmonize(
    ee_tables: dict[str, pd.DataFrame],
    power_monthly: pd.DataFrame | None = None,
    *,
    et0_monthly: pd.Series | None = None,
    et0_method: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Build tidy field×month table, climatology, and coverage metadata.

    Parameters
    ----------
    et0_monthly:
        FAO-56 monthly ET0 (mm/month, positive) from ``fieldshift.data.et0``.
    et0_method:
        ``hargreaves_samani`` or ``penman_monteith``.
    """
    from fieldshift.data.et0 import et0_tidy_rows

    parts = [
        ee_partial_to_tidy(df)
        for key, df in ee_tables.items()
        if key != "_window" and isinstance(df, pd.DataFrame)
    ]
    if power_monthly is not None:
        parts.append(power_monthly_to_tidy(power_monthly))
    tidy = (
        pd.concat(parts, ignore_index=True)
        if parts
        else pd.DataFrame(columns=["month", "variable", "value", "unit", "source", "n_obs"])
    )
    tidy = make_era5_pet_positive(tidy)
    rain_best = build_rain_best(tidy)
    if not rain_best.empty:
        tidy = pd.concat([tidy, rain_best], ignore_index=True)
    if et0_monthly is not None and not et0_monthly.empty:
        et_rows = et0_tidy_rows(et0_monthly, et0_method or "hargreaves_samani")
        tidy = pd.concat([tidy, pd.DataFrame(et_rows)], ignore_index=True)
    tidy = add_water_balance(tidy)

    corr = imerg_power_correlation(tidy)
    coverage = variable_coverage(tidy)
    climatology = climatology_from_tidy(tidy)
    meta: dict[str, Any] = {
        "variable_coverage": coverage.to_dict(orient="records"),
        "imerg_power_corr": corr,
        "recent_rain_months": RECENT_RAIN_MONTHS,
        "recent_rain_primary": "NASA POWER PRECTOTCORR",
        "long_rain_primary": "GPM IMERG V07",
        "et0_method": et0_method,
        "et0_note": (
            "Primary PET is FAO-56 ET0 from POWER; ERA5-Land PET is cross-check only."
        ),
    }
    return tidy, climatology, meta


# Plausible ranges for sanity checks (Iowa / temperate cropland)
PLAUSIBLE_RANGES: dict[str, tuple[float, float]] = {
    "ndvi_s2": (-0.2, 1.0),
    "ndvi_modis": (-0.2, 1.0),
    "ndvi_landsat": (-0.2, 1.0),
    "sm_surface": (0.0, 0.6),
    "sm_rootzone": (0.0, 0.6),
    "rain_mm": (0.0, 400.0),
    "rain_best_mm": (0.0, 400.0),
    "power_rain_mm": (0.0, 400.0),
    "power_t2m_c": (-40.0, 50.0),
    "power_t2m_max_c": (-40.0, 50.0),
    "power_t2m_min_c": (-40.0, 50.0),
    "era5_t2m_c": (-40.0, 50.0),
    "et0_mm": (0.0, 300.0),
    "era5_pet_mm": (0.0, 400.0),
    "water_balance_mm": (-400.0, 400.0),
}


def climatology_sanity_table(
    climatology: pd.DataFrame,
    *,
    variables: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Wide 12-month climatology means + flags for values outside plausible ranges."""
    wanted = variables or [
        "ndvi_s2",
        "ndvi_modis",
        "sm_surface",
        "sm_rootzone",
        "rain_best_mm",
        "et0_mm",
        "era5_pet_mm",
        "power_t2m_c",
        "power_t2m_max_c",
        "power_t2m_min_c",
        "water_balance_mm",
    ]
    # Friendly column labels for mean-of-daily extremes
    label_map = {
        "power_t2m_max_c": "mean_daily_tmax_c",
        "power_t2m_min_c": "mean_daily_tmin_c",
        "power_t2m_c": "mean_daily_t2m_c",
        "et0_mm": "et0_fao56_mm",
        "era5_pet_mm": "era5_pet_crosscheck_mm",
    }
    flags: list[str] = []
    if climatology.empty:
        return pd.DataFrame(), flags

    rows: dict[int, dict[str, Any]] = {m: {"month": m} for m in range(1, 13)}
    for var in wanted:
        sub = climatology[climatology["variable"] == var]
        unit = ""
        if not sub.empty and "unit" in sub.columns:
            unit = str(sub["unit"].iloc[0])
        label = label_map.get(var, var)
        col = f"{label}" + (f" [{unit}]" if unit else "")
        for m in range(1, 13):
            cell = sub[sub["calendar_month"] == m]
            if cell.empty or pd.isna(cell["mean"].iloc[0]):
                rows[m][col] = np.nan
                continue
            val = float(cell["mean"].iloc[0])
            rows[m][col] = round(val, 3)
            if var in PLAUSIBLE_RANGES:
                lo, hi = PLAUSIBLE_RANGES[var]
                if val < lo or val > hi:
                    flags.append(f"FLAG {var} month={m}: {val:.3f} outside [{lo}, {hi}]")

    table = pd.DataFrame([rows[m] for m in range(1, 13)])
    # Annual rain check
    rain_cols = [c for c in table.columns if c.startswith("rain_best_mm")]
    if rain_cols:
        annual = float(table[rain_cols[0]].sum(skipna=True))
        if annual < 800 or annual > 1000:
            flags.append(
                f"NOTE annual rain_best_mm sum≈{annual:.0f} mm "
                f"(Iowa expected ~800–1000 mm; check source mix)"
            )
        else:
            flags.append(f"OK annual rain_best_mm sum≈{annual:.0f} mm (Iowa ~800–1000)")
    return table, flags
