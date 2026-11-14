"""Home view: demo field picker + analyze-my-field map."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st
from fieldshift.data.ee_client import init_ee
from fieldshift.models import FieldConditions
from fieldshift.services import analyze_field, list_demo_fields, using_mock_data
from streamlit_folium import st_folium
from ui.map import field_map
from ui.mock_banner import show_mock_banner


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_analyze(polygon_json: str, name: str | None) -> FieldConditions:
    """Cache live EE+POWER analysis by polygon JSON (TTL 1 h)."""
    return analyze_field(json.loads(polygon_json), name=name)


status = init_ee()

st.title("Field Shift")
st.caption("NASA Space Apps 2026 — crop-rotation decision support with NASA Earth data")

if using_mock_data():
    show_mock_banner()

st.info(
    "This tool **supports, not replaces**, your judgment and local expertise.",
    icon="ℹ️",
)

if status.demo_mode:
    st.caption(
        f"Mode: **demo** (live EE analysis unavailable"
        f"{' — ' + status.error if status.error else ''})."
    )
else:
    st.caption(f"Mode: **live EE ready** (project configured: `{status.project}`).")

st.header("Try a demo field")
fields = list_demo_fields()
cols = st.columns(min(3, max(1, len(fields))))
for col, field in zip(cols, fields, strict=False):
    with col:
        st.subheader(field.name)
        st.write(field.climate_label)
        st.caption(field.country)
        if st.button("Open field", key=f"demo-{field.id}", use_container_width=True):
            st.session_state["field_id"] = field.id
            st.session_state["field_polygon"] = field.polygon
            st.session_state.pop("custom_conditions", None)
            st.switch_page("views/field.py")

st.header("Analyze my field")
st.write(
    "Draw a polygon on cropland (1–5000 ha). "
    "Analysis uses ~10 years of NASA / ESA / USGS data."
)
m = field_map(draw=True, center=(42.0, -93.6), zoom=5)
map_state = st_folium(m, width=None, height=420, key="home-draw")

drawn: dict[str, Any] | None = None
if map_state and map_state.get("last_active_drawing"):
    drawn = map_state["last_active_drawing"].get("geometry")

if status.demo_mode or not status.initialized:
    st.button("Live analysis unavailable (demo mode)", disabled=True)
else:
    if st.button("Analyze drawn field", disabled=drawn is None):
        try:
            with st.spinner("Analyzing 10 years of NASA data (~60 s)"):
                conditions = _cached_analyze(
                    json.dumps(drawn, sort_keys=True), "Your field"
                )
            st.session_state["field_id"] = "custom"
            st.session_state["field_polygon"] = drawn
            st.session_state["custom_conditions"] = conditions
            st.session_state["_rotation_field"] = "custom"
            st.session_state["current_rotation"] = ["maize", "soybean"]
            st.success("Analysis complete — opening field page.")
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
