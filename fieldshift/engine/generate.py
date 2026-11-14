"""Pure-Python strategy generation over cached/harmonized field features."""

from __future__ import annotations

from typing import Any

import pandas as pd

from fieldshift.engine.anomalies import detect_anomalies
from fieldshift.engine.candidates import build_candidates, season_label
from fieldshift.engine.constraints import evaluate_constraints, sequence_has_legume
from fieldshift.engine.explain import explain_strategy
from fieldshift.engine.features import compute_features
from fieldshift.engine.scenarios import apply_scenario
from fieldshift.engine.scoring import confidence_label, score_strategy
from fieldshift.engine.tiers import assign_tiers
from fieldshift.models import (
    CropInSequence,
    FarmConstraints,
    StrategyCard,
    StrategyRequest,
    StrategyResult,
)


def generate_strategies(
    field_id: str,
    tidy: pd.DataFrame,
    request: StrategyRequest,
    *,
    daily: pd.DataFrame | None = None,
    features: dict[str, Any] | None = None,
) -> StrategyResult:
    """Score candidate rotations. Must not call EE/POWER."""
    feats = features or compute_features(
        tidy, daily, current_rotation=request.current_rotation
    )
    if "series" not in feats:
        feats = compute_features(
            tidy, daily, current_rotation=request.current_rotation
        )
    anomalies = detect_anomalies(feats)
    adj = apply_scenario(feats, request.scenario)
    constraints = request.constraints or FarmConstraints()

    cands = build_candidates(
        request.current_rotation,
        adj,
        water_access=request.water_access,
        weights=request.weights,
    )
    scored: list[tuple[dict[str, Any], Any, dict[str, Any]]] = []
    for cand in cands:
        cons = evaluate_constraints(
            cand["sequence"],
            constraints,
            livestock=request.livestock,
        )
        sc = score_strategy(
            cand["sequence"],
            adj,
            weights=request.weights,
            water_access=request.water_access,
            irrigations_per_season=request.irrigations_per_season,
            nitrogen=request.nitrogen,
            livestock=request.livestock,
            market_access=constraints.market_access,
            soft_penalty=float(cons.get("soft_penalty") or 0.0),
        )
        scored.append((cand, sc, cons))

    if not scored:
        return StrategyResult(field_id=field_id, strategies=[])

    current_pair = next(
        ((cand, sc) for cand, sc, _ in scored if cand["id"] == "current"),
        (scored[0][0], scored[0][1]),
    )
    current_scores = current_pair[1]
    conf = confidence_label(
        adj, [sc for _, sc, _ in scored], [c["sequence"] for c, _, _ in scored]
    )

    cards: list[StrategyCard] = []
    for cand, sc, cons in sorted(scored, key=lambda t: t[1].total, reverse=True):
        expl = explain_strategy(cand, adj, sc, anomalies=anomalies)
        benefits = list(expl["benefits"])
        if sequence_has_legume(cand["sequence"]):
            benefits.insert(
                0, "May reduce N fertilizer for the next crop"
            )
        soft_notes = list(cons.get("soft_notes") or [])
        # Baseline stays visible even if it fails kit/market checks — still list reasons.
        unsuitable = list(cons.get("reasons") or [])
        cards.append(
            StrategyCard(
                id=cand["id"],
                name=expl["display_name"],
                sequence=[
                    CropInSequence(crop_id=cid, months=season_label(cid, adj))
                    for cid in cand["sequence"]
                ],
                scores=sc,
                delta_vs_current=_deltas_vs_current(sc, current_scores),
                why=expl["why"],
                evidence=expl["evidence"],
                benefits=benefits,
                data_gaps=expl["data_gaps"],
                risks_for_local_review=expl["risks_for_local_review"],
                confidence=conf,
                unsuitable_reasons=unsuitable,
                soft_notes=soft_notes,
            )
        )
    cards = assign_tiers(cards, weights=request.weights)
    return StrategyResult(field_id=field_id, strategies=cards)


_CRITERION_KEYS = (
    "water",
    "soil_health",
    "erosion",
    "pest_break",
    "climate_fit",
    "income",
)


def _deltas_vs_current(scores: Any, current: Any) -> dict[str, float]:
    """Per-criterion and total delta vs the farmer's current rotation scores."""
    out = {
        key: round(float(getattr(scores, key)) - float(getattr(current, key)), 4)
        for key in _CRITERION_KEYS
    }
    out["total"] = round(float(scores.total) - float(current.total), 4)
    return out
