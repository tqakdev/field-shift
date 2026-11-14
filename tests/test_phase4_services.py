"""Phase 4 package interface — demo cache + season scoring without EE."""

from __future__ import annotations

from fieldshift.cache import CACHE_DIR
from fieldshift.geo import polygon_area_ha
from fieldshift.models import ScenarioParams, StrategyRequest
from fieldshift.services import (
    generate_strategies,
    get_timelapse,
    list_demo_fields,
    load_demo_conditions,
    using_mock_data,
)


def _ensure_iowa_json() -> None:
    if (CACHE_DIR / "demo_iowa.json").exists():
        return
    from scripts.precompute_demo import DEMOS, _load_fields, precompute_one

    fields = _load_fields()
    precompute_one(
        "iowa", fields["iowa"], DEMOS["iowa"], skip_extract=True, skip_gif=True
    )


def test_using_real_cache_hides_mock() -> None:
    _ensure_iowa_json()
    assert using_mock_data() is False
    cond = load_demo_conditions("iowa")
    assert cond.field_id == "iowa"
    assert len(cond.monthly_profile) == 12
    assert "MOCK" not in (cond.features.bare_months_label or "")


def test_generate_strategies_rescore_from_cache() -> None:
    _ensure_iowa_json()
    base = generate_strategies(
        "iowa",
        StrategyRequest(current_rotation=["maize", "soybean"], water_access="rainfed"),
    )
    dry = generate_strategies(
        "iowa",
        StrategyRequest(
            current_rotation=["maize", "soybean"],
            water_access="rainfed",
            scenario=ScenarioParams(rain_mult=0.7),
        ),
    )
    assert base.strategies
    assert dry.strategies
    assert base.strategies[0].evidence[0].source


def test_list_demo_fields_three() -> None:
    fields = list_demo_fields()
    ids = {f.id for f in fields}
    assert {"iowa", "kansas", "punjab"} <= ids


def test_polygon_area_bounds() -> None:
    poly = {
        "type": "Polygon",
        "coordinates": [
            [
                [-93.60, 42.00],
                [-93.59, 42.00],
                [-93.59, 42.01],
                [-93.60, 42.01],
                [-93.60, 42.00],
            ]
        ],
    }
    ha = polygon_area_ha(poly)
    assert 50 < ha < 200


def test_timelapse_metadata() -> None:
    _ensure_iowa_json()
    tl = get_timelapse("iowa", "ndvi")
    assert "path" in tl
    assert tl["field_id"] == "iowa"
