#!/usr/bin/env python3
"""Extract + cache tidy/daily for demo fields; print ET0/WB and strategy cards."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from fieldshift.data.extract import run_extract  # noqa: E402
from fieldshift.data.harmonize import climatology_from_tidy  # noqa: E402
from fieldshift.engine.generate import generate_strategies  # noqa: E402
from fieldshift.models import StrategyRequest  # noqa: E402

DEMOS = {
    "iowa": {
        "rotation": ["maize", "soybean"],
        "water_access": "rainfed",
        "size_ha": 16.0,
    },
    "uk": {
        "rotation": ["winter_wheat"],
        "water_access": "rainfed",
        "size_ha": 25.0,
    },
    "punjab": {
        "rotation": ["rice", "winter_wheat"],
        "water_access": "irrigated",
        "size_ha": 12.0,
    },
}


def _centroid(field: dict) -> tuple[float, float]:
    ring = field["polygon"]["coordinates"][0]
    lons = [p[0] for p in ring[:-1]]
    lats = [p[1] for p in ring[:-1]]
    return sum(lats) / len(lats), sum(lons) / len(lons)


def main() -> int:
    fixture = REPO / "tests" / "fixtures"
    cache = REPO / "fieldshift" / "cache"
    fixture.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)

    fields = {
        f["id"]: f
        for f in json.loads((REPO / "mock" / "demo_fields.json").read_text())
    }

    for name, cfg in DEMOS.items():
        print(f"\n######## {name.upper()} ########")
        field = fields[name]
        lat, lon = _centroid(field)
        tidy, clim, meta = run_extract(
            lat,
            lon,
            cfg["size_ha"],
            polygon=field["polygon"],
        )
        daily = meta.pop("daily")
        tidy.to_parquet(fixture / f"{name}_tidy.parquet")
        daily.to_parquet(fixture / f"{name}_daily.parquet")
        tidy.to_parquet(cache / f"demo_{name}_tidy.parquet")
        daily.to_parquet(cache / f"demo_{name}_daily.parquet")
        slim = {k: v for k, v in meta.items() if k != "variable_coverage"}
        (cache / f"demo_{name}_meta.json").write_text(
            json.dumps(slim, indent=2, default=str)
        )

        print(f"window={meta['start']}→{meta['end']} et0_method={meta.get('et0_method')}")
        print(f"elapsed_s={meta['elapsed_s']:.1f}")

        clim = climatology_from_tidy(tidy)
        print("\n--- monthly climatology: ET0 + water balance + rain + NDVI ---")
        rows = []
        for m in range(1, 13):
            means: dict[str, float | None] = {}
            for var in (
                "et0_mm",
                "rain_best_mm",
                "water_balance_mm",
                "ndvi_s2",
                "era5_pet_mm",
            ):
                sub = clim[(clim["calendar_month"] == m) & (clim["variable"] == var)]
                means[var] = (
                    None if sub.empty else round(float(sub["mean"].iloc[0]), 2)
                )
            rows.append({"month": m, **means})
        table = pd.DataFrame(rows)
        print(table.to_string(index=False))
        print(
            f"annual et0≈{table['et0_mm'].sum():.0f}  rain≈{table['rain_best_mm'].sum():.0f}  "
            f"wb≈{table['water_balance_mm'].sum():.0f}"
        )

        req = StrategyRequest(
            current_rotation=cfg["rotation"],
            water_access=cfg["water_access"],  # type: ignore[arg-type]
        )
        result = generate_strategies(name, tidy, req, daily=daily)
        print(f"\n--- strategy cards ({len(result.strategies)}) ---")
        for card in result.strategies:
            d = card.model_dump()
            sc = {k: round(v, 3) for k, v in d["scores"].items()}
            print(f"\n{d['name']} [{d['id']}] conf={d['confidence']}")
            print(f"  scores: {sc}")
            print(f"  delta_total: {d['delta_vs_current'].get('total')}")
            for e in d["evidence"][:3]:
                print(f"  evidence: {e['text']} (source: {e['source']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
