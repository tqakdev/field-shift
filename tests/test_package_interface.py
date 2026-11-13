"""Phase 1 package interface + credential loading tests."""

from __future__ import annotations

from fieldshift.config import get_settings, is_demo_mode
from fieldshift.services import (
    generate_strategies,
    get_us_module,
    get_validation,
    list_crops,
    list_demo_fields,
    list_sources,
    load_demo_conditions,
)


def test_list_demo_fields() -> None:
    fields = list_demo_fields()
    assert len(fields) >= 2
    ids = {f.id for f in fields}
    assert "iowa" in ids


def test_load_demo_conditions_iowa() -> None:
    cond = load_demo_conditions("iowa")
    assert cond.field_id == "iowa"
    assert len(cond.monthly_profile) == 12


def test_crops_lentil_and_chickpea_separate() -> None:
    ids = {c.id for c in list_crops()}
    assert "lentil" in ids
    assert "chickpea" in ids


def test_generate_strategies_mock() -> None:
    result = generate_strategies("iowa")
    assert result.strategies
    assert result.strategies[0].evidence


def test_us_and_validation_graceful_empty() -> None:
    us = get_us_module("iowa")
    assert us.detected_rotation is None
    assert us.errors
    val = get_validation("iowa")
    assert val.cross_checks is None
    assert val.errors


def test_list_sources_nonempty() -> None:
    assert list_sources()


def test_settings_load_without_crash() -> None:
    settings = get_settings()
    assert isinstance(is_demo_mode(), bool)
    assert isinstance(settings.ee_configured, bool)
