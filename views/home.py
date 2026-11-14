"""Home view: hero, demo field picker, analyze-my-field map."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st
from fieldshift.cache import CACHE_DIR
from fieldshift.data.ee_client import init_ee
from fieldshift.models import FieldConditions
from fieldshift.services import analyze_field, list_demo_fields, using_mock_data
from streamlit_folium import st_folium
from ui.components import demo_field_card, hero, section
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
    sub="Supports, not replaces, your judgment.",
    mode_label="Live NASA data" if live else "Demo",
    live=live,
)

section("🛰 Try a demo field", "Three contrasting farms — open one to see a full advisory.")
fields = list_demo_fields()
cols = st.columns(min(3, max(1, len(fields))))
for col, field in zip(cols, fields, strict=False):
    with col:
        thumb = CACHE_DIR / f"demo_{field.id}_ndvi_thumb.png"
        if not thumb.exists():
            thumb = CACHE_DIR / f"demo_{field.id}_ndvi.gif"
        opened = demo_field_card(
            name=field.name,
            climate=field.climate_label,
            country=field.country,
            rotation=_ROTATION_LABEL.get(field.id, "—"),
            thumb_path=str(thumb) if thumb.exists() else None,
            button_key=f"demo-{field.id}",
        )
        if opened:
            st.session_state["field_id"] = field.id
            st.session_state["field_polygon"] = field.polygon
            st.session_state.pop("custom_conditions", None)
            st.switch_page("views/field.py")

section(
    "🌱 Analyze my own field",
    "Draw a polygon on cropland (1–5000 ha), then we’ll walk you through the report.",
)
st.markdown(
    """
1. **Draw** your field on the map  
2. **Tell us** about your farm (rotation, soil, priorities)  
3. **Compare** rotation options scored for you  
"""
)
m = field_map(draw=True, center=(42.0, -93.6), zoom=5)
map_state = st_folium(m, width=None, height=420, key="home-draw")

drawn: dict[str, Any] | None = None
if map_state and map_state.get("last_active_drawing"):
    drawn = map_state["last_active_drawing"].get("geometry")

if not live:
    st.button("Live analysis unavailable (demo mode)", disabled=True)
else:
    if st.button(
        "Analyze drawn field",
        disabled=drawn is None,
        type="primary",
        use_container_width=False,
    ):
        try:
            progress = st.progress(0, text="Analyzing 10 years of NASA data (~60 s)")
            progress.progress(15, text="Contacting Earth Engine & NASA POWER…")
            with st.spinner("Analyzing 10 years of NASA data (~60 s)"):
                conditions = _cached_analyze(
                    json.dumps(drawn, sort_keys=True), "Your field"
                )
            progress.progress(100, text="Done")
            st.session_state["field_id"] = "custom"
            st.session_state["field_polygon"] = drawn
            st.session_state["custom_conditions"] = conditions
            st.session_state["_rotation_field"] = "custom"
            st.session_state["current_rotation"] = ["maize", "soybean"]
            st.success("Analysis complete — opening your field report.")
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
