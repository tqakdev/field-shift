"""Shared plain-language terms — one wording per concept app-wide."""

from __future__ import annotations

GLOSSARY: dict[str, str] = {
    "NDVI": "Plant greenness from satellites (0–1). Higher means more leafy cover.",
    "Evapotranspiration (ET)": (
        "Water leaving land as evaporation plus plant transpiration."
    ),
    "Soil-moisture anomaly": (
        "How wet or dry soil is versus the usual value for that calendar month."
    ),
    "Water balance": (
        "Rainfall minus potential ET; negative means a water deficit that month."
    ),
    "Frost-free days": (
        "Days between last spring frost and first autumn frost (night lows ≤ 0 °C)."
    ),
    "GDD": "Growing degree days — heat accumulation used for crop development.",
    "Cover crop": "A crop grown mainly to protect soil, not for harvest income.",
    "N fixation": (
        "Legumes converting atmospheric nitrogen into forms plants can use."
    ),
    "Best fit": (
        "Highest overall score that beats your current rotation and passes "
        "hard farm constraints."
    ),
    "Worth considering": (
        "Passes constraints; near the best option or stronger on your top priority."
    ),
    "Your rotation today": "The rotation you said you grow now — the baseline.",
    "Not suitable here": (
        "Fails a hard constraint or scores clearly below your current rotation."
    ),
}

# Preferred display labels (avoid internal ids / underscores in UI copy)
SOURCE_LABELS: dict[str, str] = {
    "rain_best": "Best available rainfall",
    "ndvi_s2": "Sentinel-2 plant greenness",
    "grace_lwe_cm": "GRACE water storage",
    "power_t2m_c": "NASA POWER temperature",
}
