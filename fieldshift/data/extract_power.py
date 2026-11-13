"""NASA POWER daily point extraction → daily DataFrame + monthly aggregates.

Parameters (community=AG): T2M, T2M_MAX, T2M_MIN, PRECTOTCORR, RH2M, ALLSKY_SFC_SW_DWN.
Fill value −999 → NaN. Timeouts and retries on HTTP.
"""

from __future__ import annotations

from typing import Any

import httpx
import pandas as pd

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
# WS2M enables FAO-56 Penman–Monteith when present; otherwise Hargreaves–Samani.
POWER_PARAMS = "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,ALLSKY_SFC_SW_DWN,WS2M"
FILL = -999.0
DEFAULT_TIMEOUT_S = 60.0
MAX_RETRIES = 3


def _to_nan(value: Any) -> float:
    """Convert POWER fill (−999) and non-numeric values to NaN."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float("nan")
    if v == FILL:
        return float("nan")
    return v


def parse_power_payload(payload: dict[str, Any]) -> pd.DataFrame:
    """Parse a POWER JSON payload into a daily DataFrame (index = date).

    Parameters
    ----------
    payload:
        Decoded JSON from the POWER API.

    Returns
    -------
    pd.DataFrame
        Columns are parameter names; index is ``datetime64[ns]`` (UTC midnight).
        Units: temperature °C, PRECTOTCORR mm/day, RH2M %, ALLSKY_SFC_SW_DWN MJ/m²/day
        (POWER AG community conventions).
    """
    params = payload.get("properties", {}).get("parameter", {})
    if not params:
        return pd.DataFrame()

    frames: dict[str, pd.Series] = {}
    for name, series in params.items():
        dates = pd.to_datetime(list(series.keys()), format="%Y%m%d", utc=True)
        values = [_to_nan(v) for v in series.values()]
        frames[name] = pd.Series(values, index=dates, name=name)

    df = pd.concat(frames.values(), axis=1).sort_index()
    df.index.name = "date"
    return df


def monthly_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily POWER series to calendar-month values.

    - PRECTOTCORR: sum (mm/month)
    - T2M: mean of daily means (°C)
    - T2M_MAX: mean of daily maxima (°C) — not the monthly extreme
    - T2M_MIN: mean of daily minima (°C) — frost still uses daily T2M_MIN
    - RH2M: mean (%)
    - ALLSKY_SFC_SW_DWN: mean (MJ/m²/day)
    - WS2M: mean (m/s) when present

    Returns
    -------
    pd.DataFrame
        Index is period ``YYYY-MM`` (PeriodIndex month).
    """
    if daily.empty:
        return pd.DataFrame()

    # Normalize to timezone-naive for period conversion
    idx = daily.index.tz_convert(None) if daily.index.tz is not None else daily.index
    work = daily.copy()
    work.index = idx

    aggs: dict[str, str] = {}
    if "PRECTOTCORR" in work.columns:
        aggs["PRECTOTCORR"] = "sum"
    if "T2M" in work.columns:
        aggs["T2M"] = "mean"
    if "T2M_MAX" in work.columns:
        aggs["T2M_MAX"] = "mean"
    if "T2M_MIN" in work.columns:
        aggs["T2M_MIN"] = "mean"
    if "RH2M" in work.columns:
        aggs["RH2M"] = "mean"
    if "ALLSKY_SFC_SW_DWN" in work.columns:
        aggs["ALLSKY_SFC_SW_DWN"] = "mean"
    if "WS2M" in work.columns:
        aggs["WS2M"] = "mean"

    monthly = work.resample("MS").agg(aggs)
    monthly.index = monthly.index.to_period("M")
    monthly.index.name = "month"
    return monthly


def fetch_power_daily(
    lat: float,
    lon: float,
    start: str,
    end: str,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_retries: int = MAX_RETRIES,
) -> pd.DataFrame:
    """Fetch NASA POWER daily point data and return a cleaned daily DataFrame.

    Parameters
    ----------
    lat, lon:
        WGS84 coordinates (degrees).
    start, end:
        Inclusive dates as ``YYYYMMDD``.
    timeout_s:
        Per-request HTTP timeout (seconds).
    max_retries:
        Attempts on timeout / 5xx.

    Returns
    -------
    pd.DataFrame
        Daily series with −999 replaced by NaN.
    """
    params = {
        "parameters": POWER_PARAMS,
        "community": "AG",
        "latitude": lat,
        "longitude": lon,
        "start": start,
        "end": end,
        "format": "JSON",
    }
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=timeout_s) as client:
                resp = client.get(POWER_URL, params=params)
            if resp.status_code >= 500:
                raise httpx.HTTPStatusError(
                    f"POWER HTTP {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
            resp.raise_for_status()
            return parse_power_payload(resp.json())
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as exc:
            last_exc = exc
            if attempt + 1 >= max_retries:
                break
    assert last_exc is not None
    raise RuntimeError(f"NASA POWER request failed after {max_retries} attempts") from last_exc


def extract_power(
    lat: float,
    lon: float,
    start: str,
    end: str,
    **kwargs: Any,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return ``(daily, monthly)`` POWER tables for a point.

    See ``fetch_power_daily`` / ``monthly_from_daily`` for units.
    """
    daily = fetch_power_daily(lat, lon, start, end, **kwargs)
    monthly = monthly_from_daily(daily)
    return daily, monthly
