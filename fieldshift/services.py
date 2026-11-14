"""Public package interface called by Streamlit."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from fieldshift.cache import CACHE_DIR, read_json
from fieldshift.conditions_builder import build_field_conditions
from fieldshift.config import is_demo_mode
from fieldshift.engine.crops import load_crops
from fieldshift.engine.features import compute_features
from fieldshift.engine.generate import generate_strategies as engine_generate
from fieldshift.geo import polygon_area_ha, polygon_centroid
from fieldshift.models import (
    AnalyzeRequest,
    CropSummary,
    DataSourceMeta,
    DemoField,
    FieldConditions,
    StrategyRequest,
    StrategyResult,
    UsModuleResponse,
    ValidationResponse,
)

_DEMO_DEFAULTS = {
    "iowa": {"rotation": ["maize", "soybean"], "water_access": "rainfed"},
    "kansas": {"rotation": ["winter_wheat"], "water_access": "rainfed"},
    "punjab": {"rotation": ["rice", "winter_wheat"], "water_access": "irrigated"},
}


def using_mock_data() -> bool:
    """True when UI should show the MOCK DATA banner (no real demo cache)."""
    return not (CACHE_DIR / "demo_iowa.json").exists()


def _demo_cache(field_id: str) -> dict[str, Any] | None:
    raw = read_json(f"demo_{field_id}.json", from_mock=False)
    return raw if isinstance(raw, dict) else None


def list_demo_fields() -> list[DemoField]:
    """Return demo field metadata (prefer committed demo cache polygons)."""
    raw = read_json("demo_fields.json", from_mock=True) or []
    fields = [DemoField.model_validate(item) for item in raw]
    # Prefer polygon from precomputed cache when present
    out: list[DemoField] = []
    for f in fields:
        cached = _demo_cache(f.id)
        if cached and cached.get("conditions", {}).get("polygon"):
            cond = cached["conditions"]
            out.append(
                DemoField(
                    id=f.id,
                    name=cond.get("name", f.name),
                    country=cond.get("country", f.country),
                    climate_label=cond.get("climate_label", f.climate_label),
                    polygon=cond["polygon"],
                )
            )
        else:
            out.append(f)
    return out


def load_demo_conditions(field_id: str) -> FieldConditions:
    """Load FieldConditions for a demo field from committed cache (or mock)."""
    cached = _demo_cache(field_id)
    if cached and cached.get("conditions"):
        return FieldConditions.model_validate(cached["conditions"])
    raw = read_json(f"conditions_{field_id}.json", from_mock=True)
    if raw is None:
        raise FileNotFoundError(f"No conditions for field_id={field_id}")
    return FieldConditions.model_validate(raw)


def _load_demo_tables(field_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    tidy_p = CACHE_DIR / f"demo_{field_id}_tidy.parquet"
    daily_p = CACHE_DIR / f"demo_{field_id}_daily.parquet"
    # fixtures fallback for tests
    if not tidy_p.exists():
        fixtures = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
        tidy_p = fixtures / f"{field_id}_tidy.parquet"
        daily_p = fixtures / f"{field_id}_daily.parquet"
    if not tidy_p.exists() or not daily_p.exists():
        raise FileNotFoundError(
            f"No tidy/daily cache for {field_id} — run scripts/precompute_demo.py"
        )
    return pd.read_parquet(tidy_p), pd.read_parquet(daily_p)


def analyze_field(polygon: dict[str, Any], name: str | None = None) -> FieldConditions:
    """Analyze a drawn field (live EE + POWER). Validates 1–5000 ha."""
    _ = AnalyzeRequest(polygon=polygon, name=name)
    if is_demo_mode():
        raise RuntimeError(
            "Live analysis unavailable — Earth Engine credentials not configured (demo mode)."
        )
    area = polygon_area_ha(polygon)
    if area < 1.0 or area > 5000.0:
        raise ValueError(
            f"Polygon area is {area:.1f} ha — please draw a field between 1 and 5000 ha."
        )
    from fieldshift.data.extract import run_extract

    lat, lon = polygon_centroid(polygon)
    tidy, _clim, meta = run_extract(lat, lon, max(area, 1.0), polygon=polygon)
    daily = meta.pop("daily")
    # Hash cache under fieldshift/cache/live_{hash}.parquet optional — skip for now
    rotation = ["maize", "soybean"]
    feats = compute_features(tidy, daily, current_rotation=rotation)
    # stash tables on a side cache for strategy re-score of custom fields
    field_id = "custom"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tidy.to_parquet(CACHE_DIR / "demo_custom_tidy.parquet")
    daily.to_parquet(CACHE_DIR / "demo_custom_daily.parquet")
    cond = build_field_conditions(
        field_id=field_id,
        name=name or "Your field",
        country="",
        climate_label=f"Live analysis · {area:.0f} ha",
        polygon=polygon,
        tidy=tidy,
        feats=feats,
    )
    # Also write a lightweight JSON so generate_strategies can find defaults
    write_payload = {
        "using_real_data": True,
        "conditions": cond.model_dump(),
        "default_request": {
            "current_rotation": rotation,
            "water_access": "rainfed",
        },
        "default_strategies": None,
        "coverage": {"per_variable": feats.get("data_coverage", {}).get("per_variable")},
        "data_through": {},
        "cross_checks": cond.cross_checks,
        "timelapse": {"ndvi": None, "rgb": None},
        "extract_meta": {
            "start": meta.get("start"),
            "end": meta.get("end"),
            "elapsed_s": meta.get("elapsed_s"),
        },
    }
    from fieldshift.cache import write_json

    write_json("demo_custom.json", write_payload)
    return cond


def get_timelapse(field_id: str, index: str = "ndvi") -> dict[str, Any]:
    """Return static GIF path for demo fields; live EE URL not used for demos."""
    cached = _demo_cache(field_id)
    mode = "rgb" if index == "rgb" else "ndvi"
    fname = None
    if cached and cached.get("timelapse"):
        fname = cached["timelapse"].get(mode)
    if not fname:
        fname = f"demo_{field_id}_{mode}.gif"
    path = CACHE_DIR / fname
    if path.exists() and path.stat().st_size > 0:
        return {
            "path": str(path),
            "url": None,
            "cached_static": True,
            "field_id": field_id,
            "index": mode,
            "message": None,
        }
    return {
        "path": None,
        "url": None,
        "cached_static": False,
        "field_id": field_id,
        "index": mode,
        "message": "Timelapse GIF not found — run scripts/precompute_demo.py",
    }


def list_crops() -> list[CropSummary]:
    """Crop catalogue for rotation dropdowns (engine + mock extras)."""
    by_id: dict[str, CropSummary] = {}
    for c in load_crops():
        try:
            by_id[c["id"]] = CropSummary(
                id=c["id"],
                name=c["name"],
                type=c["type"],
                family=c["family"],
                season=c["season"],
            )
        except Exception:
            continue
    for item in read_json("crops.json", from_mock=True) or []:
        try:
            cs = CropSummary.model_validate(item)
            by_id.setdefault(cs.id, cs)
        except Exception:
            continue
    return list(by_id.values())


def list_sources() -> list[DataSourceMeta]:
    """Dataset catalogue for How it works."""
    raw = read_json("sources.json", from_mock=True) or []
    return [DataSourceMeta.model_validate(item) for item in raw]


def generate_strategies(
    field_id_or_conditions: str | FieldConditions,
    request: StrategyRequest | None = None,
) -> StrategyResult:
    """Score strategies from cached tidy/features — never calls EE/POWER."""
    if isinstance(field_id_or_conditions, FieldConditions):
        field_id = field_id_or_conditions.field_id
    else:
        field_id = field_id_or_conditions

    defaults = _DEMO_DEFAULTS.get(
        field_id, {"rotation": ["maize", "soybean"], "water_access": "rainfed"}
    )
    cached = _demo_cache(field_id)
    if request is None:
        if cached and cached.get("default_request"):
            request = StrategyRequest.model_validate(cached["default_request"])
        else:
            request = StrategyRequest(
                current_rotation=list(defaults["rotation"]),
                water_access=defaults["water_access"],  # type: ignore[arg-type]
            )

    # Fast path: unchanged defaults → return precomputed cards
    if (
        cached
        and cached.get("default_strategies")
        and cached.get("default_request")
        and request.model_dump(mode="json") == cached["default_request"]
    ):
        return StrategyResult.model_validate(cached["default_strategies"])

    try:
        tidy, daily = _load_demo_tables(field_id)
    except FileNotFoundError:
        # Legacy mock fallback
        raw = read_json(f"strategies_{field_id}.json", from_mock=True)
        if raw is None:
            raw = read_json("strategies_iowa.json", from_mock=True)
        if raw is None:
            raise
        return StrategyResult.model_validate(raw)

    return engine_generate(field_id, tidy, request, daily=daily)


def get_us_module(field_id: str) -> UsModuleResponse:
    """US enhancement payload — empty until Phase 7."""
    _ = field_id
    return UsModuleResponse(
        errors=["US module not available until Phase 7"],
    )


def get_validation(field_id: str) -> ValidationResponse:
    """Cross-check validation — empty until Phase 7 (may embed IMERG/POWER r)."""
    cached = _demo_cache(field_id)
    if cached and cached.get("cross_checks"):
        return ValidationResponse(
            cross_checks=cached["cross_checks"],
            errors=[],
        )
    return ValidationResponse(
        cross_checks=None,
        errors=["Validation cross-checks not available until Phase 7"],
    )


def demo_data_through(field_id: str, variable: str | None = None) -> str | None:
    """Return a data_through label from the demo cache."""
    cached = _demo_cache(field_id)
    if not cached:
        return None
    through = cached.get("data_through") or {}
    if variable and variable in through:
        return through[variable]
    for key in ("ndvi_s2", "rain_best_mm", "grace_lwe_cm"):
        if through.get(key):
            return through[key]
    return None
