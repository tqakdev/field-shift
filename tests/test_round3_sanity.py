"""Phase 3 round 3: GRACE order, season-compatible swaps, demo phenology sanity."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fieldshift.engine.candidates import (
    build_candidates,
    season_compatible,
    water_wise_replacements,
)
from fieldshift.engine.features import compute_features, grace_trend_deseasonalized
from fieldshift.engine.generate import generate_strategies
from fieldshift.engine.phenology import (
    looks_like_rice_wheat,
    looks_like_summer_crop,
    looks_like_winter_wheat,
)
from fieldshift.models import PriorityWeights, StrategyRequest

FIXTURE_DIR = Path(__file__).parent / "fixtures"
DEMO_FIELDS = json.loads(
    (Path(__file__).resolve().parents[1] / "mock" / "demo_fields.json").read_text()
)
DEMOS = {f["id"]: f for f in DEMO_FIELDS}


def _load(name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    tidy_p = FIXTURE_DIR / f"{name}_tidy.parquet"
    daily_p = FIXTURE_DIR / f"{name}_daily.parquet"
    if not tidy_p.exists() or not daily_p.exists():
        pytest.skip(f"{name} fixtures missing — run scripts/cache_demo_extracts.py")
    return pd.read_parquet(tidy_p), pd.read_parquet(daily_p)


def test_grace_deseasonalized_punjab_more_negative_than_iowa() -> None:
    iowa_t, _ = _load("iowa")
    punjab_t, _ = _load("punjab")
    iowa_f = compute_features(
        iowa_t, current_rotation=["maize", "soybean"]
    )
    punjab_f = compute_features(
        punjab_t, current_rotation=["rice", "winter_wheat"]
    )
    iowa_tr = iowa_f["grace_trend"]
    punjab_tr = punjab_f["grace_trend"]
    assert iowa_tr["trend_cm_per_yr"] is not None
    assert punjab_tr["trend_cm_per_yr"] is not None
    assert iowa_tr["se_cm_per_yr"] is not None
    assert "deseasonalized" in (iowa_tr["detail"] or "")
    assert "GRACE/GRACE-FO" in (punjab_tr["detail"] or "")
    print(
        f"Iowa GRACE: {iowa_tr['detail']}\n"
        f"Punjab GRACE: {punjab_tr['detail']}"
    )
    assert punjab_tr["trend_cm_per_yr"] < iowa_tr["trend_cm_per_yr"]


def test_grace_unit_deseasonalize_synthetic() -> None:
    idx = pd.period_range("2002-04", periods=240, freq="M")
    # seasonal cycle + linear decline
    months = idx.month.to_numpy()
    seasonal = 5.0 * np.sin(2 * np.pi * (months - 1) / 12.0)
    trend = -0.05 * np.arange(len(idx))  # ~ -0.6 cm/yr
    s = pd.Series(seasonal + trend, index=idx)
    out = grace_trend_deseasonalized(s)
    assert out["trend_cm_per_yr"] is not None
    assert out["trend_cm_per_yr"] == pytest.approx(-0.6, abs=0.05)
    assert out["se_cm_per_yr"] is not None
    assert out["se_cm_per_yr"] < 0.1


def test_cool_crop_cannot_replace_kharif_rice() -> None:
    tidy, daily = _load("punjab")
    feats = compute_features(
        tidy, daily, current_rotation=["rice", "winter_wheat"]
    )
    assert feats["crop_season_map"]["rice"]["season_label"] == "kharif"
    for cool in ("field_pea", "lentil", "winter_wheat"):
        assert season_compatible(cool, "rice", feats) is False
    # Warm replacements OK
    assert season_compatible("maize", "rice", feats) is True
    assert season_compatible("sorghum", "rice", feats) is True
    assert season_compatible("mung_bean", "rice", feats) is True
    cands = build_candidates(
        ["rice", "winter_wheat"],
        feats,
        water_access="irrigated",
        weights=PriorityWeights(),
    )
    for c in cands:
        # If rice replaced, replacement must not be cool-season
        if "rice" not in c["sequence"] and c["id"] == "water_wise_swap":
            rep = c["sequence"][0]
            assert rep not in {"field_pea", "lentil", "winter_wheat"}
            assert rep in {
                "sorghum",
                "maize",
                "millet",
                "mung_bean",
                "pigeon_pea",
                "soybean",
            }
        # No strategy may put field_pea/lentil in the rice slot
        if len(c["sequence"]) >= 2 and c["sequence"][0] in {"field_pea", "lentil"}:
            pytest.fail(f"cool crop in rice slot: {c}")


def test_maize_in_rice_water_wise_pool() -> None:
    tidy, daily = _load("punjab")
    feats = compute_features(
        tidy, daily, current_rotation=["rice", "winter_wheat"]
    )
    pool = water_wise_replacements(
        feats, "irrigated", exclude={"rice", "winter_wheat"}, replace_crop="rice"
    )
    assert "maize" in pool


def test_demo_field_sanity_all() -> None:
    """Detected seasons match demo label; GRACE order; no season-fit violations."""
    configs = {
        "iowa": {
            "rotation": ["maize", "soybean"],
            "water": "rainfed",
            "pattern": "summer",
        },
        "kansas": {
            "rotation": ["winter_wheat"],
            "water": "rainfed",
            "pattern": "winter_wheat",
        },
        "punjab": {
            "rotation": ["rice", "winter_wheat"],
            "water": "irrigated",
            "pattern": "rice_wheat",
        },
    }
    trends = {}
    for name, cfg in configs.items():
        tidy, daily = _load(name)
        feats = compute_features(
            tidy, daily, current_rotation=cfg["rotation"]
        )
        ph = feats["phenology"]
        clim = ph.get("climatology") or {}
        expected = DEMOS[name].get("expected_phenology") or cfg["pattern"]
        pattern = ph.get("pattern")
        if expected == "summer":
            assert looks_like_summer_crop(clim) or pattern == "summer"
            assert any(s.get("label") == "summer" for s in ph["seasons"])
        elif expected == "winter_wheat":
            assert looks_like_winter_wheat(clim) or pattern == "winter_wheat"
            assert any(s.get("label") == "winter" for s in ph["seasons"])
            # Must NOT look like a summer maize/soy pattern
            assert not looks_like_summer_crop(clim)
        elif expected == "rice_wheat":
            assert looks_like_rice_wheat(clim) or pattern == "rice_wheat"
            labels = {s.get("label") for s in ph["seasons"]}
            assert "kharif" in labels and "rabi" in labels
            assert 5 in (ph.get("fallow_months") or []) and 6 in (
                ph.get("fallow_months") or []
            )

        trends[name] = feats["grace_trend"]["trend_cm_per_yr"]
        assert trends[name] is not None

        req = StrategyRequest(
            current_rotation=cfg["rotation"],
            water_access=cfg["water"],  # type: ignore[arg-type]
            weights=PriorityWeights(),
        )
        result = generate_strategies(name, tidy, req, daily=daily)
        mapping = feats["crop_season_map"]
        for card in result.strategies:
            seq = [c.crop_id for c in card.sequence]
            mode = "water_wise" if card.id == "water_wise_swap" else "strict"
            # Every non-cover crop that replaced something in current must be season-ok
            for i, cid in enumerate(seq):
                if i >= len(cfg["rotation"]):
                    continue
                replaced = cfg["rotation"][i] if i < len(cfg["rotation"]) else None
                if replaced and cid != replaced:
                    assert season_compatible(cid, replaced, feats, mode=mode), (
                        f"{name}: {cid} not season-compatible with {replaced} ({mode})"
                    )
            # Never cool crop in a kharif-mapped rice slot
            if "rice" in mapping and mapping["rice"].get("season_label") == "kharif":
                if seq and seq[0] != "rice" and "rice" in cfg["rotation"]:
                    # water-wise replaced rice at index of rice
                    rice_idx = cfg["rotation"].index("rice")
                    if rice_idx < len(seq) and seq[rice_idx] != "rice":
                        from fieldshift.engine.candidates import COOL_SEASON_IDS
                        from fieldshift.engine.crops import crop_by_id

                        assert seq[rice_idx] not in COOL_SEASON_IDS
                        assert crop_by_id(seq[rice_idx])["season"] != "cool"

    assert trends["punjab"] < trends["iowa"]
    print(
        f"sanity GRACE iowa={trends['iowa']:.2f} kansas={trends['kansas']:.2f} "
        f"punjab={trends['punjab']:.2f}"
    )
