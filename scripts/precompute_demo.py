#!/usr/bin/env python3
"""Precompute demo field caches for Streamlit (Phase 4).

For Iowa, Kansas, Punjab:
  extract → features → anomalies → default strategies
  write fieldshift/cache/demo_{id}.json
  download Sentinel-2 NDVI + RGB timelapse GIFs

Usage::

    python scripts/precompute_demo.py
    python scripts/precompute_demo.py --skip-extract   # reuse existing tidy/daily
    python scripts/precompute_demo.py --skip-gif
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from fieldshift.cache import CACHE_DIR, write_json  # noqa: E402
from fieldshift.conditions_builder import (  # noqa: E402
    build_field_conditions,
    coverage_payload,
)
from fieldshift.data.extract import run_extract  # noqa: E402
from fieldshift.data.timelapse import download_s2_gif  # noqa: E402
from fieldshift.engine.anomalies import detect_anomalies  # noqa: E402
from fieldshift.engine.features import compute_features  # noqa: E402
from fieldshift.engine.generate import generate_strategies  # noqa: E402
from fieldshift.geo import polygon_centroid  # noqa: E402
from fieldshift.models import StrategyRequest  # noqa: E402

DEMOS = {
    "iowa": {
        "rotation": ["maize", "soybean"],
        "water_access": "rainfed",
        "size_ha": 16.0,
    },
    "kansas": {
        "rotation": ["winter_wheat"],
        "water_access": "rainfed",
        "size_ha": 20.0,
    },
    "punjab": {
        "rotation": ["rice", "winter_wheat"],
        "water_access": "irrigated",
        "size_ha": 40.0,
    },
}


def _load_fields() -> dict[str, dict]:
    raw = json.loads((REPO / "mock" / "demo_fields.json").read_text())
    return {f["id"]: f for f in raw}


def _gif_window(meta: dict) -> tuple[str, str]:
    """Use the last ~12 months of the analysis window for manageable GIFs."""
    import pandas as pd

    end = str(meta.get("end") or "2025-09-01")[:10]
    end_ts = pd.Timestamp(end)
    start_ts = end_ts - pd.DateOffset(months=11)
    return start_ts.strftime("%Y-%m-01"), end_ts.strftime("%Y-%m-01")


def precompute_one(
    field_id: str,
    field: dict,
    cfg: dict,
    *,
    skip_extract: bool = False,
    skip_gif: bool = False,
) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    polygon = field["polygon"]
    lat, lon = polygon_centroid(polygon)
    tidy_path = CACHE_DIR / f"demo_{field_id}_tidy.parquet"
    daily_path = CACHE_DIR / f"demo_{field_id}_daily.parquet"
    fixture_tidy = REPO / "tests" / "fixtures" / f"{field_id}_tidy.parquet"
    fixture_daily = REPO / "tests" / "fixtures" / f"{field_id}_daily.parquet"

    import pandas as pd

    meta: dict = {}
    meta_path = CACHE_DIR / f"demo_{field_id}_meta.json"
    if skip_extract:
        if not tidy_path.exists() and fixture_tidy.exists():
            tidy_path.write_bytes(fixture_tidy.read_bytes())
            daily_path.write_bytes(fixture_daily.read_bytes())
        if tidy_path.exists() and daily_path.exists():
            print(f"  reusing tidy/daily for {field_id}")
            tidy = pd.read_parquet(tidy_path)
            daily = pd.read_parquet(daily_path)
            if meta_path.exists():
                meta = json.loads(meta_path.read_text())
        else:
            skip_extract = False
    if not skip_extract:
        print(f"  extracting EE+POWER for {field_id} @ ({lat:.4f}, {lon:.4f}) …")
        tidy, _clim, meta = run_extract(
            lat, lon, float(cfg["size_ha"]), polygon=polygon
        )
        daily = meta.pop("daily")
        tidy.to_parquet(tidy_path)
        daily.to_parquet(daily_path)
        # keep fixtures in sync for tests
        fixture_tidy.parent.mkdir(parents=True, exist_ok=True)
        tidy.to_parquet(fixture_tidy)
        daily.to_parquet(fixture_daily)
        slim = {k: v for k, v in meta.items() if k != "variable_coverage"}
        meta_path.write_text(json.dumps(slim, indent=2, default=str))
        print(f"  extract done in {meta.get('elapsed_s', 0):.1f}s")

    rotation = list(cfg["rotation"])
    feats = compute_features(tidy, daily, current_rotation=rotation)
    anomalies = detect_anomalies(feats)
    req = StrategyRequest(
        current_rotation=rotation,
        water_access=cfg["water_access"],  # type: ignore[arg-type]
    )
    strategies = generate_strategies(
        field_id, tidy, req, daily=daily, features=feats
    )

    ndvi_gif = CACHE_DIR / f"demo_{field_id}_ndvi.gif"
    rgb_gif = CACHE_DIR / f"demo_{field_id}_rgb.gif"
    if not skip_gif:
        g_start, g_end = _gif_window(meta) if meta else ("2025-09-01", "2026-08-01")
        # Prefer meta dates from tidy if needed
        if not meta.get("end"):
            months = tidy[tidy["variable"] == "ndvi_s2"]["month"].dropna()
            if not months.empty:
                g_end = str(months.max()) + "-01"
                import pandas as pd

                g_start = (
                    pd.Timestamp(g_end) - pd.DateOffset(months=11)
                ).strftime("%Y-%m-01")
        print(f"  downloading NDVI GIF {g_start}→{g_end} …")
        try:
            ndvi_gif = download_s2_gif(
                polygon,
                g_start,
                g_end,
                mode="ndvi",
                field_id=f"demo_{field_id}",
                out_name=f"demo_{field_id}_ndvi.gif",
                tidy=tidy,
            )
            print("  RGB GIF …")
            rgb_gif = download_s2_gif(
                polygon,
                g_start,
                g_end,
                mode="rgb",
                field_id=f"demo_{field_id}",
                out_name=f"demo_{field_id}_rgb.gif",
                tidy=tidy,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  GIF download failed: {exc}")
    else:
        print("  skipping GIF download")

    conditions = build_field_conditions(
        field_id=field_id,
        name=field["name"],
        country=field["country"],
        climate_label=field["climate_label"],
        polygon=polygon,
        tidy=tidy,
        feats=feats,
        timelapse_url=str(ndvi_gif.name) if ndvi_gif.exists() else None,
    )

    cov = coverage_payload(feats)
    # Overall data_through for UI chips
    data_through = {}
    for row in cov.get("per_variable") or []:
        if row.get("variable") and row.get("data_through"):
            data_through[row["variable"]] = row["data_through"]

    payload = {
        "using_real_data": True,
        "conditions": conditions.model_dump(),
        "features_summary": conditions.features.model_dump(),
        "coverage": cov,
        "data_through": data_through,
        "cross_checks": conditions.cross_checks,
        "anomalies": {
            "n_growing": anomalies.get("n_growing"),
            "n_off_season": anomalies.get("n_off_season"),
            "uncertainty": anomalies.get("uncertainty"),
            "vulnerable_seasons": anomalies.get("vulnerable_seasons"),
        },
        "default_request": req.model_dump(mode="json"),
        "default_strategies": strategies.model_dump(mode="json"),
        "timelapse": {
            "ndvi": ndvi_gif.name if ndvi_gif.exists() else None,
            "rgb": rgb_gif.name if rgb_gif.exists() else None,
        },
        "extract_meta": {
            "start": meta.get("start"),
            "end": meta.get("end"),
            "grace_start": meta.get("grace_start"),
            "grace_end": meta.get("grace_end"),
            "et0_method": meta.get("et0_method"),
            "elapsed_s": meta.get("elapsed_s"),
        },
    }
    out = write_json(f"demo_{field_id}.json", payload)
    print(f"  wrote {out}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Reuse existing demo_*_tidy/daily parquet if present",
    )
    parser.add_argument("--skip-gif", action="store_true", help="Skip GIF download")
    parser.add_argument(
        "--only",
        choices=list(DEMOS),
        action="append",
        help="Only precompute these field ids (repeatable)",
    )
    args = parser.parse_args()
    fields = _load_fields()
    ids = args.only or list(DEMOS)
    for field_id in ids:
        print(f"\n######## {field_id.upper()} ########")
        if field_id not in fields or field_id not in DEMOS:
            print(f"  skip unknown id {field_id}")
            continue
        precompute_one(
            field_id,
            fields[field_id],
            DEMOS[field_id],
            skip_extract=args.skip_extract,
            skip_gif=args.skip_gif,
        )
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
