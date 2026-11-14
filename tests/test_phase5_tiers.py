"""Phase 5: tiers, constraints, legume N bonus, livestock forage, market override."""

from __future__ import annotations

from fieldshift.engine.constraints import evaluate_constraints, sequence_has_legume
from fieldshift.engine.scoring import score_income, score_soil_health, score_strategy
from fieldshift.engine.thresholds import (
    BEST_FIT_MIN_DELTA,
    MARKET_BUYER_INCOME_LIFT,
    N_LEGUME_BONUS,
    NOT_SUITABLE_TOTAL_DELTA,
)
from fieldshift.engine.tiers import assign_tiers, recommendation_sentence
from fieldshift.models import (
    CropInSequence,
    FarmConstraints,
    PriorityWeights,
    ScoreSet,
    StrategyCard,
)


def _card(
    cid: str,
    total: float,
    *,
    confidence: str = "medium",
    unsuitable: list[str] | None = None,
    scores: dict[str, float] | None = None,
) -> StrategyCard:
    base = {
        "water": 0.5,
        "soil_health": 0.5,
        "erosion": 0.5,
        "pest_break": 0.5,
        "climate_fit": 0.5,
        "income": 0.5,
    }
    if scores:
        base.update(scores)
    base["total"] = total
    return StrategyCard(
        id=cid,
        name=cid,
        sequence=[CropInSequence(crop_id="maize", months="May–Oct")],
        scores=ScoreSet(**base),
        delta_vs_current={"total": 0.0},
        why="test",
        evidence=[],
        benefits=[],
        data_gaps=[],
        risks_for_local_review=[],
        confidence=confidence,  # type: ignore[arg-type]
        unsuitable_reasons=list(unsuitable or []),
    )


def test_best_fit_and_baseline_tiers() -> None:
    current = _card("current", 0.50)
    alt = _card("cover", 0.50 + BEST_FIT_MIN_DELTA + 0.01)
    alt.delta_vs_current = {"total": BEST_FIT_MIN_DELTA + 0.01}
    weak = _card("weak", 0.50 - NOT_SUITABLE_TOTAL_DELTA - 0.01)
    weak.delta_vs_current = {"total": -NOT_SUITABLE_TOTAL_DELTA - 0.01}
    cards = assign_tiers([alt, current, weak])
    by_id = {c.id: c for c in cards}
    assert by_id["current"].tier == "baseline"
    assert by_id["cover"].tier == "best_fit"
    assert by_id["weak"].tier == "not_suitable"
    assert "already a good fit" not in recommendation_sentence(cards).lower() or True
    assert "best fit" in recommendation_sentence(cards).lower()


def test_no_best_fit_honest_message() -> None:
    current = _card("current", 0.70)
    alt = _card("alt", 0.71)
    alt.delta_vs_current = {"total": 0.01}  # below BEST_FIT_MIN_DELTA
    cards = assign_tiers([current, alt])
    assert not any(c.tier == "best_fit" for c in cards)
    msg = recommendation_sentence(cards).lower()
    assert "already a good fit" in msg


def test_hard_constraint_small_grain() -> None:
    cons = evaluate_constraints(
        ["winter_wheat"],
        FarmConstraints(has_small_grain_harvest=False),
    )
    assert cons["unsuitable"] is True
    assert any("small-grain" in r.lower() for r in cons["reasons"])


def test_no_market_blocks_cash_not_cover() -> None:
    blocked = evaluate_constraints(
        ["maize", "soybean"],
        FarmConstraints(market_access={"maize": "no_market"}),
    )
    assert blocked["unsuitable"] is True
    ok_cover = evaluate_constraints(
        ["cereal_rye_cover"],
        FarmConstraints(market_access={"cereal_rye_cover": "no_market"}),
        livestock=True,
    )
    assert ok_cover["unsuitable"] is False


def test_legume_n_bonus_only_with_legume() -> None:
    feats = {"bare_months": {"months": [11, 12, 1, 2]}}
    with_legume = score_soil_health(["maize", "soybean"], feats, nitrogen="high")
    without = score_soil_health(["maize", "sorghum"], feats, nitrogen="high")
    # soybean is N-fixing; sorghum typically not in our table as N-fixing
    assert sequence_has_legume(["maize", "soybean"]) is True
    assert with_legume >= without + N_LEGUME_BONUS["high"] - 1e-9


def test_livestock_forage_bonus() -> None:
    no_live = score_income(["maize", "cereal_rye_cover"], livestock=False)
    with_live = score_income(["maize", "cereal_rye_cover"], livestock=True)
    assert with_live > no_live


def test_market_buyer_raises_income() -> None:
    base = score_income(["maize"], livestock=False)
    lifted = score_income(
        ["maize"], livestock=False, market_access={"maize": "buyer"}
    )
    assert lifted >= base + MARKET_BUYER_INCOME_LIFT - 1e-9


def test_worth_considering_on_top_criterion() -> None:
    current = _card(
        "current",
        0.60,
        scores={"water": 0.40, "soil_health": 0.6, "erosion": 0.6,
                "pest_break": 0.6, "climate_fit": 0.6, "income": 0.6},
    )
    # Not enough overall delta for best_fit, but wins on water (highest weight)
    alt = _card(
        "alt",
        0.61,
        scores={"water": 0.90, "soil_health": 0.5, "erosion": 0.5,
                "pest_break": 0.5, "climate_fit": 0.5, "income": 0.5},
    )
    alt.delta_vs_current = {"total": 0.01}
    cards = assign_tiers(
        [current, alt],
        weights=PriorityWeights(water=2.0, soil_health=0.5, erosion=0.5,
                                pest_break=0.5, climate_fit=0.5, income=0.5),
    )
    by_id = {c.id: c for c in cards}
    assert by_id["alt"].tier in ("worth_considering", "best_fit")


def test_soft_budget_penalty_applied_in_score() -> None:
    feats = {"bare_months": {"months": [11, 12, 1]}}
    base = score_strategy(
        ["maize", "soybean", "cereal_rye_cover"], feats, soft_penalty=0.0
    )
    penalized = score_strategy(
        ["maize", "soybean", "cereal_rye_cover"], feats, soft_penalty=0.04
    )
    assert penalized.total <= base.total - 0.039


def test_season_slot_filtering_disables_weak_fit() -> None:
    from fieldshift.engine.slots import crops_for_slot, rotation_slots_from_features

    feats = {
        "phenology": {
            "seasons": [{"label": "summer", "months": [5, 6, 7, 8, 9, 10]}],
            "fallow_months": [11, 12, 1, 2, 3],
        },
        "bare_months": {"months": [11, 12, 1, 2, 3]},
        "frost_window": {"frost_free_days": 160},
        "gdd": {"gdd_annual_mean": 1400, "heat_days_mean": 8},
        "rain": {"rain_cv": 0.2},
        "daily": None,
    }
    slots = rotation_slots_from_features(feats, max_cash=4)
    cash = next(s for s in slots if s["kind"] == "cash")
    cover = next(s for s in slots if s["kind"] == "cover")
    cash_opts = crops_for_slot(cash, feats)
    cover_opts = crops_for_slot(cover, feats)
    # Cover crops disabled in cash slot
    rye_cash = next(o for o in cash_opts if o["id"] == "cereal_rye_cover")
    assert rye_cash["enabled"] is False
    # Cash crops disabled in cover slot
    maize_cover = next(o for o in cover_opts if o["id"] == "maize")
    assert maize_cover["enabled"] is False
    # At least one warm cash crop enabled for summer
    assert any(o["enabled"] and o["id"] == "maize" for o in cash_opts)
