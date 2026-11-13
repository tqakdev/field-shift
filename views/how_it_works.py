"""How it works: sources, scoring preview, SI model, limitations, glossary."""

from __future__ import annotations

import streamlit as st
from fieldshift.services import list_sources, using_mock_data
from ui.mock_banner import show_mock_banner

if using_mock_data():
    show_mock_banner()

st.title("How it works")
st.write(
    "Field Shift combines NASA and partner Earth observations with your rotation, soil, "
    "and priorities to compare crop-rotation strategies. It supports decisions — it does "
    "not replace local expertise."
)

st.header("Pipeline")
st.markdown(
    """
1. Reduce satellite & weather datasets to field × month values.
2. Derive bare months, stress months, frost window, water balance, trends.
3. Flag unusual seasons with an IsolationForest anomaly model (“SI”).
4. Generate rotation candidates (current + cover + swaps).
5. Score water, soil health, erosion, pest break, climate fit, income.
6. Explain each card with evidence tagged by dataset source.
"""
)

st.header("Data sources")
sources = list_sources()
st.dataframe(
    [
        {
            "Purpose": s.purpose,
            "Dataset": s.name,
            "ID / access": s.id_or_access,
            "Resolution": s.resolution,
            "Link": s.link,
        }
        for s in sources
    ],
    use_container_width=True,
    hide_index=True,
)

st.header("Scoring (preview)")
st.write(
    "Each criterion is 0–1. Total is a weighted mean of the priority sliders. "
    "Full formulas land in Phase 3 engine docstrings. Phase 1 scores are MOCK placeholders."
)

st.header("SI anomaly model")
st.write(
    "We fit an IsolationForest on field-month features (NDVI, soil moisture, rain, water "
    "balance, heat anomalies). Flagged months become “vulnerable seasons.” The model finds "
    "unusual patterns — not causes. Uncertainty (contamination, years used) is shown with "
    "results when the engine is live."
)

st.header("Limitations")
st.markdown(
    """
- Phase 1 UI uses labelled MOCK data with obviously round numbers.
- Satellite pixels are not the same as a soil probe or rain gauge on your field.
- Crop table values are typical published ranges — they need local expert review.
- If time runs short, cut in this order (never the SI model or evidence tagging):
  (a) Punjab demo field, (b) live analysis of newly drawn fields, (c) timelapse,
  (d) docker-compose polish, (e) About / How-it-works page depth.
"""
)

st.header("Glossary")
glossary = {
    "NDVI": "Normalized Difference Vegetation Index — green plant cover from satellites.",
    "Evapotranspiration (ET)": "Water leaving land as evaporation + plant transpiration.",
    "Soil-moisture anomaly": "How wet/dry soil is vs the usual value for that calendar month.",
    "Water balance": "Precipitation minus potential ET; negative means a deficit.",
    "Frost-free days": "Days between last spring frost and first autumn frost (Tmin ≤ 0 °C).",
    "GDD": "Growing Degree Days — heat accumulation above a crop base temperature.",
    "Cover crop": "Grown mainly to protect and improve soil between cash crops.",
    "Nitrogen fixation": "Legumes convert atmospheric N into plant-available forms.",
}
for term, definition in glossary.items():
    st.markdown(f"**{term}** — {definition}")
