"""Field view: conditions, timelapse, farmer inputs, strategies, what-if."""

from __future__ import annotations

import streamlit as st
from fieldshift.models import (
    FieldConditions,
    PriorityWeights,
    ScenarioParams,
    StrategyRequest,
)
from fieldshift.services import (
    demo_data_through,
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


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_conditions(field_id: str) -> FieldConditions:
    """Load demo FieldConditions from committed cache (fast)."""
    return load_demo_conditions(field_id)


if using_mock_data():
    show_mock_banner()

field_id = st.session_state.get("field_id", "iowa")
st.title(f"Field: {field_id}")

# Live custom analysis result may already be in session
if field_id == "custom" and st.session_state.get("custom_conditions"):
    conditions = st.session_state["custom_conditions"]
else:
    try:
        conditions = _cached_conditions(field_id)
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()

_DEFAULT_ROTATION = {
    "iowa": ["maize", "soybean"],
    "kansas": ["winter_wheat"],
    "punjab": ["rice", "winter_wheat"],
    "custom": ["maize", "soybean"],
}
_DEFAULT_WATER = {
    "iowa": "rainfed",
    "kansas": "rainfed",
    "punjab": "irrigated",
    "custom": "rainfed",
}

if (
    "current_rotation" not in st.session_state
    or st.session_state.get("_rotation_field") != field_id
):
    st.session_state["current_rotation"] = list(
        _DEFAULT_ROTATION.get(field_id, ["maize", "soybean"])
    )
    st.session_state["_rotation_field"] = field_id
st.session_state.setdefault("soil_type", "loam")
st.session_state.setdefault(
    "water_access", _DEFAULT_WATER.get(field_id, "rainfed")
)
st.session_state.setdefault("livestock", False)
st.session_state.setdefault("rain_mult", 1.0)
st.session_state.setdefault("temp_offset", 0.0)

ndvi_through = demo_data_through(field_id, "ndvi_s2")
rain_through = demo_data_through(field_id, "rain_best_mm")
power_through = demo_data_through(field_id, "power_t2m_c")

st.header("Your field")
st.write(f"**{conditions.name}** — {conditions.climate_label}")
fmap = field_map(conditions.polygon)
st_folium(fmap, width=None, height=360, key=f"field-map-{field_id}")

tl_cols = st.columns(2)
with tl_cols[0]:
    tl = get_timelapse(field_id, index="ndvi")
    if tl.get("path"):
        st.image(tl["path"], caption=f"NDVI timelapse — {conditions.name}")
        source_caption("Sentinel-2 NDVI", ndvi_through)
    else:
        st.info(tl.get("message", "NDVI timelapse not available yet."))
with tl_cols[1]:
    tl_rgb = get_timelapse(field_id, index="rgb")
    if tl_rgb.get("path"):
        st.image(tl_rgb["path"], caption=f"RGB timelapse — {conditions.name}")
        source_caption("Sentinel-2 RGB", ndvi_through)
    else:
        st.caption("RGB timelapse not available yet.")

st.header("Conditions")
st.plotly_chart(conditions_figure(conditions), use_container_width=True)
source_caption("Sentinel-2 / SMAP / rain_best / water balance", rain_through)

feat = conditions.features
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(
        "Frost-free days",
        f"{feat.frost_free_days:.0f}" if feat.frost_free_days is not None else "—",
    )
    source_caption("NASA POWER T2M_MIN", power_through)
with c2:
    st.metric(
        "Rain (mm/yr)",
        f"{feat.rain_annual_mm:.0f}" if feat.rain_annual_mm is not None else "—",
    )
    source_caption("rain_best (POWER / IMERG)", rain_through)
with c3:
    st.metric(
        "Rain CV",
        f"{feat.rain_cv:.2f}" if feat.rain_cv is not None else "—",
    )
    source_caption("rain_best", rain_through)
with c4:
    st.metric(
        "Slope %",
        f"{feat.slope_pct_mean:.1f}" if feat.slope_pct_mean is not None else "—",
    )
    source_caption("SRTM")
st.caption(feat.bare_months_label)
source_caption("Sentinel-2 NDVI", ndvi_through)
st.caption(feat.stress_months_label)
st.caption(feat.heat_days_trend)
st.caption(feat.data_coverage_note)

st.header("About your farm")
crops = list_crops()
crop_ids = [c.id for c in crops]
crop_labels = {c.id: c.name for c in crops}

rot = st.session_state["current_rotation"]
new_rot: list[str] = []
n_slots = max(len(rot), 1)
for i in range(n_slots):
    crop_id = rot[i] if i < len(rot) else crop_ids[0]
    choice = st.selectbox(
        f"Rotation crop {i + 1}",
        crop_ids,
        index=crop_ids.index(crop_id) if crop_id in crop_ids else 0,
        format_func=lambda x: crop_labels.get(x, x),
        key=f"rot-{field_id}-{i}",
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
        key.replace("_", " ").title(), 0.0, 2.0, 1.0, 0.1, key=f"w-{field_id}-{key}"
    )

st.header("Options")
st.caption(
    "Priority and what-if sliders re-score from cached features only "
    "(no Earth Engine re-extract)."
)


def _render_options() -> None:
    st.session_state["rain_mult"] = st.slider(
        "Rainfall change (multiplier)",
        0.7,
        1.3,
        float(st.session_state["rain_mult"]),
        0.05,
        key=f"rain-{field_id}",
    )
    st.session_state["temp_offset"] = st.slider(
        "Temperature offset (°C)",
        0.0,
        3.0,
        float(st.session_state["temp_offset"]),
        0.5,
        key=f"temp-{field_id}",
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


if hasattr(st, "fragment"):

    @st.fragment  # type: ignore[attr-defined]
    def options_fragment() -> None:
        _render_options()

    options_fragment()
else:
    _render_options()
