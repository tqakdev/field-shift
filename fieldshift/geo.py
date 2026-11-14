"""Polygon helpers (area, centroid) — pure Python, no EE."""

from __future__ import annotations

import math
from typing import Any


def polygon_rings(polygon: dict[str, Any]) -> list[list[list[float]]]:
    """Return exterior (+ holes) rings from a GeoJSON Polygon or MultiPolygon."""
    geom = polygon.get("geometry", polygon)
    gtype = geom.get("type")
    coords = geom.get("coordinates") or []
    if gtype == "Polygon":
        return coords  # type: ignore[return-value]
    if gtype == "MultiPolygon":
        rings: list[list[list[float]]] = []
        for poly in coords:
            rings.extend(poly)
        return rings
    raise ValueError(f"Unsupported geometry type: {gtype}")


def polygon_centroid(polygon: dict[str, Any]) -> tuple[float, float]:
    """Rough centroid (mean of exterior ring vertices, excluding closing point)."""
    ring = polygon_rings(polygon)[0]
    pts = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    if not pts:
        raise ValueError("Empty polygon")
    lon = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return lat, lon


def polygon_area_ha(polygon: dict[str, Any]) -> float:
    """Approximate geodesic area in hectares (Shoelace on equirectangular projection)."""
    ring = polygon_rings(polygon)[0]
    pts = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    if len(pts) < 3:
        return 0.0
    lat0 = sum(p[1] for p in pts) / len(pts)
    # meters per degree
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * max(0.2, abs(math.cos(math.radians(lat0))))
    xy = [(p[0] * m_per_deg_lon, p[1] * m_per_deg_lat) for p in pts]
    area = 0.0
    for i in range(len(xy)):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % len(xy)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0 / 10_000.0
