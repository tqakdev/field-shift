"""FAO-56 reference evapotranspiration (ET0) from NASA POWER daily weather.

Primary method: **Hargreaves–Samani** using T2M_MAX, T2M_MIN and extraterrestrial
radiation Ra(latitude, day-of-year).

If daily ``WS2M`` (wind), ``RH2M``, and ``ALLSKY_SFC_SW_DWN`` (or equivalent) are
present, **FAO-56 Penman–Monteith** is used instead and ``method`` is recorded.

ET0 is always returned as a **positive** mm/day (or mm/month when aggregated).
ERA5-Land potential_evaporation remains a cross-check only (see harmonize).
"""

from __future__ import annotations

import math
from typing import Any, Literal

import numpy as np
import pandas as pd

GSC = 0.0820  # MJ m-2 min-1 solar constant
SIGMA = 4.903e-9  # MJ K-4 m-2 day-1 Stefan-Boltzmann
LAMBDA = 2.45  # MJ kg-1 latent heat → mm from MJ: / LAMBDA


def extraterrestrial_radiation_mm(lat_deg: float, doy: int | np.ndarray) -> np.ndarray:
    """FAO-56 Eq. 21–28: Ra in mm/day (equivalent evaporation)."""
    lat = math.radians(lat_deg)
    j = np.asarray(doy, dtype=float)
    dr = 1.0 + 0.033 * np.cos(2 * math.pi / 365.0 * j)
    delta = 0.409 * np.sin(2 * math.pi / 365.0 * j - 1.39)
    # sunset hour angle; clamp for polar day/night
    arg = np.clip(-np.tan(lat) * np.tan(delta), -1.0, 1.0)
    ws = np.arccos(arg)
    ra_mj = (
        24.0
        * 60.0
        / math.pi
        * GSC
        * dr
        * (ws * np.sin(lat) * np.sin(delta) + np.cos(lat) * np.cos(delta) * np.sin(ws))
    )
    return ra_mj / LAMBDA


def hargreaves_samani_et0_mm(
    tmin_c: float | np.ndarray,
    tmax_c: float | np.ndarray,
    lat_deg: float,
    doy: int | np.ndarray,
) -> np.ndarray:
    """FAO-56 Eq. 52 Hargreaves–Samani ET0 (mm/day), always ≥ 0.

    ET0 = 0.0023 * (Tmean + 17.8) * sqrt(Tmax − Tmin) * Ra
    """
    tmin = np.asarray(tmin_c, dtype=float)
    tmax = np.asarray(tmax_c, dtype=float)
    tmean = (tmin + tmax) / 2.0
    dtr = np.maximum(tmax - tmin, 0.0)
    ra = extraterrestrial_radiation_mm(lat_deg, doy)
    et0 = 0.0023 * (tmean + 17.8) * np.sqrt(dtr) * ra
    return np.maximum(et0, 0.0)


def penman_monteith_et0_mm(
    tmin_c: np.ndarray,
    tmax_c: np.ndarray,
    rh_pct: np.ndarray,
    wind_ms: np.ndarray,
    rs_mj: np.ndarray,
    lat_deg: float,
    doy: np.ndarray,
    elev_m: float = 100.0,
) -> np.ndarray:
    """FAO-56 Penman–Monteith (Eq. 6) simplified daily form, mm/day."""
    tmin = np.asarray(tmin_c, dtype=float)
    tmax = np.asarray(tmax_c, dtype=float)
    tmean = (tmin + tmax) / 2.0
    # saturation vapour pressure
    e0_max = 0.6108 * np.exp(17.27 * tmax / (tmax + 237.3))
    e0_min = 0.6108 * np.exp(17.27 * tmin / (tmin + 237.3))
    es = (e0_max + e0_min) / 2.0
    ea = es * np.clip(rh_pct, 0, 100) / 100.0
    # slope of vapour pressure curve
    delta = 4098.0 * (0.6108 * np.exp(17.27 * tmean / (tmean + 237.3))) / (tmean + 237.3) ** 2
    p = 101.3 * ((293.0 - 0.0065 * elev_m) / 293.0) ** 5.26
    gamma = 0.665e-3 * p
    ra_mm = extraterrestrial_radiation_mm(lat_deg, doy)
    ra_mj = ra_mm * LAMBDA
    rso = (0.75 + 2e-5 * elev_m) * ra_mj
    rs = np.asarray(rs_mj, dtype=float)
    rns = (1.0 - 0.23) * rs
    rnl = (
        SIGMA
        * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4)
        / 2.0
        * (0.34 - 0.14 * np.sqrt(np.maximum(ea, 0)))
        * (1.35 * np.clip(rs / np.maximum(rso, 1e-6), 0.0, 1.0) - 0.35)
    )
    rn = rns - rnl
    u2 = np.asarray(wind_ms, dtype=float)
    num = 0.408 * delta * rn + gamma * 900.0 / (tmean + 273.0) * u2 * (es - ea)
    den = delta + gamma * (1.0 + 0.34 * u2)
    et0 = num / den
    return np.maximum(et0, 0.0)


def daily_et0(
    daily: pd.DataFrame,
    lat_deg: float,
    *,
    elev_m: float = 100.0,
) -> tuple[pd.Series, Literal["hargreaves_samani", "penman_monteith"]]:
    """Compute daily ET0 (mm/day) Series indexed like ``daily``.

    Prefers Penman–Monteith when WS2M + RH2M + ALLSKY_SFC_SW_DWN are present;
    otherwise Hargreaves–Samani.
    """
    if daily.empty or "T2M_MAX" not in daily.columns or "T2M_MIN" not in daily.columns:
        return pd.Series(dtype=float), "hargreaves_samani"

    work = daily.copy()
    idx = work.index.tz_convert(None) if getattr(work.index, "tz", None) else work.index
    work.index = idx
    doy = work.index.dayofyear.to_numpy()

    has_pm = (
        "WS2M" in work.columns
        and "RH2M" in work.columns
        and "ALLSKY_SFC_SW_DWN" in work.columns
    )
    if has_pm and work[["WS2M", "RH2M", "ALLSKY_SFC_SW_DWN"]].notna().all(axis=None):
        # POWER ALLSKY_SFC_SW_DWN is MJ/m2/day in AG community
        et = penman_monteith_et0_mm(
            work["T2M_MIN"].to_numpy(),
            work["T2M_MAX"].to_numpy(),
            work["RH2M"].to_numpy(),
            work["WS2M"].to_numpy(),
            work["ALLSKY_SFC_SW_DWN"].to_numpy(),
            lat_deg,
            doy,
            elev_m=elev_m,
        )
        return pd.Series(et, index=work.index, name="et0_mm"), "penman_monteith"

    et = hargreaves_samani_et0_mm(
        work["T2M_MIN"].to_numpy(),
        work["T2M_MAX"].to_numpy(),
        lat_deg,
        doy,
    )
    return pd.Series(et, index=work.index, name="et0_mm"), "hargreaves_samani"


def monthly_et0_from_daily(et0_daily: pd.Series) -> pd.Series:
    """Sum daily ET0 to calendar-month totals (mm/month), PeriodIndex month."""
    if et0_daily.empty:
        return pd.Series(dtype=float)
    idx = et0_daily.index
    if getattr(idx, "tz", None) is not None:
        et0_daily = et0_daily.copy()
        et0_daily.index = idx.tz_convert(None)
    monthly = et0_daily.resample("MS").sum()
    monthly.index = monthly.index.to_period("M")
    monthly.name = "et0_mm"
    return monthly


def et0_tidy_rows(monthly: pd.Series, method: str) -> list[dict[str, Any]]:
    """Tidy rows for harmonize (positive ET0).

    Method is recorded by the caller in harmonize ``meta["et0_method"]``.
    """
    _ = method
    rows = []
    for period, val in monthly.items():
        rows.append(
            {
                "month": str(period),
                "variable": "et0_mm",
                "value": float(val) if pd.notna(val) else float("nan"),
                "unit": "mm/month",
                "source": "FAO-56 ET0 from NASA POWER (positive)",
                "n_obs": 1 if pd.notna(val) else 0,
            }
        )
    return rows
