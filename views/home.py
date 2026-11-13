"""Home view: demo field picker + analyze-my-field map."""

from __future__ import annotations

import streamlit as st
from fieldshift.data.ee_client import init_ee
from fieldshift.services import list_demo_fields, using_mock_data
from streamlit_folium import st_folium
from ui.map import field_map
from ui.mock_banner import show_mock_banner

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
            st.switch_page("views/field.py")

st.header("Analyze my field")
st.write(
    "Draw a polygon on the map. Live Earth Engine analysis ships in Phase 2–4; "
    "for now the draw tool is wired."
)
m = field_map(draw=True, center=(42.0, -93.6), zoom=5)
map_state = st_folium(m, width=None, height=420, key="home-draw")

drawn = None
if map_state and map_state.get("last_active_drawing"):
    drawn = map_state["last_active_drawing"].get("geometry")

if status.demo_mode or not status.initialized:
    st.button("Live analysis unavailable (demo mode)", disabled=True)
else:
    if st.button("Analyze drawn field", disabled=drawn is None):
        st.session_state["field_id"] = "custom"
        st.session_state["field_polygon"] = drawn
        st.warning("Live analyze path is stubbed until Phase 2–4.")

if drawn:
    st.caption("Polygon captured — will analyze when the data layer is wired.")
