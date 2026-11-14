"""Farmer-facing strategy-card copy helpers (pure, unit-tested)."""

from __future__ import annotations

from typing import Any

from fieldshift.engine.thresholds import DELTA_NEUTRAL_THRESHOLD

SCORE_KEYS = (
    "water",
    "soil_health",
    "erosion",
    "pest_break",
    "climate_fit",
    "income",
)

_LABELS = {
    "water": "Water",
    "soil_health": "Soil health",
    "erosion": "Erosion",
    "pest_break": "Pest break",
    "climate_fit": "Climate fit",
    "income": "Income",
}

_FRIENDLY = {
    "water": "water match",
    "soil_health": "soil health",
    "erosion": "erosion protection",
    "pest_break": "pest break",
    "climate_fit": "climate fit",
    "income": "income potential",
}


def _band_word(value: float) -> str:
    """Documented bands: Strong ≥0.75, Good ≥0.55, Fair ≥0.35, else Weak."""
    v = float(value)
    if v >= 0.75:
        return "Strong"
    if v >= 0.55:
        return "Good"
    if v >= 0.35:
        return "Fair"
    return "Weak"


def format_delta_label(
    delta: float | None,
    *,
    threshold: float = DELTA_NEUTRAL_THRESHOLD,
) -> tuple[str, str]:
    """Return (display text, tone) for overall delta vs current rotation.

    tone is one of: neutral | up | down
    """
    if delta is None:
        return "Compared to yours", "neutral"
    if abs(float(delta)) < threshold:
        return "About the same as yours", "neutral"
    d = float(delta)
    if d > 0:
        return f"+{d:.2f} vs yours", "up"
    return f"{d:.2f} vs yours", "down"


def top_criterion_diffs(
    scores: Any,
    baseline_scores: Any | None,
    *,
    n: int = 3,
) -> list[dict[str, Any]]:
    """Return the n criteria with largest |delta| vs baseline.

    Each item: key, label, delta, pct (0–100), direction ('better'|'worse'|'same'),
    band word for the option's absolute score.
    """
    rows: list[dict[str, Any]] = []
    for key in SCORE_KEYS:
        val = float(getattr(scores, key))
        base = (
            float(getattr(baseline_scores, key))
            if baseline_scores is not None
            else val
        )
        delta = val - base
        band = _band_word(val)
        direction = (
            "better" if delta > 0.005 else ("worse" if delta < -0.005 else "same")
        )
        rows.append(
            {
                "key": key,
                "label": _LABELS[key],
                "delta": delta,
                "pct": int(round(max(0.0, min(1.0, val)) * 100)),
                "direction": direction,
                "band": band,
                "friendly": _FRIENDLY[key],
            }
        )
    rows.sort(key=lambda r: abs(r["delta"]), reverse=True)
    return rows[:n]


def farmer_comparison_sentence(
    diffs: list[dict[str, Any]],
    *,
    overall_delta: float | None,
    threshold: float = DELTA_NEUTRAL_THRESHOLD,
) -> str:
    """One plain sentence from criterion diffs — never engine jargon."""
    meaningful = [d for d in diffs if d["direction"] != "same"]
    better = [d for d in meaningful if d["direction"] == "better"]
    worse = [d for d in meaningful if d["direction"] == "worse"]

    overall_close = overall_delta is None or abs(float(overall_delta)) < threshold

    def _join(items: list[dict[str, Any]]) -> str:
        names = [d["friendly"] for d in items[:2]]
        if len(names) == 1:
            return names[0]
        return f"{names[0]} and {names[1]}"

    if overall_close and not meaningful:
        return "Similar overall to your rotation on the measures that matter most."
    if overall_close and better and not worse:
        return (
            f"Similar overall to your rotation, with better {_join(better)}."
        )
    if overall_close and better and worse:
        return (
            f"Similar overall to your rotation, with better {_join(better)} "
            f"and slightly lower {_join(worse)}."
        )
    if overall_close and worse and not better:
        return (
            f"Similar overall to your rotation, with slightly lower {_join(worse)}."
        )
    if better and worse:
        return (
            f"Better {_join(better)} than your rotation, "
            f"with a trade-off on {_join(worse)}."
        )
    if better:
        return f"Stronger than your rotation on {_join(better)}."
    if worse:
        return f"Weaker than your rotation on {_join(worse)}."
    return "A close alternative to your current rotation."


_SEASON_PREFIX = (
    "summer ",
    "winter ",
    "spring ",
    "autumn ",
    "fall ",
    "kharif ",
    "rabi ",
)


def _clean_months(months: str) -> str:
    s = months.strip()
    low = s.lower()
    for prefix in _SEASON_PREFIX:
        if low.startswith(prefix):
            return s[len(prefix) :].strip()
    return s


def rotation_title_line(sequence: list[Any]) -> str:
    """One-line rotation with months: 'Maize (May–Oct) → Soybean (May–Oct)'."""
    parts: list[str] = []
    for slot in sequence:
        crop = getattr(slot, "crop_id", None) or (
            slot.get("crop_id") if isinstance(slot, dict) else "?"
        )
        months = getattr(slot, "months", None) or (
            slot.get("months") if isinstance(slot, dict) else ""
        )
        name = str(crop).replace("_", " ").title()
        # Cover crops: keep short "cover" cue when type is in the id/name
        if "cover" in str(crop).lower() and "cover" not in name.lower():
            name = f"{name} cover"
        months_s = _clean_months(str(months)) if months else ""
        if months_s:
            parts.append(f"{name} ({months_s})")
        else:
            parts.append(name)
    return " → ".join(parts)
