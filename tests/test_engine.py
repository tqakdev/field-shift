"""Engine unit tests — synthetic series only (no network)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fieldshift.engine.anomalies import detect_anomalies
from fieldshift.engine.candidates import (
    WATER_WISE_ANNUAL_DEFICIT_MM,
    WATER_WISE_RAIN_CV,
    build_candidates,
    climate_ok,
    water_wise_needed,
)
from fieldshift.engine.crops import crop_by_id, load_crops
from fieldshift.engine.features import compute_features
from fieldshift.engine.generate import generate_strategies
from fieldshift.engine.scenarios import apply_scenario
from fieldshift.engine.scoring import (
    COVER_ESTABLISHMENT_PENALTY,
    score_income,
    score_strategy,
    score_water,
)
from fieldshift.models import PriorityWeights, ScenarioParams, StrategyRequest


def _synthetic_tidy(years: int = 5) -> pd.DataFrame:
    rows = []
    rng = np.random.default_rng(0)
    for y in range(2018, 2018 + years):
        for m in range(1, 13):
            month = f"{y}-{m:02d}"
            ndvi = 0.15 + 0.55 * max(0, np.sin((m - 3) / 12 * np.pi))
            rain = 40 + 60 * max(0, np.sin((m - 4) / 12 * np.pi)) + rng.normal(0, 5)
            et0 = 20 + 15 * max(0, np.sin((m - 3) / 12 * np.pi))
            sm = 0.25 + 0.05 * np.sin(m / 12 * 2 * np.pi)
            for var, val, unit, source in [
                ("ndvi_s2", ndvi, "1", "Sentinel-2 NDVI"),
                ("sm_surface", sm, "m3/m3", "SMAP"),
                ("rain_best_mm", max(0, rain), "mm/month", "POWER/IMERG"),
                ("rain_mm", max(0, rain), "mm/month", "IMERG"),
                ("power_rain_mm", max(0, rain * 0.98), "mm/month", "POWER"),
                ("et0_mm", et0, "mm/month", "FAO-56 ET0"),
                ("water_balance_mm", max(0, rain) - et0, "mm/month", "wb"),
                ("power_t2m_c", 5 + m * 1.5, "deg_C", "POWER"),
                ("power_t2m_max_c", 10 + m * 1.5, "deg_C", "POWER"),
                ("power_t2m_min_c", m * 1.2 - 5, "deg_C", "POWER"),
                ("grace_lwe_cm", -2 + 0.01 * (y - 2018), "cm", "GRACE"),
            ]:
                rows.append(
                    {
                        "month": month,
                        "variable": var,
                        "value": float(val),
                        "unit": unit,
                        "source": source,
                        "n_obs": 1,
                    }
                )
    rows.append(
        {
            "month": "static",
            "variable": "slope_pct",
            "value": 2.0,
            "unit": "percent",
            "source": "SRTM",
            "n_obs": 1,
        }
    )
    return pd.DataFrame(rows)


def _synthetic_daily(years: int = 5) -> pd.DataFrame:
    idx = pd.date_range("2018-01-01", periods=365 * years, freq="D", tz="UTC")
    doy = idx.dayofyear
    t = -5 + 30 * np.sin(2 * np.pi * (doy - 80) / 365)
    return pd.DataFrame(
        {
            "T2M": t,
            "T2M_MAX": t + 8,
            "T2M_MIN": t - 8,
            "PRECTOTCORR": 2.0,
        },
        index=idx,
    )


def test_crops_have_sources_and_review_flags() -> None:
    crops = load_crops()
    assert len(crops) >= 15
    for c in crops:
        assert c["sources"]
        assert "needs_expert_review" in c


def test_features_from_synthetic() -> None:
    feats = compute_features(
        _synthetic_tidy(), _synthetic_daily(), current_rotation=["maize", "soybean"]
    )
    assert feats["rain"]["rain_annual_mm"] is not None
    assert feats["frost_window"]["frost_free_days"] is not None
    assert "erosion_risk" in feats
    assert feats["bare_months"]["calendar_fallow"]


def test_anomalies_split_growing_and_offseason() -> None:
    feats = compute_features(
        _synthetic_tidy(years=6),
        _synthetic_daily(years=6),
        current_rotation=["maize", "soybean"],
    )
    out = detect_anomalies(feats)
    assert "flagged_growing_season" in out
    assert "flagged_off_season" in out
    assert "uncertainty" in out


def test_phenology_double_peak_kharif_rabi() -> None:
    """Synthetic double-peak NDVI → kharif Jun–Oct, rabi Nov–Apr, fallow ≈ May–Jun."""
    from fieldshift.engine.phenology import detect_seasons_from_ndvi, map_crops_to_seasons

    rows = []
    # Twin peaks: monsoon (Aug) + winter (Feb); trough May–Jun
    clim = {
        1: 0.42,
        2: 0.55,
        3: 0.50,
        4: 0.40,
        5: 0.22,
        6: 0.28,
        7: 0.48,
        8: 0.62,
        9: 0.58,
        10: 0.46,
        11: 0.38,
        12: 0.40,
    }
    for y in range(2018, 2024):
        for m, v in clim.items():
            rows.append((f"{y}-{m:02d}", v))
    ndvi = pd.Series(
        {pd.Period(m): v for m, v in rows},
    )
    ndvi.index = pd.PeriodIndex(ndvi.index, freq="M")
    ph = detect_seasons_from_ndvi(ndvi, source_label="Sentinel-2 NDVI")
    assert ph["n_seasons"] == 2
    labels = {s["label"] for s in ph["seasons"]}
    assert labels == {"kharif", "rabi"}
    by_label = {s["label"]: s["months"] for s in ph["seasons"]}
    assert by_label["kharif"] == [6, 7, 8, 9, 10]
    assert by_label["rabi"] == [11, 12, 1, 2, 3, 4]
    assert set(ph["fallow_months"]) <= {5, 6}
    assert 5 in ph["fallow_months"] and 6 in ph["fallow_months"]
    assert "Seasons detected from Sentinel-2 NDVI" in ph["detail"]
    mapping = map_crops_to_seasons(["rice", "winter_wheat"], ph)
    assert mapping["rice"]["season_label"] == "kharif"
    assert mapping["winter_wheat"]["season_label"] == "rabi"


def test_irrigated_rice_worse_water_than_maize_or_pulse() -> None:
    feats = compute_features(
        _synthetic_tidy(years=6),
        _synthetic_daily(years=6),
        current_rotation=["rice", "winter_wheat"],
    )
    # Force dual-season map like Punjab
    from fieldshift.engine.phenology import KHARIF_MONTHS, RABI_MONTHS

    feats["crop_season_map"] = {
        "rice": {"season_label": "kharif", "months": list(KHARIF_MONTHS), "source": "ndvi"},
        "winter_wheat": {
            "season_label": "rabi",
            "months": list(RABI_MONTHS),
            "source": "ndvi",
        },
        "maize": {"season_label": "kharif", "months": list(KHARIF_MONTHS), "source": "ndvi"},
        "field_pea": {
            "season_label": "rabi",
            "months": list(RABI_MONTHS),
            "source": "ndvi",
        },
    }
    feats["grace_trend_cm_per_yr"] = -3.0
    rice = score_water(["rice", "winter_wheat"], feats, "irrigated")
    maize = score_water(["maize", "winter_wheat"], feats, "irrigated")
    pulse = score_water(["field_pea", "winter_wheat"], feats, "irrigated")
    assert rice < maize
    assert rice < pulse
    assert rice < 0.95  # must not saturate at 1.0


def test_scoring_monotonic_water_with_more_rain() -> None:
    feats_dry = {
        "rain": {"rain_annual_mm": 400.0, "rain_cv": 0.2},
        "bare_months": {"months": [11, 12, 1, 2]},
        "frost_window": {"frost_free_days": 160},
        "gdd": {"gdd_annual_mean": 1500, "heat_days_mean": 5},
        "erosion_risk": 0.3,
        "water_balance": {"annual_deficit_mm": -200},
        "data_coverage": {"per_variable": []},
    }
    feats_wet = {**feats_dry, "rain": {"rain_annual_mm": 900.0, "rain_cv": 0.15}}
    seq = ["maize", "soybean"]
    assert score_water(seq, feats_wet) > score_water(seq, feats_dry)


def test_income_cover_not_averaged_and_small_penalty() -> None:
    cash = score_income(["maize", "soybean"], livestock=False)
    with_cover = score_income(["maize", "soybean", "cereal_rye_cover"], livestock=False)
    assert cash == pytest.approx(0.9)
    assert with_cover == pytest.approx(cash - COVER_ESTABLISHMENT_PENALTY)
    assert abs(cash - with_cover) <= 0.05 + 1e-9


def test_cover_raises_soil_health() -> None:
    feats = {
        "rain": {"rain_annual_mm": 900.0, "rain_cv": 0.15},
        "bare_months": {"months": [11, 12, 1, 2, 3, 4, 10]},
        "frost_window": {"frost_free_days": 160},
        "gdd": {"gdd_annual_mean": 1600, "heat_days_mean": 4},
        "erosion_risk": 0.4,
        "water_balance": {"annual_deficit_mm": -50},
        "data_coverage": {"per_variable": []},
    }
    base = score_strategy(["maize", "soybean"], feats)
    with_cover = score_strategy(["maize", "soybean", "cereal_rye_cover"], feats)
    assert with_cover.soil_health >= base.soil_health
    assert with_cover.erosion >= base.erosion
    assert abs(with_cover.income - base.income) <= 0.05 + 1e-9


def test_candidate_skips_water_wise_when_mild() -> None:
    feats = {
        "frost_window": {"frost_free_days": 160},
        "gdd": {"gdd_annual_mean": 1600, "heat_days_mean": 5},
        "rain": {"rain_annual_mm": 900, "rain_cv": 0.20},
        "water_balance": {"annual_deficit_mm": -40},
        "bare_months": {
            "months": [10, 11, 12, 1, 2, 3, 4],
            "calendar_fallow": [10, 11, 12, 1, 2, 3, 4],
        },
        "erosion_risk": 0.2,
        "data_coverage": {"per_variable": []},
    }
    assert water_wise_needed(feats) is False
    assert feats["rain"]["rain_cv"] < WATER_WISE_RAIN_CV
    assert feats["water_balance"]["annual_deficit_mm"] > WATER_WISE_ANNUAL_DEFICIT_MM
    cands = build_candidates(["maize", "soybean"], feats)
    ids = {c["id"] for c in cands}
    assert "current" in ids
    assert "water_wise_swap" not in ids
    assert "legume_swap" not in ids  # soybean already present


def test_candidate_filters_cotton() -> None:
    feats = {
        "frost_window": {"frost_free_days": 160},
        "gdd": {"gdd_annual_mean": 1600, "heat_days_mean": 5},
        "rain": {"rain_annual_mm": 900, "rain_cv": 0.15},
        "water_balance": {"annual_deficit_mm": -80},
        "bare_months": {"months": [11, 12, 1], "calendar_fallow": [11, 12, 1]},
        "erosion_risk": 0.2,
        "data_coverage": {"per_variable": []},
    }
    assert climate_ok(crop_by_id("cotton"), feats, "rainfed") is False


def test_scenario_rescore_changes_water() -> None:
    feats = compute_features(
        _synthetic_tidy(), _synthetic_daily(), current_rotation=["maize", "soybean"]
    )
    base = score_strategy(["maize", "soybean"], feats)
    dry = apply_scenario(feats, ScenarioParams(rain_mult=0.7, temp_offset=0.0))
    dry_score = score_strategy(["maize", "soybean"], dry)
    assert dry_score.water <= base.water + 1e-9


def test_generate_strategies_returns_cards() -> None:
    tidy = _synthetic_tidy()
    daily = _synthetic_daily()
    req = StrategyRequest(
        current_rotation=["maize", "soybean"],
        weights=PriorityWeights(),
    )
    result = generate_strategies("iowa_synth", tidy, req, daily=daily)
    assert result.strategies
    card = result.strategies[0]
    assert card.why
    assert card.evidence
    assert card.benefits
    assert card.data_gaps
    assert card.risks_for_local_review
    assert 0.0 <= card.scores.total <= 1.0
