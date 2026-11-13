"""Field view: conditions, timelapse, farmer inputs, strategies, what-if."""

from __future__ import annotations

import streamlit as st
from fieldshift.models import PriorityWeights, ScenarioParams, StrategyRequest
from fieldshift.services import (
    generate_strategies,
    get_timelapse,
    list_crops,
    load_demo_conditions,
    using_mock_data,
)
from streamlit_folium import st_folium
from ui.charts import conditions_figure
from ui.map import field_map
from ui.mock_banner import show_mock_banner
from ui.source_caption import source_caption
from ui.strategy_cards import render_strategy_cards

if using_mock_data():
    show_mock_banner()

field_id = st.session_state.get("field_id", "iowa")
st.title(f"Field: {field_id}")

try:
    conditions = load_demo_conditions(field_id)
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

st.session_state.setdefault("current_rotation", ["maize", "soybean"])
st.session_state.setdefault("soil_type", "loam")
st.session_state.setdefault("water_access", "rainfed")
st.session_state.setdefault("livestock", False)
st.session_state.setdefault("rain_mult", 1.0)
st.session_state.setdefault("temp_offset", 0.0)

st.header("Your field")
st.write(f"**{conditions.name}** — {conditions.climate_label}")
fmap = field_map(conditions.polygon)
st_folium(fmap, width=None, height=360, key=f"field-map-{field_id}")

tl = get_timelapse(field_id)
if tl.get("path"):
    st.image(tl["path"], caption=f"Timelapse — {conditions.name}")
else:
    st.info(tl.get("message", "Timelapse not available yet."))

st.header("Conditions")
st.plotly_chart(conditions_figure(conditions), use_container_width=True)
source_caption("MOCK / multi-source monthly profile")

feat = conditions.features
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(
        "Frost-free days",
        feat.frost_free_days if feat.frost_free_days is not None else "—",
    )
    source_caption("MOCK / NASA POWER")
with c2:
    st.metric("Rain (mm/yr)", feat.rain_annual_mm if feat.rain_annual_mm is not None else "—")
    source_caption("MOCK / IMERG")
with c3:
    st.metric("Rain CV", feat.rain_cv if feat.rain_cv is not None else "—")
    source_caption("MOCK / IMERG")
with c4:
    st.metric("Slope %", feat.slope_pct_mean if feat.slope_pct_mean is not None else "—")
    source_caption("MOCK / SRTM")
st.caption(feat.bare_months_label)
source_caption("MOCK / Sentinel-2")
st.caption(feat.stress_months_label)
st.caption(feat.heat_days_trend)

st.header("About your farm")
crops = list_crops()
crop_ids = [c.id for c in crops]
crop_labels = {c.id: c.name for c in crops}

rot = st.session_state["current_rotation"]
new_rot: list[str] = []
for i, crop_id in enumerate(rot):
    choice = st.selectbox(
        f"Rotation crop {i + 1}",
        crop_ids,
        index=crop_ids.index(crop_id) if crop_id in crop_ids else 0,
        format_func=lambda x: crop_labels.get(x, x),
        key=f"rot-{i}",
    )
    new_rot.append(choice)
st.session_state["current_rotation"] = new_rot

st.session_state["soil_type"] = st.selectbox(
    "Soil type",
    ["sand", "loam", "clay", "silt", "unknown"],
    index=["sand", "loam", "clay", "silt", "unknown"].index(st.session_state["soil_type"]),
)
st.session_state["water_access"] = st.radio(
    "Water access",
    ["rainfed", "limited", "irrigated"],
    index=["rainfed", "limited", "irrigated"].index(st.session_state["water_access"]),
    horizontal=True,
)
st.session_state["livestock"] = st.checkbox(
    "I have livestock",
    value=st.session_state["livestock"],
)

st.subheader("Your priorities")
w_keys = ["water", "soil_health", "erosion", "pest_break", "climate_fit", "income"]
weights: dict[str, float] = {}
for key in w_keys:
    weights[key] = st.slider(
        key.replace("_", " ").title(), 0.0, 2.0, 1.0, 0.1, key=f"w-{key}"
    )

st.header("Options")


def _render_options() -> None:
    st.session_state["rain_mult"] = st.slider(
        "Rainfall change (multiplier)",
        0.7,
        1.3,
        float(st.session_state["rain_mult"]),
        0.05,
    )
    st.session_state["temp_offset"] = st.slider(
        "Temperature offset (°C)",
        0.0,
        3.0,
        float(st.session_state["temp_offset"]),
        0.5,
    )
    req = StrategyRequest(
        current_rotation=st.session_state["current_rotation"],
        soil_type=st.session_state["soil_type"],
        water_access=st.session_state["water_access"],
        livestock=st.session_state["livestock"],
        weights=PriorityWeights(**weights),
        scenario=ScenarioParams(
            rain_mult=st.session_state["rain_mult"],
            temp_offset=st.session_state["temp_offset"],
        ),
    )
    result = generate_strategies(field_id, req)
    render_strategy_cards(result.strategies)
    st.caption(
        "Phase 1: what-if sliders update session state; "
        "live re-score formulas arrive in Phase 3."
    )


if hasattr(st, "fragment"):

    @st.fragment  # type: ignore[attr-defined]
    def options_fragment() -> None:
        _render_options()

    options_fragment()
else:
    _render_options()
