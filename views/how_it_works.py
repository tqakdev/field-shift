"""How it works: pipeline, sources, scoring, SI, glossary."""

from __future__ import annotations

import streamlit as st
from fieldshift.cache import read_json
from fieldshift.engine import thresholds as th
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
- **Water** — crop water demand vs rain / irrigation access (+ irrigation-event lift)  
- **Soil health** — cover, legumes, diversity (+ N-fertilizer context when legumes present)  
- **Erosion** — slope, rain extremes, bare months  
- **Pest break** — family breaks in the rotation  
- **Climate fit** — season length / heat vs crop needs  
- **Income** — relative price tier × yield potential, adjusted for market access  
"""
)

section("Decision thresholds")
st.write(
    "Documented constants in `fieldshift/engine/thresholds.py` "
    "(used for tiered cards):"
)
st.dataframe(
    [
        {
            "Constant": "BEST_FIT_MIN_DELTA",
            "Value": th.BEST_FIT_MIN_DELTA,
            "Meaning": "Best fit must beat current by at least this",
        },
        {
            "Constant": "WORTH_CONSIDERING_OF_BEST",
            "Value": th.WORTH_CONSIDERING_OF_BEST,
            "Meaning": "Near-best band for Worth considering",
        },
        {
            "Constant": "NOT_SUITABLE_TOTAL_DELTA",
            "Value": th.NOT_SUITABLE_TOTAL_DELTA,
            "Meaning": "Below current by this → Not suitable",
        },
        {
            "Constant": "BUDGET_LOW_COVER_PENALTY",
            "Value": th.BUDGET_LOW_COVER_PENALTY,
            "Meaning": "Soft penalty: low seed budget + cover",
        },
        {
            "Constant": "LABOR_LOW_COVER_PENALTY",
            "Value": th.LABOR_LOW_COVER_PENALTY,
            "Meaning": "Soft penalty: low labor + cover",
        },
        {
            "Constant": "MARKET_BUYER_INCOME_LIFT",
            "Value": th.MARKET_BUYER_INCOME_LIFT,
            "Meaning": "Income lift when I have a buyer",
        },
        {
            "Constant": "IRRIGATION_EVENT_WATER_LIFT",
            "Value": th.IRRIGATION_EVENT_WATER_LIFT,
            "Meaning": "Water lift per irrigation event",
        },
        {
            "Constant": "IRRIGATION_EVENT_WATER_CAP",
            "Value": th.IRRIGATION_EVENT_WATER_CAP,
            "Meaning": "Cap on irrigation-event lift",
        },
    ],
    use_container_width=True,
    hide_index=True,
)
st.markdown(
    """
**Tiers:** Best fit · Worth considering · Your rotation today · Not suitable here
(collapsed). Labels always include an icon + text — never color alone.
**Constraints** (machinery, market, labor, budget) do not change priority weights;
they exclude candidates or apply the soft penalties above.
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
