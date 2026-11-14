"""Field view: numbered advisory-report story."""

from __future__ import annotations

import io
from pathlib import Path

import streamlit as st
from fieldshift.cache import read_json
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
    get_validation,
    list_crops,
    load_demo_conditions,
    using_mock_data,
)
from PIL import Image
from streamlit_folium import st_folium
from ui.charts import conditions_figure
from ui.components import (
    fact_chips,
    recommendation_banner,
    section,
    weights_bar,
)
from ui.map import field_map
from ui.mock_banner import show_mock_banner
from ui.source_caption import source_caption
from ui.strategy_cards import render_strategy_cards

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
_MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_conditions(field_id: str) -> FieldConditions:
    return load_demo_conditions(field_id)


@st.cache_data(show_spinner=False)
def _gif_png_frames(path: str) -> list[bytes]:
    im = Image.open(path)
    out: list[bytes] = []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="PNG")
        out.append(buf.getvalue())
    return out


def _demo_payload(field_id: str) -> dict:
    return read_json(f"demo_{field_id}.json", from_mock=False) or {}


if using_mock_data():
    show_mock_banner()

field_id = st.session_state.get("field_id", "iowa")

if field_id == "custom" and st.session_state.get("custom_conditions"):
    conditions = st.session_state["custom_conditions"]
else:
    try:
        conditions = _cached_conditions(field_id)
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()

if (
    "current_rotation" not in st.session_state
    or st.session_state.get("_rotation_field") != field_id
):
    st.session_state["current_rotation"] = list(
        _DEFAULT_ROTATION.get(field_id, ["maize", "soybean"])
    )
    st.session_state["_rotation_field"] = field_id
st.session_state.setdefault("soil_type", "loam")
st.session_state.setdefault("water_access", _DEFAULT_WATER.get(field_id, "rainfed"))
st.session_state.setdefault("livestock", False)
st.session_state.setdefault("rain_mult", 1.0)
st.session_state.setdefault("temp_offset", 0.0)

payload = _demo_payload(field_id)
ndvi_through = demo_data_through(field_id, "ndvi_s2")
rain_through = demo_data_through(field_id, "rain_best_mm")
grace_through = demo_data_through(field_id, "grace_lwe_cm")
power_through = demo_data_through(field_id, "power_t2m_c")
feat = conditions.features
grace = (payload.get("coverage") or {}).get("grace_trend") or {}
grace_cm = grace.get("trend_cm_per_yr")
grace_label = (
    f"{grace_cm:+.1f} cm/yr" if grace_cm is not None else (grace.get("detail") or "—")
)

st.title(conditions.name)
st.caption(f"{conditions.climate_label} · {conditions.country or 'Custom field'}")

# --- 1. Your field ---
section(
    "🛰 Your field",
    "Satellite view of the polygon and a year of Sentinel-2.",
    step=1,
)
c_map, c_tl = st.columns([1, 1])
with c_map:
    fmap = field_map(conditions.polygon)
    st_folium(fmap, width=None, height=360, key=f"field-map-{field_id}")
with c_tl:
    mode = st.radio(
        "Timelapse",
        ["ndvi", "rgb"],
        format_func=lambda x: "Plant greenness (NDVI)" if x == "ndvi" else "True color (RGB)",
        horizontal=True,
        key=f"tl-mode-{field_id}",
    )
    tl = get_timelapse(field_id, index=mode)
    if tl.get("path") and Path(tl["path"]).exists():
        frames = _gif_png_frames(tl["path"])
        st.image(tl["path"], caption=f"Sentinel-2 {mode.upper()} · autoplay")
        idx = st.slider(
            "Month frame",
            0,
            max(0, len(frames) - 1),
            0,
            key=f"tl-slider-{field_id}-{mode}",
        )
        st.image(frames[idx], use_container_width=True)
        source_caption(
            "Sentinel-2 NDVI" if mode == "ndvi" else "Sentinel-2 RGB",
            ndvi_through,
        )
    else:
        st.info(tl.get("message", "Timelapse not available yet."))

# --- 2. What the satellites see ---
section(
    "🌱 What the satellites see",
    "Key facts first, then the seasonal pattern.",
    step=2,
)
chips = [
    {
        "label": "Bare soil window",
        "value": feat.bare_months_label.split("(")[0].strip()
        if feat.bare_months_label
        else "—",
        "help": f"source: Sentinel-2 NDVI · data through {ndvi_through or '—'}",
    },
    {
        "label": "Frost-free days",
        "value": f"{feat.frost_free_days:.0f}" if feat.frost_free_days else "—",
        "help": f"source: NASA POWER T2M_MIN · data through {power_through or '—'}",
    },
    {
        "label": "Rain (mm/yr)",
        "value": f"≈ {feat.rain_annual_mm:.0f}" if feat.rain_annual_mm else "—",
        "help": f"source: rain_best · data through {rain_through or '—'}",
    },
    {
        "label": "Regional water storage",
        "value": grace_label,
        "help": f"source: GRACE/FO · data through {grace_through or '—'}",
    },
]
fact_chips(chips)

st.plotly_chart(conditions_figure(conditions), use_container_width=True)
st.caption(
    "Shaded brown months ≈ usually bare · light red ≈ growing-season stress. "
    "Legend: Plant greenness · Rain · Water balance."
)
source_caption("Sentinel-2 / SMAP / rain_best / water balance", rain_through)

anoms = payload.get("anomalies") or {}
with st.expander("🔍 Stress & anomalies (SI)"):
    vulns = anoms.get("vulnerable_seasons") or []
    if vulns:
        for v in vulns:
            m = v.get("calendar_month")
            label = _MONTHS[m - 1] if isinstance(m, int) and 1 <= m <= 12 else m
            st.write(
                f"• Calendar month **{label}** flagged "
                f"{v.get('n_flags', 1)}× in the record"
            )
    else:
        st.write("No recurring growing-season anomaly months in the SI output.")
    st.caption(feat.stress_months_label)
    if anoms.get("uncertainty"):
        st.info(anoms["uncertainty"])
    source_caption("IsolationForest SI model", ndvi_through)

# --- 3. About your farm ---
section(
    "🌾 About your farm",
    "Your rotation, soil, water, and what matters most.",
    step=3,
)
crops = list_crops()
crop_ids = [c.id for c in crops]
crop_labels = {c.id: c.name for c in crops}
left, right = st.columns(2)
with left:
    rot = st.session_state["current_rotation"]
    new_rot: list[str] = []
    for i in range(max(len(rot), 1)):
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
        index=["sand", "loam", "clay", "silt", "unknown"].index(
            st.session_state["soil_type"]
        ),
    )
with right:
    st.session_state["water_access"] = st.radio(
        "Water access",
        ["rainfed", "limited", "irrigated"],
        index=["rainfed", "limited", "irrigated"].index(
            st.session_state["water_access"]
        ),
    )
    st.session_state["livestock"] = st.checkbox(
        "I have livestock",
        value=st.session_state["livestock"],
    )

st.markdown("**What matters most to you?**")
w_meta = [
    ("water", "💧 Water"),
    ("soil_health", "🌱 Soil health"),
    ("erosion", "🛡 Erosion"),
    ("pest_break", "🐛 Pest break"),
    ("climate_fit", "🌤 Climate fit"),
    ("income", "💰 Income"),
]
w_cols = st.columns(3)
weights: dict[str, float] = {}
for i, (key, label) in enumerate(w_meta):
    with w_cols[i % 3]:
        weights[key] = st.slider(label, 0.0, 2.0, 1.0, 0.1, key=f"w-{field_id}-{key}")
weights_bar(weights)

# --- 4 + 5 Options / what-if (live re-score) ---
section(
    "🌾 Your options",
    "Scored for your priorities — updates as you move the sliders.",
    step=4,
)


def _options_block() -> None:
    climate_shifted = (
        abs(float(st.session_state["rain_mult"]) - 1.0) > 1e-6
        or float(st.session_state["temp_offset"]) > 1e-6
    )
    req = StrategyRequest(
        current_rotation=st.session_state["current_rotation"],
        soil_type=st.session_state["soil_type"],
        water_access=st.session_state["water_access"],
        livestock=st.session_state["livestock"],
        weights=PriorityWeights(**weights),
        scenario=ScenarioParams(
            rain_mult=float(st.session_state["rain_mult"]),
            temp_offset=float(st.session_state["temp_offset"]),
        ),
    )
    result = generate_strategies(field_id, req)
    cards = result.strategies
    if cards:
        top = next((c for c in cards if c.id != "current"), cards[0])
        delta_bit = (
            f", {top.delta_vs_current.get('total', 0):+.2f} vs your current rotation"
            if top.delta_vs_current.get("total") is not None
            else ""
        )
        why_bit = top.why.split(".")[0] + "." if top.why else ""
        recommendation_banner(
            f"<em>{top.name}</em> scores highest for your priorities "
            f"({top.scores.total:.2f}{delta_bit}). {why_bit}"
        )
        render_strategy_cards(cards, show_climate_delta=climate_shifted)

    section(
        "🌤 What if the climate shifts?",
        "Move the sliders — cards re-score from cached features only "
        "(no Earth Engine re-extract).",
        step=5,
    )
    st.session_state["rain_mult"] = st.slider(
        "💧 Rainfall change (multiplier)",
        0.7,
        1.3,
        float(st.session_state["rain_mult"]),
        0.05,
        key=f"rain-{field_id}",
    )
    st.session_state["temp_offset"] = st.slider(
        "🌤 Temperature offset (°C)",
        0.0,
        3.0,
        float(st.session_state["temp_offset"]),
        0.5,
        key=f"temp-{field_id}",
    )
    if climate_shifted:
        st.caption(
            f"Scenario applied above: rain ×{st.session_state['rain_mult']:.2f}, "
            f"temp +{st.session_state['temp_offset']:.1f} °C"
        )


if hasattr(st, "fragment"):

    @st.fragment  # type: ignore[attr-defined]
    def options_fragment() -> None:
        _options_block()

    options_fragment()
else:
    _options_block()

# --- 6. Reliability ---
section(
    "🔍 How reliable is this?",
    "Where the numbers come from, and where human judgment still matters.",
    step=6,
)
val = get_validation(field_id)
through = payload.get("data_through") or {}
if through:
    lines = [
        f"- **{k}**: data through {v}"
        for k, v in list(through.items())[:8]
    ]
    st.markdown("**Dataset coverage**\n\n" + "\n".join(lines))
cc = None
if val.cross_checks:
    cc = val.cross_checks.get("imerg_vs_power_rain")
elif payload.get("cross_checks"):
    cc = payload["cross_checks"].get("imerg_vs_power_rain")
if cc and cc.get("r") is not None:
    st.write(
        f"Cross-check: IMERG vs POWER monthly rain **r = {cc['r']:.2f}** "
        f"(n = {cc.get('n_months', '—')} months)."
    )
    source_caption("IMERG + NASA POWER", rain_through)
st.info(
    "This tool **supports, not replaces**, your judgment and local expertise. "
    "Confidence badges reflect data coverage and SI uncertainty — not yield guarantees."
)
st.caption(
    "NASA & partners: Sentinel-2 (ESA/Copernicus), SMAP, IMERG, POWER, ERA5-Land, "
    "GRACE/FO, SRTM. Field Shift · NASA Space Apps 2026."
)
