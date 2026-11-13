"""Acceptance: Iowa cached features — cover beats current on soil/erosion; no millet/lentil."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fieldshift.engine.candidates import build_candidates
from fieldshift.engine.features import compute_features
from fieldshift.engine.generate import generate_strategies
from fieldshift.engine.scoring import score_strategy
from fieldshift.models import PriorityWeights, StrategyRequest

FIXTURE_DIR = Path(__file__).parent / "fixtures"
TIDY_PATH = FIXTURE_DIR / "iowa_tidy.parquet"
DAILY_PATH = FIXTURE_DIR / "iowa_daily.parquet"


@pytest.fixture(scope="module")
def iowa_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not TIDY_PATH.exists() or not DAILY_PATH.exists():
        pytest.skip("Iowa fixtures missing — run scripts/cache_demo_extracts.py")
    tidy = pd.read_parquet(TIDY_PATH)
    daily = pd.read_parquet(DAILY_PATH)
    return tidy, daily


def test_iowa_cover_beats_current_soil_erosion_income_near(iowa_data) -> None:
    tidy, daily = iowa_data
    feats = compute_features(tidy, daily, current_rotation=["maize", "soybean"])
    current = score_strategy(["maize", "soybean"], feats)
    cover = score_strategy(["maize", "soybean", "cereal_rye_cover"], feats)
    assert cover.soil_health > current.soil_health
    assert cover.erosion > current.erosion
    assert abs(cover.income - current.income) <= 0.05 + 1e-9


def test_iowa_no_water_wise_or_lentil(iowa_data) -> None:
    tidy, daily = iowa_data
    feats = compute_features(tidy, daily, current_rotation=["maize", "soybean"])
    cands = build_candidates(["maize", "soybean"], feats)
    ids = {c["id"] for c in cands}
    assert "water_wise_swap" not in ids
    assert "legume_swap" not in ids
    for c in cands:
        assert "lentil" not in c["sequence"]
        assert "millet" not in c["sequence"]
        assert "sorghum" not in c["sequence"]


def test_iowa_generate_cover_present(iowa_data) -> None:
    tidy, daily = iowa_data
    req = StrategyRequest(
        current_rotation=["maize", "soybean"],
        weights=PriorityWeights(),
    )
    result = generate_strategies("iowa", tidy, req, daily=daily)
    ids = [s.id for s in result.strategies]
    assert "current" in ids
    assert "current_plus_cover" in ids
