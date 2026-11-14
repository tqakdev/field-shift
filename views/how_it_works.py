"""How it works: pipeline, sources, scoring, SI, glossary."""

from __future__ import annotations

import streamlit as st
from fieldshift.cache import read_json
from fieldshift.services import list_sources, using_mock_data
from ui.charts import pipeline_figure
from ui.components import hero, section
from ui.mock_banner import show_mock_banner
from ui.source_caption import source_caption

if using_mock_data():
    show_mock_banner()

hero(
    "How it works",
    "Field Shift turns NASA and partner Earth observations into a rotation advisory "
    "you can check against local knowledge.",
    sub="Methods, data provenance, and limitations — written for farmers and judges.",
    mode_label="Methods & data",
    live=True,
    eyebrow="Mission documentation",
)

section("Pipeline")
st.plotly_chart(
    pipeline_figure(), use_container_width=True, config={"displayModeBar": False}
)
st.markdown(
    """
1. Reduce satellite & weather datasets to **field × month** values.  
2. Derive bare months, stress months, frost window, water balance, trends.  
3. Flag unusual seasons with an IsolationForest anomaly model (**SI**).  
4. Generate rotation candidates (current + cover + swaps).  
5. Score water, soil health, erosion, pest break, climate fit, income.  
6. Explain each card with evidence tagged by dataset source.  
"""
)

section("Data sources")
sources = list_sources()
iowa = read_json("demo_iowa.json", from_mock=False) or {}
through = iowa.get("data_through") or {}
rows = []
for s in sources:
    rows.append(
        {
            "Purpose": s.purpose,
            "Dataset": s.name,
            "ID / access": s.id_or_access,
            "Resolution": s.resolution,
            "Data through (Iowa demo)": through.get("ndvi_s2", "see demo cache"),
            "Link": s.link,
        }
    )
st.dataframe(rows, use_container_width=True, hide_index=True)
source_caption("Demo field cache · Iowa", through.get("ndvi_s2"))

section("Scoring")
st.write(
    "Each criterion is 0–1. Total is a weighted mean of your priority sliders. "
    "Formulas live in `fieldshift/engine/scoring.py`. Priority and what-if sliders "
    "only re-score — they never re-extract Earth Engine data."
)
st.markdown(
    """
- **Water** — crop water demand vs rain / irrigation access  
- **Soil health** — cover, legumes, diversity  
- **Erosion** — slope, rain extremes, bare months  
- **Pest break** — family breaks in the rotation  
- **Climate fit** — season length / heat vs crop needs  
- **Income** — coarse relative yield / market proxy  
"""
)

section("SI anomaly model")
st.write(
    "We fit an IsolationForest on field-month features (NDVI, soil moisture, rain, "
    "water balance, heat anomalies). Flagged months become “vulnerable seasons.” "
    "The model finds unusual patterns — not causes. Uncertainty (contamination, years "
    "used) is shown with confidence badges."
)

section("Satellite vs ground data")
st.write(
    "A satellite pixel averages tens of meters; a rain gauge or soil probe measures "
    "one point. We harmonize datasets onto a common monthly field mean and show "
    "cross-checks (e.g. IMERG vs POWER rain) so you can see where sensors agree."
)

section("Limitations")
st.markdown(
    """
- Satellite pixels are not the same as a soil probe or rain gauge on your field.  
- Crop table values are typical published ranges — they need local expert review.  
- Live analysis of newly drawn fields needs Earth Engine credentials and ~60 s.  
- Demo fields load instantly from committed cache (no credentials required).  
"""
)

section("Glossary")
glossary = {
    "NDVI": "Normalized Difference Vegetation Index — green plant cover from satellites.",
    "Evapotranspiration (ET)": "Water leaving land as evaporation + plant transpiration.",
    "Soil-moisture anomaly": "How wet/dry soil is vs the usual value for that calendar month.",
    "Water balance": "Precipitation minus potential ET; negative means a deficit.",
    "Frost-free days": "Days between last spring frost and first autumn frost (Tmin ≤ 0 °C).",
    "GDD": "Growing Degree Days — heat accumulation for crop development.",
    "Cover crop": "A crop grown to protect soil, not primarily for harvest.",
    "N fixation": "Legumes converting atmospheric nitrogen into plant-available forms.",
}
for term, definition in glossary.items():
    st.markdown(f"**{term}** — {definition}")

section("Team & AI use")
st.write(
    "Built for NASA Space Apps Challenge 2026. See `AI_USAGE.md` for how AI assisted "
    "implementation. Human experts remain responsible for agronomic decisions."
)
