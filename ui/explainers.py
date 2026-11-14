"""Plain-language orientation labels for scores, metrics, and charts."""

from __future__ import annotations

from typing import Any

# Criterion → what the score measures (farmer-facing)
CRITERION_HELP: dict[str, dict[str, str]] = {
    "water": {
        "label": "Water",
        "short": "How well the rotation matches available water",
        "detail": (
            "Higher is better. Scores how crop water needs line up with rainfall "
            "and your irrigation access (rainfed / limited / irrigated)."
        ),
    },
    "soil_health": {
        "label": "Soil health",
        "short": "Cover crops, legumes, and rotation diversity",
        "detail": (
            "Higher is better. Rewards living roots, nitrogen-fixing legumes, "
            "and more plant families in the rotation."
        ),
    },
    "erosion": {
        "label": "Erosion",
        "short": "Protection of bare soil from wash-off",
        "detail": (
            "Higher is better. Considers slope, heavy rain, and months when the "
            "field is usually bare (no living cover)."
        ),
    },
    "pest_break": {
        "label": "Pest break",
        "short": "Breaking pest and disease cycles",
        "detail": (
            "Higher is better. Changing plant families between seasons makes it "
            "harder for pests and diseases to carry over."
        ),
    },
    "climate_fit": {
        "label": "Climate fit",
        "short": "Match to frost-free season and heat",
        "detail": (
            "Higher is better. Checks whether crop seasons fit frost-free days "
            "and heat stress on this field."
        ),
    },
    "income": {
        "label": "Income",
        "short": "Relative harvest / market potential",
        "detail": (
            "Higher is better, but approximate. A coarse proxy for yield and "
            "market value — not a farm budget. Check locally."
        ),
    },
    "total": {
        "label": "Overall score",
        "short": "Weighted average of the six criteria",
        "detail": (
            "0–1 scale. Combines the six scores using your priority sliders. "
            "A higher total means a better match for what you said matters most."
        ),
    },
}

# Field fact chips → orientation
FACT_HELP: dict[str, str] = {
    "bare": (
        "Months when satellites usually see little green cover. Bare soil is "
        "more exposed to erosion and is a window for cover crops."
    ),
    "frost": (
        "Days between last spring frost and first autumn frost. Longer windows "
        "support more crop choices and cover-crop windows."
    ),
    "rain": (
        "Typical yearly rainfall over the field (mm). Compare to crop water "
        "needs; rainfed farms feel this number most."
    ),
    "grace": (
        "Trend in regional underground water storage from GRACE satellites. "
        "Negative means the wider region is losing water over time — context, "
        "not a well measurement on your farm."
    ),
}


def score_band(value: float | None) -> tuple[str, str]:
    """Return (band label, plain meaning) for a 0–1 score."""
    if value is None:
        return "—", "No score available"
    v = float(value)
    if v >= 0.75:
        return "Strong", "Looks favorable for this criterion"
    if v >= 0.55:
        return "Good", "Solid — room to improve with your priorities"
    if v >= 0.35:
        return "Fair", "Mixed — worth reviewing the evidence"
    return "Needs attention", "Weak for this criterion — check risks and data gaps"


def format_score_line(key: str, value: float) -> dict[str, Any]:
    """Build a display row for one criterion score."""
    meta = CRITERION_HELP.get(key, {"label": key, "short": "", "detail": ""})
    band, band_meaning = score_band(value)
    pct = int(round(max(0.0, min(1.0, value)) * 100))
    return {
        "key": key,
        "label": meta["label"],
        "value": value,
        "pct": pct,
        "band": band,
        "band_meaning": band_meaning,
        "short": meta["short"],
        "detail": meta["detail"],
        "display": f"{value:.2f} · {pct}%",
        "orientation": (
            f"{meta['label']} is {value:.2f} ({pct}%). "
            f"{band}: {meta['short']}."
        ),
    }


def total_orientation(total: float, delta: float | None) -> str:
    """One-line meaning for the overall score + delta vs current."""
    band, _ = score_band(total)
    base = f"Overall {total:.2f} of 1.00 — {band.lower()} match for your priorities."
    if delta is None:
        return base
    if abs(delta) < 0.005:
        return base + " About the same as your current rotation."
    if delta > 0:
        return base + f" About {delta:+.2f} better than your current rotation."
    return base + f" About {abs(delta):.2f} weaker than your current rotation."


def confidence_orientation(level: str) -> str:
    """Explain confidence badges."""
    level = (level or "medium").lower()
    mapping = {
        "high": "Data coverage is strong and the SI model is stable for this field.",
        "medium": "Useful guidance, but some data gaps or uncertainty remain — review locally.",
        "low": "Limited evidence or high uncertainty — treat as exploratory only.",
    }
    return mapping.get(level, mapping["medium"])


def chart_how_to_read() -> str:
    return (
        "**Plant greenness (NDVI)** — how leafy the field looks from space (0–1). "
        "Higher in the growing season, lower when bare or dormant.\n\n"
        "**Rain (bars)** — typical monthly rainfall in millimeters.\n\n"
        "**Water balance (dashed)** — rain minus evaporative demand. Negative = "
        "the atmosphere is pulling more water than rain supplies that month.\n\n"
        "**Shaded months** — tan ≈ usually bare soil; light red ≈ growing-season stress."
    )
