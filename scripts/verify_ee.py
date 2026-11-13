#!/usr/bin/env python3
"""Verify Earth Engine dataset IDs / bands / date ranges from PROJECT_SPEC §4 + POWER.

Fast checks: always filterBounds to the Iowa demo point before any getInfo.
Never aggregate over a global collection. Each dataset has a ~30 s timeout.
Prints catalogue facts only — never prints credentials.
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fieldshift.data.ee_client import init_ee  # noqa: E402

EE_DATASETS: list[tuple[str, str, str]] = [
    ("Sentinel-2 SR", "COPERNICUS/S2_SR_HARMONIZED", "collection"),
    ("Cloud Score+", "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED", "collection"),
    ("Landsat 8 C2 L2", "LANDSAT/LC08/C02/T1_L2", "collection"),
    ("Landsat 9 C2 L2", "LANDSAT/LC09/C02/T1_L2", "collection"),
    ("MODIS MOD13Q1", "MODIS/061/MOD13Q1", "collection"),
    ("SMAP L4", "NASA/SMAP/SPL4SMGP/008", "collection"),
    ("IMERG V07 monthly", "NASA/GPM_L3/IMERG_MONTHLY_V07", "collection"),
    ("ERA5-Land monthly", "ECMWF/ERA5_LAND/MONTHLY_AGGR", "collection"),
    ("SRTM", "USGS/SRTMGL1_003", "image"),
    ("GRACE Mascon CRI", "NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI", "collection"),
    ("VIIRS VNP13A1", "NASA/VIIRS/002/VNP13A1", "collection"),
    ("GLDAS-2.1 Noah", "NASA/GLDAS/V021/NOAH/G025/T3H", "collection"),
]

IOWA_LAT = 42.0
IOWA_LON = -93.6
DATASET_TIMEOUT_S = 30.0


def _iowa_point(ee: Any) -> Any:
    """Small Iowa AOI so filterBounds is meaningful (point + tiny buffer)."""
    return ee.Geometry.Point([IOWA_LON, IOWA_LAT]).buffer(500)


def _check_collection(ee: Any, ee_id: str) -> dict[str, Any]:
    """Bands + first/last date for a collection filtered to Iowa."""
    geom = _iowa_point(ee)
    col = ee.ImageCollection(ee_id).filterBounds(geom)
    first = ee.Image(col.sort("system:time_start").first())
    last = ee.Image(col.sort("system:time_start", False).first())
    # One combined getInfo to reduce round-trips
    info = ee.Dictionary(
        {
            "bands": first.bandNames(),
            "t0": first.date().format("YYYY-MM-dd"),
            "t1": last.date().format("YYYY-MM-dd"),
            "n_probe": col.limit(5).size(),
        }
    ).getInfo()
    return {
        "bands": list(info["bands"]),
        "t0": str(info["t0"]),
        "t1": str(info["t1"]),
        "n_probe": int(info["n_probe"]),
    }


def _check_image(ee: Any, ee_id: str) -> dict[str, Any]:
    """Bands for a static Image (SRTM)."""
    img = ee.Image(ee_id)
    bands = img.bandNames().getInfo()
    return {"bands": list(bands), "t0": None, "t1": None, "n_probe": 1}


def _run_with_timeout(fn: Any, timeout_s: float) -> tuple[Any | None, str | None]:
    """Run ``fn`` in a worker thread; return (result, error_label).

    On timeout, shut down without waiting so a stuck EE ``getInfo`` cannot block
    the rest of the script.
    """
    pool = ThreadPoolExecutor(max_workers=1)
    fut = pool.submit(fn)
    try:
        return fut.result(timeout=timeout_s), None
    except FuturesTimeout:
        return None, "TIMEOUT"
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def verify_ee_datasets() -> None:
    """Print ID, bands, date range, and elapsed seconds for each §4 EE dataset."""
    import ee

    print("=== Earth Engine dataset verification ===")
    print(f"UTC: {datetime.now(UTC).isoformat()}")
    print(f"AOI: Iowa point ({IOWA_LAT}N, {IOWA_LON}W), timeout={DATASET_TIMEOUT_S:.0f}s")

    for label, ee_id, kind in EE_DATASETS:
        print(f"\n--- {label} ---")
        print(f"ID: {ee_id}")
        t_start = time.perf_counter()

        def _job(k: str = kind, i: str = ee_id) -> dict[str, Any]:
            if k == "image":
                return _check_image(ee, i)
            return _check_collection(ee, i)

        result, err = _run_with_timeout(_job, DATASET_TIMEOUT_S)
        elapsed = time.perf_counter() - t_start
        print(f"elapsed_s: {elapsed:.2f}")

        if err == "TIMEOUT":
            print("TIMEOUT")
            continue
        if err:
            print(f"ERROR: {err}")
            continue
        assert result is not None
        print(f"bands ({len(result['bands'])}): {result['bands']}")
        if kind == "image":
            print("date_range: static DEM (no time dimension)")
        else:
            print(f"date_range: {result['t0']} → {result['t1']}")
            print(f"iowa_filter_probe: n={result['n_probe']}")


def verify_gedi_catalog_hint() -> None:
    """Try known GEDI gridded IDs (spec: search catalog; report what exists)."""
    import ee

    print("\n=== GEDI (catalog search candidates) ===")
    candidates = [
        "LARSE/GEDI/GEDI04_A_002_MONTHLY",
        "LARSE/GEDI/GEDI04_B_002",
    ]
    for ee_id in candidates:
        t_start = time.perf_counter()

        def _job(i: str = ee_id) -> dict[str, Any]:
            return _check_collection(ee, i)

        result, err = _run_with_timeout(_job, DATASET_TIMEOUT_S)
        elapsed = time.perf_counter() - t_start
        print(f"\nID: {ee_id}")
        print(f"elapsed_s: {elapsed:.2f}")
        if err == "TIMEOUT":
            print("TIMEOUT")
        elif err:
            print(f"NOT AVAILABLE or error: ({err})")
        else:
            assert result is not None
            print("FOUND")
            print(f"bands ({len(result['bands'])}): {result['bands']}")
            print(f"date_range: {result['t0']} → {result['t1']}")


def verify_power_iowa() -> None:
    """One NASA POWER daily point request for the Iowa demo coordinates."""
    print("\n=== NASA POWER (Iowa point) ===")
    print(f"lat={IOWA_LAT}, lon={IOWA_LON}")
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,ALLSKY_SFC_SW_DWN",
        "community": "AG",
        "latitude": IOWA_LAT,
        "longitude": IOWA_LON,
        "start": "20240101",
        "end": "20240107",
        "format": "JSON",
    }
    t_start = time.perf_counter()
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(url, params=params)
        data = resp.json()
        props = data.get("properties", {})
        param_block = props.get("parameter", {})
        print(f"elapsed_s: {time.perf_counter() - t_start:.2f}")
        print(f"HTTP {resp.status_code}")
        print(f"parameters_returned: {sorted(param_block.keys())}")
        t2m = param_block.get("T2M", {})
        sample_keys = list(t2m.keys())[:3]
        print(f"T2M_sample_dates: {sample_keys}")
        for k in sample_keys:
            v = t2m[k]
            print(f"  {k}: {v}{' (fill/-999 → treat as NaN)' if v == -999 else ''}")
    except Exception as exc:  # noqa: BLE001
        print(f"elapsed_s: {time.perf_counter() - t_start:.2f}")
        print(f"ERROR: {type(exc).__name__}: {exc}")


def main() -> int:
    status = init_ee(force=True)
    print("=== EE init status (no secrets) ===")
    print(
        f"configured={status.configured} "
        f"initialized={status.initialized} demo_mode={status.demo_mode}"
    )
    print(
        f"project_set={bool(status.project)} "
        f"service_account_set={status.service_account_set}"
    )
    ee_ok = status.initialized and not status.error
    if status.error:
        print(f"error={status.error}")
        print("Skipping Earth Engine dataset band/date checks until EE init succeeds.")
    else:
        verify_ee_datasets()
        verify_gedi_catalog_hint()

    verify_power_iowa()
    print("\n=== verify_ee.py done ===")
    return 0 if ee_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
