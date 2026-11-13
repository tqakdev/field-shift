"""Pure-Python strategy generation over cached/harmonized field features."""

from __future__ import annotations

from typing import Any

import pandas as pd

from fieldshift.engine.anomalies import detect_anomalies
from fieldshift.engine.candidates import build_candidates, season_label
from fieldshift.engine.explain import explain_strategy
from fieldshift.engine.features import compute_features
from fieldshift.engine.scenarios import apply_scenario
from fieldshift.engine.scoring import confidence_label, score_strategy
from fieldshift.models import (
    CropInSequence,
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

    cands = build_candidates(
        request.current_rotation,
        adj,
        water_access=request.water_access,
        weights=request.weights,
    )
    scored: list[tuple[dict[str, Any], Any]] = []
    for cand in cands:
        sc = score_strategy(
            cand["sequence"],
            adj,
            weights=request.weights,
            water_access=request.water_access,
            livestock=request.livestock,
        )
        scored.append((cand, sc))

    if not scored:
        return StrategyResult(field_id=field_id, strategies=[])

    current_total = next(
        (sc.total for cand, sc in scored if cand["id"] == "current"), scored[0][1].total
    )
    conf = confidence_label(adj, [sc for _, sc in scored], [c["sequence"] for c, _ in scored])

    cards: list[StrategyCard] = []
    for cand, sc in sorted(scored, key=lambda t: t[1].total, reverse=True):
        expl = explain_strategy(cand, adj, sc, anomalies=anomalies)
        cards.append(
            StrategyCard(
                id=cand["id"],
                name=expl["display_name"],
                sequence=[
                    CropInSequence(crop_id=cid, months=season_label(cid, adj))
                    for cid in cand["sequence"]
                ],
                scores=sc,
                delta_vs_current={"total": round(sc.total - current_total, 4)},
                why=expl["why"],
                evidence=expl["evidence"],
                benefits=expl["benefits"],
                data_gaps=expl["data_gaps"],
                risks_for_local_review=expl["risks_for_local_review"],
                confidence=conf,
            )
        )
    return StrategyResult(field_id=field_id, strategies=cards)
