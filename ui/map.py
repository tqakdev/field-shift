"""Folium map helpers with Esri World Imagery and optional Draw tool."""

from __future__ import annotations

from typing import Any

import folium
from folium.plugins import Draw

from ui.theme import PRIMARY


def _esri_tiles() -> folium.TileLayer:
    return folium.TileLayer(
        tiles=(
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}"
        ),
        attr="Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics",
        name="Esri World Imagery",
        overlay=False,
        control=True,
    )


def field_map(
    polygon: dict[str, Any] | None = None,
    *,
    center: tuple[float, float] = (42.0, -93.6),
    zoom: int = 13,
    draw: bool = False,
) -> folium.Map:
    """Build a Folium map centered on a field polygon or default Iowa point.

    Parameters
    ----------
    polygon:
        GeoJSON Polygon dict, or None.
    center:
        (lat, lon) used when no polygon is provided.
    zoom:
        Initial zoom level.
    draw:
        If True, enable ``folium.plugins.Draw`` for polygon / rectangle drawing.
    """
    lat, lon = center
    if polygon and polygon.get("coordinates"):
        ring = polygon["coordinates"][0]
        lat = sum(p[1] for p in ring) / len(ring)
        lon = sum(p[0] for p in ring) / len(ring)

    m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None)
    _esri_tiles().add_to(m)
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="OSM fallback",
        overlay=False,
        control=True,
    ).add_to(m)

    if polygon and polygon.get("coordinates"):
        folium.GeoJson(
            polygon,
            name="Field",
            style_function=lambda _: {
                "color": PRIMARY,
                "weight": 3,
                "fillColor": PRIMARY,
                "fillOpacity": 0.22,
            },
        ).add_to(m)
        m.fit_bounds([[p[1], p[0]] for p in polygon["coordinates"][0]])

    if draw:
        Draw(
            export=False,
            draw_options={
                "polyline": False,
                "circle": False,
                "circlemarker": False,
                "marker": False,
                "polygon": True,
                "rectangle": True,
            },
            edit_options={"edit": True},
        ).add_to(m)

    folium.LayerControl(collapsed=True).add_to(m)
    return m
