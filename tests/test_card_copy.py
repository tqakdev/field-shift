"""Farmer-facing strategy card copy helpers."""

from __future__ import annotations

from types import SimpleNamespace

from fieldshift.engine.card_copy import (
    farmer_comparison_sentence,
    format_delta_label,
    rotation_title_line,
    top_criterion_diffs,
)
from fieldshift.engine.thresholds import DELTA_NEUTRAL_THRESHOLD


def test_delta_below_threshold_is_neutral() -> None:
    text, tone = format_delta_label(0.01)
    assert tone == "neutral"
    assert text == "About the same as yours"
    assert abs(0.01) < DELTA_NEUTRAL_THRESHOLD


def test_delta_at_threshold_shows_signed() -> None:
    text, tone = format_delta_label(0.02)
    assert tone == "up"
    assert text == "+0.02 vs yours"
    text2, tone2 = format_delta_label(-0.05)
    assert tone2 == "down"
    assert text2 == "-0.05 vs yours"


def test_top_criterion_diffs_returns_exactly_three() -> None:
    scores = SimpleNamespace(
        water=0.7,
        soil_health=0.6,
        erosion=0.5,
        pest_break=0.8,
        climate_fit=0.55,
        income=0.4,
    )
    baseline = SimpleNamespace(
        water=0.5,
        soil_health=0.6,
        erosion=0.7,
        pest_break=0.4,
        climate_fit=0.55,
        income=0.5,
    )
    diffs = top_criterion_diffs(scores, baseline, n=3)
    assert len(diffs) == 3
    # Largest |delta|: pest +0.4, erosion -0.2, water +0.2
    assert diffs[0]["key"] == "pest_break"
    assert {d["key"] for d in diffs} <= {
        "water",
        "soil_health",
        "erosion",
        "pest_break",
        "climate_fit",
        "income",
    }


def test_farmer_sentence_avoids_engine_jargon() -> None:
    diffs = [
        {
            "key": "erosion",
            "label": "Erosion",
            "delta": 0.06,
            "pct": 60,
            "direction": "better",
            "band": "Good",
            "friendly": "erosion protection",
        },
        {
            "key": "income",
            "label": "Income",
            "delta": -0.03,
            "pct": 50,
            "direction": "worse",
            "band": "Fair",
            "friendly": "income potential",
        },
        {
            "key": "water",
            "label": "Water",
            "delta": 0.0,
            "pct": 55,
            "direction": "same",
            "band": "Good",
            "friendly": "water match",
        },
    ]
    sentence = farmer_comparison_sentence(diffs, overall_delta=0.01)
    low = sentence.lower()
    assert "within 0." not in low
    assert "suitable option" not in low
    assert "soil_health" not in low
    assert "pest_break" not in low
    assert "climate_fit" not in low
    assert "erosion" in low or "income" in low


def test_rotation_title_strips_season_words() -> None:
    seq = [
        SimpleNamespace(crop_id="maize", months="summer May–Oct"),
        SimpleNamespace(crop_id="soybean", months="summer May–Oct"),
        SimpleNamespace(crop_id="cereal_rye_cover", months="Oct–Apr"),
    ]
    title = rotation_title_line(seq)
    assert "summer" not in title.lower()
    assert "Maize (May–Oct)" in title
    assert "→" in title
    assert "Cereal Rye Cover" in title or "Cereal Rye" in title
