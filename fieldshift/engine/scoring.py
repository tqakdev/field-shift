"""Criterion scores in [0, 1]. Formulas documented in each function docstring."""

from __future__ import annotations

from typing import Any

from fieldshift.engine.crops import crop_by_id
from fieldshift.engine.thresholds import (
    IRRIGATION_EVENT_WATER_CAP,
    IRRIGATION_EVENT_WATER_LIFT,
    MARKET_BUYER_INCOME_LIFT,
    N_LEGUME_BONUS,
)
from fieldshift.models import (
    Confidence,
    MarketAccess,
    NitrogenUse,
    PriorityWeights,
    ScoreSet,
    WaterAccess,
)

MARKET_TIER = {"none": 0.0, "low": 0.3, "medium": 0.6, "high": 0.9}
ROOT_DEPTH = {"shallow": 0.35, "medium": 0.65, "deep": 1.0}


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def grace_groundwater_penalty(features: dict[str, Any]) -> float:
    """Documented GRACE/FO groundwater stress penalty ∈ [0, 0.25].

    penalty = min(0.25, −trend_cm_per_yr / 20) when trend < 0; else 0.
    """
    trend = features.get("grace_trend_cm_per_yr")
    if trend is None or trend >= 0:
        return 0.0
    return float(min(0.25, -float(trend) / 20.0))


def score_water(
    sequence: list[str],
    features: dict[str, Any],
    water_access: WaterAccess = "rainfed",
    irrigations_per_season: int = 0,
) -> float:
    """Water score from seasonal irrigation requirement (Kc × ET0 − effective rain).

    For each non-cover crop::

        demand = Σ_season (Kc × ET0_month)   # FAO mid-season Kc
        rain_eff = 0.8 × Σ_season rain_best   # single rain series everywhere
        IR = max(0, demand − rain_eff)
        crop_score = rain_eff / max(demand, 1)   # saturates at 1 only if rain covers demand

    Sequence score = mean(crop_score). Cover crops are excluded from the mean.

    Irrigated fields: same IR framing (irrigation does not erase demand) plus a
    **regional groundwater penalty** from GRACE/FO LWE trend when negative::

        score = clip(mean_crop_score − grace_penalty)
        grace_penalty = min(0.25, −trend_cm_per_yr / 20)

    Limited irrigation: half the grace penalty. Rainfed: no grace penalty.
    When irrigated/limited, ``irrigations_per_season`` adds
    ``min(CAP, n × LIFT)`` (see thresholds.py).
    """
    from fieldshift.engine.crop_water import irrigation_requirement_mm

    cash = [c for c in sequence if crop_by_id(c)["type"] != "cover"]
    if not cash:
        return 0.5
    scores = []
    for cid in cash:
        ir = irrigation_requirement_mm(cid, features)
        demand = max(ir["demand_mm"], 1.0)
        rain_eff = ir["rain_eff_mm"]
        scores.append(_clip01(rain_eff / demand))
    base = sum(scores) / len(scores)
    penalty = grace_groundwater_penalty(features)
    if water_access == "irrigated":
        score = base - penalty
    elif water_access == "limited":
        score = base - 0.5 * penalty
    else:
        score = base
    if water_access in ("irrigated", "limited") and irrigations_per_season > 0:
        lift = min(
            IRRIGATION_EVENT_WATER_CAP,
            irrigations_per_season * IRRIGATION_EVENT_WATER_LIFT,
        )
        score += lift
    return _clip01(score)


def score_soil_health(
    sequence: list[str],
    features: dict[str, Any],
    *,
    nitrogen: NitrogenUse = "unknown",
) -> float:
    """Weighted mean of N-fixing, residue OM, root depth, and cover months.

    weights: N-fix 0.3, residue 0.25, root 0.2, cover 0.25.
    Cover = 1 − (n_bare_months / 12).
    When any crop is nitrogen-fixing, add ``N_LEGUME_BONUS[nitrogen]``
    (larger when current fertilizer use is high).
    """
    if not sequence:
        return 0.0
    nfix = sum(1.0 if crop_by_id(c)["nitrogen_fixing"] else 0.0 for c in sequence) / len(
        sequence
    )
    residue = sum(float(crop_by_id(c)["residue_organic_matter"]) for c in sequence) / len(
        sequence
    )
    root = sum(ROOT_DEPTH.get(crop_by_id(c)["root_depth"], 0.5) for c in sequence) / len(
        sequence
    )
    bare_n = len(features.get("bare_months", {}).get("months") or [])
    # covers in sequence reduce effective bare
    cover_boost = sum(1 for c in sequence if crop_by_id(c)["type"] == "cover")
    bare_eff = max(0, bare_n - cover_boost)
    cover = 1.0 - bare_eff / 12.0
    base = 0.3 * nfix + 0.25 * residue + 0.2 * root + 0.25 * cover
    if any(bool(crop_by_id(c).get("nitrogen_fixing")) for c in sequence):
        base += float(N_LEGUME_BONUS.get(nitrogen, N_LEGUME_BONUS["unknown"]))
    return _clip01(base)


def score_erosion(sequence: list[str], features: dict[str, Any]) -> float:
    """Erosion = ground cover during risk periods × (1 − slope/extreme factor).

    score = mean(ground_cover, erosion_protection) × (1 − 0.6 * erosion_risk)
    Cover crops in the sequence raise the mean.
    """
    if not sequence:
        return 0.0
    cover = sum(
        0.5 * float(crop_by_id(c)["ground_cover"])
        + 0.5 * float(crop_by_id(c)["erosion_protection"])
        for c in sequence
    ) / len(sequence)
    risk = float(features.get("erosion_risk") or 0.0)
    return _clip01(cover * (1.0 - 0.6 * risk))


def score_pest_break(sequence: list[str]) -> float:
    """Pest break from family diversity and avoiding consecutive same family.

    diversity = n_unique_families / max(3, n_slots)
    consecutive penalty: −0.15 per same-family adjacent pair.
    """
    if not sequence:
        return 0.0
    families = [crop_by_id(c)["family"] for c in sequence]
    diversity = len(set(families)) / max(3.0, float(len(families)))
    penalty = 0.0
    for a, b in zip(families, families[1:], strict=False):
        if a == b:
            penalty += 0.15
    return _clip01(diversity - penalty)


def score_climate_fit(
    sequence: list[str],
    features: dict[str, Any],
    *,
    season_months: list[int] | None = None,
) -> float:
    """Climate fit = mean of frost / GDD / heat / drought margins (no GAEZ yet).

    When ``season_months`` is set, heat / GDD / frost / mean Tmax are taken from
    that window (via ``season_window_climate``), not annual averages — required
    for season-compatible swap checks (e.g. kharif rice vs cool-season pea).

    frost_margin = clip((frost_free − crop.min_frost_free) / max(crop.min_frost_free, 1))
    gdd_margin similarly; heat = crop.heat_tolerance vs normalized heat_days;
    drought = crop.drought_tolerance vs rain_cv.
    Final = mean of available margins (Phase 7 may blend 70% this / 30% GAEZ).
    """
    rain_cv = features.get("rain", {}).get("rain_cv") or 0.2
    if season_months:
        from fieldshift.engine.features import season_window_climate

        win = season_window_climate(features.get("daily"), season_months)
        frost_free = win.get("frost_free_proxy_days")
        gdd_mean = win.get("gdd_mean")
        heat_days = win.get("heat_days_mean") or 0.0
        tmax_mean = win.get("tmax_mean")
    else:
        frost_free = features.get("frost_window", {}).get("frost_free_days")
        gdd_mean = features.get("gdd", {}).get("gdd_annual_mean")
        heat_days = features.get("gdd", {}).get("heat_days_mean") or 0.0
        tmax_mean = None
    margins = []
    for cid in sequence:
        c = crop_by_id(cid)
        if frost_free is not None and c["min_frost_free_days"]:
            # Scale crop frost-free need to season length (~fraction of year)
            need = float(c["min_frost_free_days"])
            if season_months:
                need = need * (len(season_months) / 12.0)
            margins.append(_clip01((frost_free - need) / max(need, 1.0)))
        elif c["min_frost_free_days"] == 0:
            margins.append(1.0)
        if gdd_mean is not None and c["gdd_required"]:
            need_gdd = float(c["gdd_required"])
            if season_months:
                need_gdd = need_gdd * (len(season_months) / 12.0)
            margins.append(_clip01(gdd_mean / max(need_gdd, 1.0)))
        heat_load = min(1.0, heat_days / 20.0)
        margins.append(_clip01(float(c["heat_tolerance"]) * (1.0 - 0.5 * heat_load)))
        # Cool-season crops fail hot windows (mean Tmax ≫ 30 °C)
        if tmax_mean is not None and c["season"] == "cool" and tmax_mean > 32:
            margins.append(_clip01(float(c["heat_tolerance"]) * 0.2))
        if tmax_mean is not None and c["season"] == "warm" and tmax_mean < 18:
            margins.append(0.2)
        margins.append(_clip01(float(c["drought_tolerance"]) * (1.0 - min(1.0, rain_cv))))
    if not margins:
        return 0.5
    return _clip01(sum(margins) / len(margins))


# Documented off-season cover establishment cost (fraction of income score).
COVER_ESTABLISHMENT_PENALTY = 0.05
COVER_FORAGE_BONUS = 0.08


def score_income(
    sequence: list[str],
    livestock: bool = False,
    *,
    market_access: dict[str, MarketAccess] | None = None,
) -> float:
    """Relative income proxy (not a farm budget).

    income = mean(market_tier of non-cover crops)
           − COVER_ESTABLISHMENT_PENALTY × n_cover_crops
           + COVER_FORAGE_BONUS if livestock and any cover forage_value > 0.5
           + MARKET_BUYER_INCOME_LIFT × share of cash crops with buyer access

    ``market_tier`` ≈ typical price tier × yield potential. Market access adjusts
    the relative score; "no local market" is a hard constraint for cash crops
    (see constraints.py), not a soft income cut here.
    """
    if not sequence:
        return 0.0
    access = market_access or {}
    cash = [c for c in sequence if crop_by_id(c)["type"] != "cover"]
    covers = [c for c in sequence if crop_by_id(c)["type"] == "cover"]
    if not cash:
        base = 0.0
    else:
        tiers = [MARKET_TIER.get(crop_by_id(c)["market_tier"], 0.3) for c in cash]
        base = sum(tiers) / len(tiers)
        buyer_n = sum(1 for c in cash if access.get(c) == "buyer")
        if buyer_n:
            base += MARKET_BUYER_INCOME_LIFT * (buyer_n / len(cash))
    base -= COVER_ESTABLISHMENT_PENALTY * len(covers)
    if livestock and covers:
        forage = max(float(crop_by_id(c)["forage_value"]) for c in covers)
        if forage > 0.5:
            base += COVER_FORAGE_BONUS
    return _clip01(base)


def score_strategy(
    sequence: list[str],
    features: dict[str, Any],
    *,
    weights: PriorityWeights | None = None,
    water_access: WaterAccess = "rainfed",
    irrigations_per_season: int = 0,
    nitrogen: NitrogenUse = "unknown",
    livestock: bool = False,
    market_access: dict[str, MarketAccess] | None = None,
    soft_penalty: float = 0.0,
) -> ScoreSet:
    """Weighted total = Σ(w_i × s_i) / Σ w_i − soft_penalty (clipped)."""
    weights = weights or PriorityWeights()
    scores = {
        "water": score_water(
            sequence,
            features,
            water_access,
            irrigations_per_season=irrigations_per_season,
        ),
        "soil_health": score_soil_health(sequence, features, nitrogen=nitrogen),
        "erosion": score_erosion(sequence, features),
        "pest_break": score_pest_break(sequence),
        "climate_fit": score_climate_fit(sequence, features),
        "income": score_income(
            sequence, livestock, market_access=market_access
        ),
    }
    w = weights.model_dump()
    total_w = sum(w[k] for k in scores)
    total = sum(w[k] * scores[k] for k in scores) / total_w if total_w else 0.0
    total = _clip01(total - float(soft_penalty or 0.0))
    return ScoreSet(**scores, total=float(total))


def confidence_label(
    features: dict[str, Any],
    scores: list[ScoreSet],
    sequence_ids: list[list[str]],
) -> Confidence:
    """high/medium/low from coverage, expert-review flags, and score separation."""
    from fieldshift.engine.crops import crop_by_id

    cov = features.get("data_coverage", {}).get("per_variable") or []
    if cov:
        rates = []
        for row in cov:
            n = row.get("n_valid", 0) + row.get("n_gaps", 0)
            if n:
                rates.append(row.get("n_valid", 0) / n)
        coverage = float(sum(rates) / len(rates)) if rates else 0.5
    else:
        coverage = 0.5
    review = any(
        crop_by_id(cid).get("needs_expert_review")
        for seq in sequence_ids
        for cid in seq
    )
    if len(scores) >= 2:
        totals = sorted([s.total for s in scores], reverse=True)
        separation = totals[0] - totals[1]
    else:
        separation = 0.1
    if coverage >= 0.85 and separation >= 0.05 and not review:
        return "high"
    if coverage >= 0.6:
        return "medium"
    return "low"
