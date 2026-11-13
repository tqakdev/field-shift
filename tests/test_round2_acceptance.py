"""Phase 3 round 2 acceptance: Punjab phenology/water-wise, Kansas candidates, Iowa cover."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from fieldshift.engine.candidates import build_candidates
from fieldshift.engine.features import compute_features
from fieldshift.engine.generate import generate_strategies
from fieldshift.engine.scoring import score_strategy, score_water
from fieldshift.models import PriorityWeights, StrategyRequest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    tidy_p = FIXTURE_DIR / f"{name}_tidy.parquet"
    daily_p = FIXTURE_DIR / f"{name}_daily.parquet"
    if not tidy_p.exists() or not daily_p.exists():
        pytest.skip(f"{name} fixtures missing — run scripts/cache_demo_extracts.py")
    return pd.read_parquet(tidy_p), pd.read_parquet(daily_p)


def test_punjab_fallow_may_jun_and_rice_wheat_seasons() -> None:
    tidy, daily = _load("punjab")
    feats = compute_features(
        tidy, daily, current_rotation=["rice", "winter_wheat"]
    )
    ph = feats["phenology"]
    fallow = set(ph.get("fallow_months") or [])
    assert 5 in fallow and 6 in fallow
    assert fallow <= {4, 5, 6} or ({5, 6} <= fallow)
    labels = {s["label"] for s in ph["seasons"]}
    assert "kharif" in labels and "rabi" in labels
    mapping = feats["crop_season_map"]
    assert mapping["rice"]["season_label"] == "kharif"
    assert set(mapping["rice"]["months"]) == {6, 7, 8, 9, 10}
    assert mapping["winter_wheat"]["season_label"] == "rabi"
    assert "Seasons detected from" in (ph.get("detail") or "")


def test_punjab_water_wise_beats_current_on_water_and_total() -> None:
    tidy, daily = _load("punjab")
    weights = PriorityWeights()  # equal weights
    req = StrategyRequest(
        current_rotation=["rice", "winter_wheat"],
        water_access="irrigated",
        weights=weights,
    )
    result = generate_strategies("punjab", tidy, req, daily=daily)
    by_id = {s.id: s for s in result.strategies}
    assert "current" in by_id
    assert "water_wise_swap" in by_id
    ww = by_id["water_wise_swap"]
    cur = by_id["current"]
    assert "rice" not in [c.crop_id for c in ww.sequence]
    assert ww.scores.water > cur.scores.water
    assert ww.scores.total > cur.scores.total
    # Rice clearly worse water than maize/pulse on this field
    feats = compute_features(
        tidy, daily, current_rotation=["rice", "winter_wheat"]
    )
    rice_w = score_water(["rice", "winter_wheat"], feats, "irrigated")
    maize_w = score_water(["maize", "winter_wheat"], feats, "irrigated")
    pulse_w = score_water(["field_pea", "winter_wheat"], feats, "irrigated")
    assert rice_w < maize_w
    assert rice_w < pulse_w


def test_kansas_sorghum_or_field_pea_not_lentil() -> None:
    tidy, daily = _load("kansas")
    feats = compute_features(tidy, daily, current_rotation=["winter_wheat"])
    cands = build_candidates(
        ["winter_wheat"], feats, water_access="rainfed", weights=PriorityWeights()
    )
    sequences = [c["sequence"] for c in cands]
    flat = {cid for seq in sequences for cid in seq}
    assert "lentil" not in flat
    assert "sorghum" in flat or "field_pea" in flat


def test_iowa_cover_still_tops_soil_erosion() -> None:
    tidy, daily = _load("iowa")
    feats = compute_features(tidy, daily, current_rotation=["maize", "soybean"])
    current = score_strategy(["maize", "soybean"], feats)
    cover = score_strategy(["maize", "soybean", "cereal_rye_cover"], feats)
    assert cover.soil_health > current.soil_health
    assert cover.erosion > current.erosion
    cands = build_candidates(["maize", "soybean"], feats)
    ids = {c["id"] for c in cands}
    assert "current_plus_cover" in ids
    assert "water_wise_swap" not in ids
    for c in cands:
        assert "lentil" not in c["sequence"]
        assert "millet" not in c["sequence"]
