"""Home view: NASA-style hero, demo fields, analyze-my-field."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st
from fieldshift.cache import CACHE_DIR
from fieldshift.data.ee_client import init_ee
from fieldshift.models import FieldConditions
from fieldshift.services import analyze_field, list_demo_fields, using_mock_data
from streamlit_folium import st_folium
from ui.components import demo_field_cards, hero, section
from ui.map import field_map
from ui.mock_banner import show_mock_banner

_ROTATION_LABEL = {
    "iowa": "Maize → Soybean",
    "kansas": "Winter wheat",
    "punjab": "Rice → Winter wheat",
}


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_analyze(polygon_json: str, name: str | None) -> FieldConditions:
    return analyze_field(json.loads(polygon_json), name=name)


status = init_ee()
live = bool(status.initialized and not status.demo_mode)

if using_mock_data():
    show_mock_banner()

hero(
    "Field Shift",
    "See what NASA satellites know about your field, and compare crop rotations "
    "that build soil and resilience.",
    sub="Decision support for farmers — supports, not replaces, your judgment.",
    mode_label="Live NASA data" if live else "Cached demo mode",
    live=live,
)

section(
    "Try a demo field",
    "Three contrasting farms pre-loaded from NASA / ESA / USGS archives.",
)
fields = list_demo_fields()
card_payload = []
for field in fields:
    thumb = CACHE_DIR / f"demo_{field.id}_ndvi_thumb.png"
    if not thumb.exists():
        thumb = CACHE_DIR / f"demo_{field.id}_ndvi.gif"
    card_payload.append(
        {
            "id": field.id,
            "name": field.name,
            "climate": field.climate_label,
            "country": field.country,
            "rotation": _ROTATION_LABEL.get(field.id, "—"),
            "thumb_path": str(thumb) if thumb.exists() else None,
        }
    )
opened_id = demo_field_cards(card_payload)
if opened_id:
    field = next(f for f in fields if f.id == opened_id)
    st.session_state["field_id"] = field.id
    st.session_state["field_polygon"] = field.polygon
    st.session_state.pop("custom_conditions", None)
    st.switch_page("views/field.py")

section(
    "Analyze my own field",
    "Draw a polygon on cropland (1–5000 ha). Live runs use ~10 years of Earth observations.",
)
step_cols = st.columns(3)
with step_cols[0]:
    st.markdown("**01 — Draw**  \nOutline your field on the imagery.")
with step_cols[1]:
    st.markdown("**02 — Describe**  \nRotation, soil, water, priorities.")
with step_cols[2]:
    st.markdown("**03 — Compare**  \nScored rotation options with evidence.")

m = field_map(draw=True, center=(42.0, -93.6), zoom=5)
map_state = st_folium(m, width=None, height=400, key="home-draw")

drawn: dict[str, Any] | None = None
if map_state and map_state.get("last_active_drawing"):
    drawn = map_state["last_active_drawing"].get("geometry")

if not live:
    st.button("Live analysis unavailable (demo mode)", disabled=True)
else:
    clicked = st.button(
        "Analyze drawn field",
        disabled=drawn is None,
        type="primary",
    )
    if clicked:
        try:
            progress = st.progress(0, text="Analyzing 10 years of NASA data (~60 s)")
            progress.progress(20, text="Querying Earth Engine & NASA POWER…")
            with st.spinner("Analyzing 10 years of NASA data (~60 s)"):
                conditions = _cached_analyze(
                    json.dumps(drawn, sort_keys=True), "Your field"
                )
            progress.progress(100, text="Analysis complete")
            st.session_state["field_id"] = "custom"
            st.session_state["field_polygon"] = drawn
            st.session_state["custom_conditions"] = conditions
            st.session_state["_rotation_field"] = "custom"
            st.session_state["current_rotation"] = ["maize", "soybean"]
            st.success("Opening your field report.")
            st.switch_page("views/field.py")
        except ValueError as exc:
            st.error(str(exc))
        except RuntimeError as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001
            st.error(
                f"Earth Engine / POWER analysis failed: {exc}. "
                "Check credentials and try a smaller cropland polygon."
            )

if drawn:
    st.caption("Polygon captured — ready to analyze.")
