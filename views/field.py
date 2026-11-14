"""Field view: numbered advisory-report story."""

from __future__ import annotations

import io
from pathlib import Path

import streamlit as st
from fieldshift.cache import read_json
from fieldshift.engine.crops import crop_by_id
from fieldshift.engine.slots import (
    crops_for_slot,
    default_rotation_for_slots,
    rotation_slots_from_features,
)
from fieldshift.engine.tiers import recommendation_sentence
from fieldshift.models import (
    FarmConstraints,
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
    load_demo_conditions,
    load_field_features,
    using_mock_data,
)
from PIL import Image
from streamlit_folium import st_folium
from ui.charts import conditions_figure, conditions_takeaway
from ui.components import (
    fact_chips,
    recommendation_banner,
    section,
    weights_bar,
)
from ui.explainers import CRITERION_HELP, FACT_HELP, chart_how_to_read
from ui.map import field_map
from ui.mock_banner import show_mock_banner
from ui.source_caption import source_caption
from ui.strategy_cards import render_strategy_cards

_DEFAULT_ROTATION = {
    "iowa": ["maize", "soybean"],
    "uk": ["winter_wheat"],
    "punjab": ["rice", "winter_wheat"],
    "custom": ["maize", "soybean"],
}
_DEFAULT_WATER = {
    "iowa": "rainfed",
    "uk": "rainfed",
    "punjab": "irrigated",
    "custom": "rainfed",
}
# Iowa maize→soy share one summer season → need a 2-year cycle.
# Punjab rice→wheat fill two seasons in one year → cycle_years=1.
_DEFAULT_CYCLE = {
    "iowa": 2,
    "uk": 1,
    "punjab": 1,
    "custom": 2,
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
def _cached_demo_conditions_figure(field_id: str, theme_ver: str = "design-v1") -> object:
    """Seasonal chart for demo fields — skip rebuild on unrelated widget reruns."""
    _ = theme_ver
    return conditions_figure(load_demo_conditions(field_id))


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
st.session_state.setdefault("irrigations_per_season", 0)
st.session_state.setdefault("nitrogen", "unknown")
st.session_state.setdefault("livestock", False)
st.session_state.setdefault("labor", "normal")
st.session_state.setdefault("budget_new_seed", "normal")
st.session_state.setdefault("has_small_grain_harvest", None)
st.session_state.setdefault("has_hay_forage_equipment", None)
st.session_state.setdefault("has_row_crop_planter", None)
st.session_state.setdefault("market_access", {})
# Multi-crop same-season rotations (e.g. maize→soy) need a 2-year cycle of slots
if st.session_state.get("_cycle_field") != field_id:
    st.session_state["cycle_years"] = _DEFAULT_CYCLE.get(field_id, 1)
    st.session_state["_cycle_field"] = field_id
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

st.markdown(
    '<p class="fs-eyebrow">FIELD REPORT</p>',
    unsafe_allow_html=True,
)
st.title(conditions.name)
st.caption(f"{conditions.climate_label} · {conditions.country or 'Custom field'}")

# --- 1. Your field (fragment: NDVI/RGB toggles must not re-run the whole page) ---
def _imagery_block() -> None:
    section(
        "Your field",
        "Satellite basemap with your polygon, plus a Sentinel-2 monthly timelapse.",
        step=1,
    )
    c_map, c_tl = st.columns([1, 1], gap="large")
    with c_map:
        fmap = field_map(conditions.polygon)
        # Display-only map — skip returning draw state (much faster on reruns).
        st_folium(
            fmap,
            height=360,
            use_container_width=True,
            key=f"field-map-{field_id}",
            returned_objects=[],
        )
    with c_tl:
        mode = st.radio(
            "Imagery product",
            ["ndvi", "rgb"],
            format_func=lambda x: (
                "Plant greenness (NDVI)" if x == "ndvi" else "True color (RGB)"
            ),
            horizontal=True,
            key=f"tl-mode-{field_id}",
        )
        play = st.toggle("Autoplay GIF", value=True, key=f"tl-play-{field_id}")
        tl = get_timelapse(field_id, index=mode)
        if tl.get("path") and Path(tl["path"]).exists():
            if play:
                # Autoplay uses the GIF as-is — do not decode every frame.
                st.image(tl["path"], use_container_width=True)
                st.caption("Autoplay · monthly cloud-masked composites")
            else:
                frames = _gif_png_frames(tl["path"])
                idx = st.slider(
                    "Month frame",
                    0,
                    max(0, len(frames) - 1),
                    min(7, max(0, len(frames) - 1)),
                    key=f"tl-slider-{field_id}-{mode}",
                )
                st.image(frames[idx], use_container_width=True)
                st.caption(
                    "Scrub months manually — labels are burned into each frame"
                )
            source_caption(
                "Sentinel-2 NDVI" if mode == "ndvi" else "Sentinel-2 RGB",
                ndvi_through,
            )
        else:
            st.info(tl.get("message", "Timelapse not available yet."))


if hasattr(st, "fragment"):

    @st.fragment  # type: ignore[attr-defined]
    def imagery_fragment() -> None:
        _imagery_block()

    imagery_fragment()
else:
    _imagery_block()

# --- 2. What the satellites see ---
section(
    "What the satellites see",
    "Key facts first, then the seasonal pattern across a typical year.",
    step=2,
)
if feat.frost_free_days:
    frost_value = f"{feat.frost_free_days:.0f} days"
elif conditions.climate_label and "subtropical" in conditions.climate_label.lower():
    frost_value = "Rarely frosts"
else:
    frost_value = "Not estimated yet"

chips = [
    {
        "label": "Bare soil window",
        "value": feat.bare_months_label.split("(")[0].strip()
        if feat.bare_months_label
        else "Not estimated yet",
        "meaning": FACT_HELP["bare"],
        "help": (
            f"source: Sentinel-2 plant greenness · data through "
            f"{ndvi_through or 'latest available'}"
        ),
    },
    {
        "label": "Frost-free days",
        "value": frost_value,
        "meaning": FACT_HELP["frost"],
        "help": (
            f"source: NASA POWER temperature · data through "
            f"{power_through or 'latest available'}"
        ),
    },
    {
        "label": "Rain (mm/yr)",
        "value": f"≈ {feat.rain_annual_mm:.0f} mm"
        if feat.rain_annual_mm
        else "Not estimated yet",
        "meaning": FACT_HELP["rain"],
        "help": (
            f"source: Best available rainfall · data through "
            f"{rain_through or 'latest available'}"
        ),
    },
    {
        "label": "Regional water storage",
        "value": grace_label if grace_label and grace_label != "—" else "Not estimated yet",
        "meaning": FACT_HELP["grace"],
        "help": (
            f"source: GRACE water storage · data through "
            f"{grace_through or 'latest available'}"
        ),
    },
]
fact_chips(chips)

with st.expander("How to read this chart", expanded=False):
    st.markdown(chart_how_to_read())

st.markdown(
    f'<p class="fs-chart-takeaway">{conditions_takeaway(conditions)}</p>',
    unsafe_allow_html=True,
)
_chart = (
    conditions_figure(conditions)
    if field_id == "custom"
    else _cached_demo_conditions_figure(field_id)
)
st.plotly_chart(
    _chart,
    use_container_width=True,
    config={"displayModeBar": False},
)
st.caption(
    "Plant greenness (line) · Rain mm (bars) · Water balance (dashed). "
    "Tan shade ≈ usually bare · light red ≈ growing-season stress."
)
source_caption(
    "Sentinel-2 / SMAP / Best available rainfall / water balance",
    rain_through,
)

anoms = payload.get("anomalies") or {}
with st.expander("Stress & anomalies (SI model)"):
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
    "About your farm",
    "Build your rotation from satellite seasons, then set farm inputs and priorities.",
    step=3,
)

try:
    engine_feats = load_field_features(
        field_id, current_rotation=st.session_state["current_rotation"]
    )
except FileNotFoundError:
    engine_feats = {}

st.markdown("**Rotation builder**")
st.caption(
    "Season slots come from detected NDVI seasons (1–2 per year). "
    "Up to 4 cash crops per cycle; optional cover in each bare window. "
    "Crops that fail climate fit for a slot are disabled (see reason)."
)
st.session_state["cycle_years"] = st.selectbox(
    "Rotation cycle length (years)",
    [1, 2],
    index=[1, 2].index(int(st.session_state.get("cycle_years", 1))),
    help="Repeat satellite seasons across years so you can place up to 4 cash crops.",
    key=f"cycle-{field_id}",
)
slots = rotation_slots_from_features(
    engine_feats,
    max_cash=4,
    cycle_years=int(st.session_state["cycle_years"]),
)
preferred = list(st.session_state["current_rotation"])
if not preferred:
    preferred = list(_DEFAULT_ROTATION.get(field_id, ["maize", "soybean"]))

cash_slots = [s for s in slots if s.get("kind") == "cash"]
cover_slots = [s for s in slots if s.get("kind") == "cover"]
default_cash = default_rotation_for_slots(slots, preferred)
# Keep any covers already in preferred
prev_covers = [
    c
    for c in preferred
    if c not in default_cash
]

new_rot: list[str] = []
slot_cols = st.columns(max(1, min(4, len(cash_slots) + len(cover_slots))))
all_slots = cash_slots + cover_slots
for i, slot in enumerate(all_slots):
    with slot_cols[i % len(slot_cols)]:
        options = crops_for_slot(
            slot, engine_feats, always_allow=preferred
        )
        enabled = [o for o in options if o["enabled"]]
        disabled_ids = {o["id"] for o in options if not o["enabled"]}
        reason_by_id = {o["id"]: o["reason"] for o in options}
        labels = {
            o["id"]: (
                o["name"]
                if o["enabled"]
                else f"{o['name']} — {o['reason']}"
            )
            for o in options
        }
        if slot.get("kind") == "cover":
            choices = ["(none)"] + [o["id"] for o in options]
            default_cover = next(
                (c for c in prev_covers if c in {o["id"] for o in enabled}),
                "(none)",
            )
            _labels = dict(labels)

            def _fmt_cover(x: str, _l: dict[str, str] = _labels) -> str:
                return "No cover crop" if x == "(none)" else _l.get(x, x)

            pick = st.selectbox(
                f"{slot['label']}",
                choices,
                index=choices.index(default_cover)
                if default_cover in choices
                else 0,
                format_func=_fmt_cover,
                key=f"slot-{field_id}-{slot['id']}",
                help="Optional cover in the bare / fallow window.",
            )
            if pick != "(none)" and pick not in disabled_ids:
                new_rot.append(pick)
            elif pick != "(none)" and pick in disabled_ids:
                st.caption(f"Unavailable: {reason_by_id.get(pick, '')}")
        else:
            enabled_ids = [o["id"] for o in enabled] or [
                default_cash[min(i, len(default_cash) - 1)]
            ]
            # Prefer matching preferred crop for this cash index
            cash_idx = sum(1 for s in all_slots[:i] if s.get("kind") == "cash")
            pref = (
                default_cash[cash_idx]
                if cash_idx < len(default_cash)
                else enabled_ids[0]
            )
            if pref not in enabled_ids:
                pref = enabled_ids[0]
            _labels_cash = dict(labels)

            def _fmt_cash(x: str, _l: dict[str, str] = _labels_cash) -> str:
                return _l.get(x, x)

            pick = st.selectbox(
                f"{slot['label']}",
                enabled_ids + sorted(disabled_ids),
                index=enabled_ids.index(pref),
                format_func=_fmt_cash,
                key=f"slot-{field_id}-{slot['id']}",
            )
            if pick in disabled_ids:
                st.caption(f"Unavailable: {reason_by_id.get(pick, '')}")
                pick = pref
            new_rot.append(pick)

if not new_rot:
    new_rot = list(default_cash)
st.session_state["current_rotation"] = new_rot

_soil_labels = {
    "sand": "Sandy",
    "loam": "Loam (mixed)",
    "clay": "Clay",
    "silt": "Silt",
    "unknown": "Not sure",
}
st.session_state["soil_type"] = st.selectbox(
    "Soil type",
    ["sand", "loam", "clay", "silt", "unknown"],
    index=["sand", "loam", "clay", "silt", "unknown"].index(
        st.session_state["soil_type"]
    ),
    format_func=lambda x, _l=_soil_labels: _l[x],
    help="Rough texture is enough. Used lightly for climate/soil context — "
    "not a lab soil test.",
)

st.markdown("**What you have on the farm**")
st.caption(
    "Optional. Skip any field you are unsure about — we will not block options "
    "for blanks. Answers here filter or gently adjust recommendations; they do "
    "not change your priority sliders below."
)
c1, c2, c3 = st.columns(3)
with c1:
    water_label = {
        "rainfed": "Rain-fed only (no irrigation)",
        "limited": "Some irrigation available",
        "irrigated": "Fully irrigated",
    }
    st.session_state["water_access"] = st.radio(
        "How do you water this field?",
        ["rainfed", "limited", "irrigated"],
        index=["rainfed", "limited", "irrigated"].index(
            st.session_state["water_access"]
        ),
        format_func=lambda x: water_label[x],
        help="Used in the water score. Rain-fed relies only on rainfall from satellites.",
    )
    if st.session_state["water_access"] in ("limited", "irrigated"):
        st.session_state["irrigations_per_season"] = int(
            st.number_input(
                "Typical irrigations per growing season",
                min_value=0,
                max_value=20,
                value=int(st.session_state.get("irrigations_per_season", 0)),
                help="Rough count is fine. Each watering adds a small, capped lift "
                "to the water score.",
                key=f"irr-n-{field_id}",
            )
        )
    else:
        st.session_state["irrigations_per_season"] = 0
    _n_labels = {
        "unknown": "Not sure / prefer not to say",
        "low": "Low — little synthetic N",
        "medium": "Medium — typical for the area",
        "high": "High — heavy N fertilizer",
    }
    st.session_state["nitrogen"] = st.selectbox(
        "Nitrogen fertilizer on this field",
        ["unknown", "low", "medium", "high"],
        index=["unknown", "low", "medium", "high"].index(
            st.session_state.get("nitrogen", "unknown")
        ),
        format_func=lambda x, _l=_n_labels: _l[x],
        help="If a rotation includes a nitrogen-fixing crop (legume), we note that "
        "it may cut N need for the next crop, and give a small soil-health bonus "
        "(larger when your current N use is high).",
        key=f"n-{field_id}",
    )
    st.session_state["livestock"] = st.checkbox(
        "I keep livestock that can eat forage",
        value=st.session_state["livestock"],
        help="If yes, cover crops and forage legumes can count as feed income — "
        "not only as soil cover.",
        key=f"live-{field_id}",
    )
with c2:
    st.markdown("**Equipment you can use**")
    st.caption("Leave unchecked if you are not sure — we will not exclude options.")
    sg = st.checkbox(
        "Can harvest small grains (wheat, rye, …)",
        value=st.session_state.get("has_small_grain_harvest") is True,
        key=f"mach-sg-{field_id}",
    )
    hay = st.checkbox(
        "Can make hay or manage forage",
        value=st.session_state.get("has_hay_forage_equipment") is True,
        key=f"mach-hay-{field_id}",
    )
    rowp = st.checkbox(
        "Can plant row crops (maize, soy, …)",
        value=st.session_state.get("has_row_crop_planter") is True,
        key=f"mach-row-{field_id}",
    )
    # Tri-state: unchecked after never set stays None (don't know) via "I know my kit"
    know_kit = st.checkbox(
        "Use my answers above as hard limits",
        value=st.session_state.get("know_kit", False),
        key=f"know-kit-{field_id}",
        help="Turn this on only when you are sure. Then unchecked boxes mean "
        "you cannot run that crop type — those options are marked Not suitable.",
    )
    st.session_state["know_kit"] = know_kit
    if know_kit:
        st.session_state["has_small_grain_harvest"] = bool(sg)
        st.session_state["has_hay_forage_equipment"] = bool(hay)
        st.session_state["has_row_crop_planter"] = bool(rowp)
    else:
        st.session_state["has_small_grain_harvest"] = None
        st.session_state["has_hay_forage_equipment"] = None
        st.session_state["has_row_crop_planter"] = None
with c3:
    _labor_labels = {
        "low": "Tight — hard to take on extra field work",
        "normal": "Typical — manage a normal season",
        "high": "Flexible — can take on more management",
    }
    st.session_state["labor"] = st.selectbox(
        "People available for field work",
        ["low", "normal", "high"],
        index=["low", "normal", "high"].index(
            st.session_state.get("labor", "normal")
        ),
        format_func=lambda x, _l=_labor_labels: _l[x],
        help="Tight labor slightly lowers scores for rotations that add cover crops "
        "(extra planting/termination work). It does not hide those options.",
        key=f"labor-{field_id}",
    )
    _budget_labels = {
        "low": "Tight — prefer not to buy new seed now",
        "normal": "OK — can buy seed if the benefit is clear",
    }
    st.session_state["budget_new_seed"] = st.selectbox(
        "Money for new seed this year",
        ["low", "normal"],
        index=["low", "normal"].index(
            st.session_state.get("budget_new_seed", "normal")
        ),
        format_func=lambda x, _l=_budget_labels: _l[x],
        help="Tight budget slightly lowers scores when a strategy adds cover-crop "
        "seed. It does not remove the option — you still see it with the reason.",
        key=f"budget-{field_id}",
    )
    st.markdown("**Can you sell each crop?**")
    st.caption(
        "One answer per crop in your rotation. “Not sure” keeps income at the "
        "default estimate."
    )
    market: dict[str, str] = dict(st.session_state.get("market_access") or {})
    # Unique crop ids (multi-year cycles can repeat the same cash crop).
    _mkt_labels = {
        "unknown": "Not sure yet",
        "buyer": "Yes — I already have a buyer",
        "no_market": "No — hard to sell locally",
    }
    for cid in dict.fromkeys(c for c in new_rot if c and c != "(none)"):
        try:
            crop_name = crop_by_id(cid)["name"]
        except KeyError:
            crop_name = cid.replace("_", " ").title()

        def _fmt_mkt(x: str, _l: dict[str, str] = _mkt_labels) -> str:
            return _l.get(x, x)

        market[cid] = st.selectbox(
            f"Selling {crop_name}",
            ["unknown", "buyer", "no_market"],
            index=["unknown", "buyer", "no_market"].index(
                market.get(cid, "unknown")
            ),
            format_func=_fmt_mkt,
            key=f"mkt-{field_id}-{cid}",
            help="Yes (buyer): raises the relative income score. "
            "No (hard to sell): cash crops are marked Not suitable. "
            "Cover/forage kept for on-farm use can still be suitable.",
        )
    st.session_state["market_access"] = market

# --- 4 + 5 Priorities, climate what-if, then options (fragment for snappy sliders) ---
def _options_block() -> None:
    st.markdown("**What matters most to you**")
    st.caption(
        "These sliders set how we rank options (0 = ignore, 1 = equal weight, "
        "2 = twice as important). Farm facts above only filter or gently adjust "
        "scores — they never change these weights."
    )
    w_meta = [
        ("water", "Water"),
        ("soil_health", "Soil health"),
        ("erosion", "Erosion"),
        ("pest_break", "Pest break"),
        ("climate_fit", "Climate fit"),
        ("income", "Income"),
    ]
    w_cols = st.columns(3)
    weights: dict[str, float] = {}
    for i, (key, label) in enumerate(w_meta):
        with w_cols[i % 3]:
            help_txt = CRITERION_HELP.get(key, {}).get("detail", "")
            if key == "income":
                help_txt = (
                    "Relative income: typical price tier × yield potential, "
                    "adjusted for market access (buyer lift). Not a farm budget. "
                    + help_txt
                )
            weights[key] = st.slider(
                label,
                0.0,
                2.0,
                1.0,
                0.1,
                key=f"w-{field_id}-{key}",
                help=help_txt,
            )
    weights_bar(weights)

    # Climate first so scenario is set before reading the scored options.
    section(
        "What if the climate shifts?",
        "Set a scenario first — options below re-score from cached features only "
        "(no Earth Engine re-extract).",
        step=4,
    )
    c_rain, c_temp = st.columns(2)
    with c_rain:
        st.session_state["rain_mult"] = st.slider(
            "Rainfall change (multiplier)",
            0.7,
            1.3,
            float(st.session_state["rain_mult"]),
            0.05,
            key=f"rain-{field_id}",
            help="1.0 = today’s rainfall. 0.8 ≈ 20% drier years; 1.2 ≈ 20% wetter.",
        )
    with c_temp:
        st.session_state["temp_offset"] = st.slider(
            "Temperature offset (°C)",
            0.0,
            3.0,
            float(st.session_state["temp_offset"]),
            0.5,
            key=f"temp-{field_id}",
            help="Extra warming on top of today’s climate (e.g. +2 °C warmer seasons).",
        )

    climate_shifted = (
        abs(float(st.session_state["rain_mult"]) - 1.0) > 1e-6
        or float(st.session_state["temp_offset"]) > 1e-6
    )
    if climate_shifted:
        st.caption(
            f"Scenario applied below: rain ×{st.session_state['rain_mult']:.2f}, "
            f"temp +{st.session_state['temp_offset']:.1f} °C"
        )

    section(
        "Your options",
        "Tiered cards: Best fit · Worth considering · Your rotation · Not suitable. "
        "Updates when you change priorities, constraints, or climate sliders.",
        step=5,
    )
    cons = FarmConstraints(
        has_small_grain_harvest=st.session_state.get("has_small_grain_harvest"),
        has_hay_forage_equipment=st.session_state.get(
            "has_hay_forage_equipment"
        ),
        has_row_crop_planter=st.session_state.get("has_row_crop_planter"),
        labor=st.session_state.get("labor", "normal"),
        budget_new_seed=st.session_state.get("budget_new_seed", "normal"),
        market_access=dict(st.session_state.get("market_access") or {}),
    )
    req = StrategyRequest(
        current_rotation=st.session_state["current_rotation"],
        soil_type=st.session_state["soil_type"],
        water_access=st.session_state["water_access"],
        irrigations_per_season=int(
            st.session_state.get("irrigations_per_season", 0)
        ),
        nitrogen=st.session_state.get("nitrogen", "unknown"),
        livestock=st.session_state["livestock"],
        weights=PriorityWeights(**weights),
        constraints=cons,
        scenario=ScenarioParams(
            rain_mult=float(st.session_state["rain_mult"]),
            temp_offset=float(st.session_state["temp_offset"]),
        ),
    )
    result = generate_strategies(field_id, req)
    cards = result.strategies
    if cards:
        recommendation_banner(recommendation_sentence(cards))
        render_strategy_cards(cards, show_climate_delta=climate_shifted)


if hasattr(st, "fragment"):

    @st.fragment  # type: ignore[attr-defined]
    def options_fragment() -> None:
        _options_block()

    options_fragment()
else:
    _options_block()

# --- 6. Reliability ---
section(
    "How reliable is this?",
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
