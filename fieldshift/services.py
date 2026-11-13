"""Public package interface called by Streamlit (Phase 1: mock / stubs)."""

from __future__ import annotations

from typing import Any

from fieldshift.cache import read_json
from fieldshift.config import is_demo_mode
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


def list_demo_fields() -> list[DemoField]:
    """Return demo field metadata (from mock/ in Phase 1)."""
    raw = read_json("demo_fields.json", from_mock=True) or []
    return [DemoField.model_validate(item) for item in raw]


def load_demo_conditions(field_id: str) -> FieldConditions:
    """Load FieldConditions for a demo field (mock JSON in Phase 1)."""
    raw = read_json(f"conditions_{field_id}.json", from_mock=True)
    if raw is None:
        raise FileNotFoundError(f"No conditions mock for field_id={field_id}")
    return FieldConditions.model_validate(raw)


def analyze_field(polygon: dict[str, Any], name: str | None = None) -> FieldConditions:
    """Analyze a drawn field (live EE + POWER). Phase 1: not implemented."""
    _ = AnalyzeRequest(polygon=polygon, name=name)
    if is_demo_mode():
        raise RuntimeError(
            "Live analysis unavailable — Earth Engine credentials not configured (demo mode)."
        )
    raise RuntimeError("Live analysis is not wired until Phase 2–4.")


def get_timelapse(field_id: str, index: str = "ndvi") -> dict[str, Any]:
    """Return timelapse path/URL metadata. Phase 1: no GIF yet."""
    _ = index
    return {
        "path": None,
        "url": None,
        "cached_static": False,
        "field_id": field_id,
        "message": "Timelapse GIF will appear after demo precompute (Phase 4).",
    }


def list_crops() -> list[CropSummary]:
    """Crop catalogue for rotation dropdowns."""
    raw = read_json("crops.json", from_mock=True) or []
    return [CropSummary.model_validate(item) for item in raw]


def list_sources() -> list[DataSourceMeta]:
    """Dataset catalogue for How it works."""
    raw = read_json("sources.json", from_mock=True) or []
    return [DataSourceMeta.model_validate(item) for item in raw]


def generate_strategies(
    field_id_or_conditions: str | FieldConditions,
    request: StrategyRequest | None = None,
) -> StrategyResult:
    """Score strategies. Phase 1: return mock cards (no EE)."""
    _ = request
    if isinstance(field_id_or_conditions, FieldConditions):
        field_id = field_id_or_conditions.field_id
    else:
        field_id = field_id_or_conditions
    raw = read_json(f"strategies_{field_id}.json", from_mock=True)
    if raw is None:
        raw = read_json("strategies_iowa.json", from_mock=True)
    if raw is None:
        raise FileNotFoundError("No strategy mock JSON found")
    return StrategyResult.model_validate(raw)


def get_us_module(field_id: str) -> UsModuleResponse:
    """US enhancement payload — empty until Phase 7."""
    _ = field_id
    return UsModuleResponse(
        errors=["US module not available until Phase 7"],
    )


def get_validation(field_id: str) -> ValidationResponse:
    """Cross-check validation — empty until Phase 7."""
    _ = field_id
    return ValidationResponse(
        cross_checks=None,
        errors=["Validation cross-checks not available until Phase 7"],
    )


def using_mock_data() -> bool:
    """True when UI should show the MOCK DATA banner (Phase 1 uses mock/ only)."""
    from fieldshift.cache import CACHE_DIR

    return not (CACHE_DIR / "demo_iowa.json").exists()
