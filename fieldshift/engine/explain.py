"""Template-based deterministic explanations for strategy cards."""

from __future__ import annotations

from typing import Any

from fieldshift.engine.crops import crop_by_id
from fieldshift.engine.scoring import grace_groundwater_penalty
from fieldshift.models import EvidenceItem, ScoreSet


def explain_strategy(
    strategy: dict[str, Any],
    features: dict[str, Any],
    scores: ScoreSet,
    *,
    anomalies: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bare = features.get("bare_months", {})
    rain = features.get("rain", {})
    frost = features.get("frost_window", {})
    phenology = features.get("phenology") or {}
    erisk = features.get("erosion_risk")
    seq = strategy["sequence"]
    names = [crop_by_id(c)["name"] for c in seq]

    why_bits = []
    if bare.get("months"):
        why_bits.append(bare.get("detail") or "Persistent bare months detected.")
    if (rain.get("rain_cv") or 0) > 0.2:
        why_bits.append(
            f"Year-to-year rain variability is high (CV={rain['rain_cv']:.2f})."
        )
    if any(crop_by_id(c)["type"] == "cover" for c in seq):
        why_bits.append("A cover crop is included to protect soil in the off-season.")
    if not why_bits:
        why_bits.append(
            f"Scores favour this rotation for local water, soil, and climate margins "
            f"(total={scores.total:.2f})."
        )
    why = " ".join(why_bits[:2])

    evidence: list[EvidenceItem] = []
    if phenology.get("n_seasons", 0) > 0 and phenology.get("detail"):
        evidence.append(
            EvidenceItem(
                text=str(phenology["detail"]),
                source=str(phenology.get("source") or "NDVI"),
            )
        )
    elif bare.get("evidence_line"):
        evidence.append(
            EvidenceItem(text=str(bare["evidence_line"]), source="Sentinel-2/MODIS NDVI")
        )
    if bare.get("detail") and bare.get("ndvi_confirmed_ok"):
        evidence.append(EvidenceItem(text=str(bare["detail"]), source="Sentinel-2 NDVI"))
    if rain.get("rain_annual_mm") is not None:
        src = rain.get("source") or "rain_best"
        period = rain.get("period") or ""
        evidence.append(
            EvidenceItem(
                text=(
                    f"Mean annual rain_best ≈ {rain['rain_annual_mm']:.0f} mm"
                    + (f" ({period})" if period else "")
                ),
                source=str(src),
            )
        )
    trend = features.get("grace_trend_cm_per_yr")
    if trend is not None and trend < 0:
        evidence.append(
            EvidenceItem(
                text=(
                    f"Regional water storage falling {abs(trend):.1f} cm/yr (GRACE-FO)"
                ),
                source="GRACE/FO Mascon CRI",
            )
        )
        _ = grace_groundwater_penalty(features)
    if frost.get("frost_free_days") is not None:
        evidence.append(
            EvidenceItem(
                text=f"Frost-free period ≈ {frost['frost_free_days']:.0f} days",
                source="NASA POWER T2M_MIN",
            )
        )
    if erisk is not None:
        evidence.append(
            EvidenceItem(
                text=f"Erosion risk index ≈ {erisk:.2f} (0–1)",
                source="SRTM slope + rain extremes + bare months",
            )
        )
    if anomalies and anomalies.get("vulnerable_seasons"):
        top = anomalies["vulnerable_seasons"][0]
        evidence.append(
            EvidenceItem(
                text=(
                    f"Growing-season anomaly: calendar month {top['calendar_month']} "
                    f"({top['n_flags']} times)"
                ),
                source="IsolationForest SI",
            )
        )
    if not evidence:
        evidence.append(
            EvidenceItem(text="Limited field evidence available", source="data coverage")
        )

    benefits = []
    if any(crop_by_id(c)["nitrogen_fixing"] for c in seq):
        benefits.append("Includes a nitrogen-fixing crop")
    if any(crop_by_id(c)["type"] == "cover" for c in seq):
        benefits.append("Winter/off-season ground cover")
    if len({crop_by_id(c)["family"] for c in seq}) >= 2:
        benefits.append("More than one plant family in the rotation")
    if scores.water >= 0.65:
        benefits.append("Water demand aligns with local rainfall")
    if not benefits:
        benefits.append("Maintains familiar cash-crop economics")

    data_gaps = list(features.get("feature_data_gaps") or [])
    cov = features.get("data_coverage", {}).get("per_variable") or []
    for row in cov:
        if row.get("n_gaps", 0) > 0 and row.get("variable") in {
            "ndvi_s2",
            "grace_lwe_cm",
            "rain_mm",
        }:
            data_gaps.append(
                f"{row['variable']}: {row['n_gaps']} gap months "
                f"(data through {row.get('data_through')})"
            )
    if anomalies and anomalies.get("uncertainty"):
        data_gaps.append(anomalies["uncertainty"])
    if not data_gaps:
        data_gaps.append("GAEZ suitability and US SSURGO modules not applied yet")

    risks = [
        "Check local seed availability and herbicide carryover",
        "Confirm planting windows with a local agronomist",
    ]
    if any(crop_by_id(c).get("needs_expert_review") for c in seq):
        risks.append("Crop parameter values need local expert review")
    if "cotton" in seq or "rice" in seq:
        risks.append("Crop may be poorly adapted — double-check climate filter")

    return {
        "why": why,
        "evidence": evidence,
        "benefits": benefits,
        "data_gaps": data_gaps,
        "risks_for_local_review": risks,
        "display_name": " → ".join(names),
    }
