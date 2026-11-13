"""CLI: extract + harmonize field monthly table for a point/size.

Usage::

    python -m fieldshift.data.extract --lat 42.0 --lon -93.6 --size-ha 60
"""

from __future__ import annotations

import argparse
import time
from typing import Any

import pandas as pd


def _power_dates(start: str, end: str) -> tuple[str, str]:
    """Convert YYYY-MM-01 window to POWER YYYYMMDD inclusive end-of-month."""
    start_d = start.replace("-", "")[:8]
    end_ts = pd.Timestamp(end[:10]) + pd.offsets.MonthEnd(0)
    return start_d, end_ts.strftime("%Y%m%d")


def run_extract(
    lat: float,
    lon: float,
    size_ha: float,
    *,
    start: str | None = None,
    end: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Extract EE + POWER, harmonize; return tidy, climatology, meta."""
    from fieldshift.data.extract_ee import extract_ee_field, polygon_from_point
    from fieldshift.data.extract_power import extract_power
    from fieldshift.data.harmonize import harmonize

    polygon = polygon_from_point(lat, lon, size_ha)
    t0 = time.perf_counter()
    ee_tables = extract_ee_field(polygon, start=start, end=end)
    window = ee_tables["_window"].iloc[0]
    w_start, w_end = str(window["start"]), str(window["end"])
    p_start, p_end = _power_dates(w_start, w_end)
    daily, monthly = extract_power(lat, lon, p_start, p_end)
    tidy, clim = harmonize(ee_tables, monthly)
    elapsed = time.perf_counter() - t0
    meta = {
        "lat": lat,
        "lon": lon,
        "size_ha": size_ha,
        "start": w_start,
        "end": w_end,
        "elapsed_s": elapsed,
        "power_daily_rows": len(daily),
        "power_monthly_rows": len(monthly),
    }
    return tidy, clim, meta


def summarize(tidy: pd.DataFrame) -> pd.DataFrame:
    """Per-variable row counts, date range, and gap count (NaN values)."""
    if tidy.empty:
        return pd.DataFrame(
            columns=["variable", "n_rows", "n_valid", "n_gaps", "month_min", "month_max"]
        )
    work = tidy[tidy["month"].str.match(r"^\d{4}-\d{2}$", na=False)].copy()
    rows = []
    for var, g in work.groupby("variable"):
        n_rows = len(g)
        n_valid = int(g["value"].notna().sum())
        rows.append(
            {
                "variable": var,
                "n_rows": n_rows,
                "n_valid": n_valid,
                "n_gaps": n_rows - n_valid,
                "month_min": g["month"].min(),
                "month_max": g["month"].max(),
            }
        )
    return pd.DataFrame(rows).sort_values("variable").reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Field Shift data extract (EE + POWER)")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--size-ha", type=float, default=60.0)
    parser.add_argument("--start", type=str, default=None, help="YYYY-MM-01 optional")
    parser.add_argument("--end", type=str, default=None, help="YYYY-MM-01 optional")
    args = parser.parse_args(argv)

    tidy, _clim, meta = run_extract(
        args.lat, args.lon, args.size_ha, start=args.start, end=args.end
    )
    summary = summarize(tidy)

    print("=== Field Shift extract ===")
    print(
        f"point=({meta['lat']}, {meta['lon']}) size_ha={meta['size_ha']} "
        f"window={meta['start']} → {meta['end']}"
    )
    print(f"elapsed_s={meta['elapsed_s']:.1f}")
    print(f"tidy_rows={len(tidy)} climatology built")
    print("\n--- summary (per variable) ---")
    print(summary.to_string(index=False))
    gaps = summary[summary["n_gaps"] > 0]
    if not gaps.empty:
        print("\n--- variables with gaps ---")
        print(gaps[["variable", "n_gaps", "n_rows"]].to_string(index=False))
    else:
        print("\n--- variables with gaps ---\n(none)")
    print("\n--- monthly table (first 24 rows) ---")
    show = tidy[tidy["month"].str.match(r"^\d{4}-\d{2}$", na=False)].head(24)
    print(show.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
