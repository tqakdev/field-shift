"""Field-level monthly Earth Engine reductions for PROJECT_SPEC §4 global core datasets.

One ``getInfo`` per dataset (batched FeatureCollection), not per month.
Units are converted to the values documented in each helper.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from fieldshift.data.ee_client import init_ee

# Optical / climate analysis window length (complete years), ending at data availability.
ANALYSIS_YEARS = 10


def _require_ee() -> Any:
    """Import ee after ensuring the client is initialized."""
    status = init_ee()
    if not status.initialized:
        raise RuntimeError(status.error or "Earth Engine is not initialized")
    import ee

    return ee


def polygon_from_point(lat: float, lon: float, size_ha: float) -> dict[str, Any]:
    """Build an approximate square GeoJSON polygon of ``size_ha`` around a point."""
    # 1 ha ≈ 100 m × 100 m; side length in degrees ~ size-dependent at mid-latitudes
    side_m = (size_ha * 10_000) ** 0.5
    # rough meters → degrees (lon scaled by cos(lat))
    import math

    dlat = (side_m / 2) / 111_320
    dlon = (side_m / 2) / (111_320 * max(0.2, abs(math.cos(math.radians(lat)))))
    ring = [
        [lon - dlon, lat - dlat],
        [lon + dlon, lat - dlat],
        [lon + dlon, lat + dlat],
        [lon - dlon, lat + dlat],
        [lon - dlon, lat - dlat],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


def _geom(ee: Any, polygon: dict[str, Any]) -> Any:
    return ee.Geometry.Polygon(polygon["coordinates"])


def _month_list(ee: Any, start: str, end: str) -> Any:
    """List of ``YYYY-MM-01`` strings from start (inclusive) to end (inclusive), monthly."""
    start_d = ee.Date(start)
    end_d = ee.Date(end)
    n = end_d.difference(start_d, "month").round()
    return ee.List.sequence(0, n).map(
        lambda i: start_d.advance(i, "month").format("YYYY-MM-01")
    )


def _fc_to_df(info: dict[str, Any], value_keys: list[str]) -> pd.DataFrame:
    """Convert a FeatureCollection.getInfo() dict to a tidy monthly DataFrame."""
    rows: list[dict[str, Any]] = []
    for feat in info.get("features", []):
        props = feat.get("properties", {})
        month = props.get("month")
        if not month:
            continue
        for key in value_keys:
            val = props.get(key)
            rows.append({"month": str(month)[:7], "variable": key, "value": val})
    if not rows:
        return pd.DataFrame(columns=["month", "variable", "value"])
    df = pd.DataFrame(rows)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def collection_last_month(ee: Any, polygon: dict[str, Any], ee_id: str) -> str:
    """Last image month-start (YYYY-MM-01) for a collection at this field."""
    geom = _geom(ee, polygon)
    last = ee.Image(
        ee.ImageCollection(ee_id).filterBounds(geom).sort("system:time_start", False).first()
    )
    # Snap to month start of the image's month
    return ee.Date(last.date()).format("YYYY-MM-01").getInfo()


def analysis_end_date(ee: Any, polygon: dict[str, Any]) -> str:
    """Freshest complete month from S2 + ERA5 (explicitly excludes IMERG GEE lag).

    IMERG often lags ~1 year on GEE; using it as a global end truncated every series.
    Each dataset still keeps its own valid range via per-variable metadata.
    """
    geom = _geom(ee, polygon)
    candidates = []
    for ee_id in (
        "COPERNICUS/S2_SR_HARMONIZED",
        "ECMWF/ERA5_LAND/MONTHLY_AGGR",
    ):
        col = ee.ImageCollection(ee_id).filterBounds(geom)
        last = ee.Image(col.sort("system:time_start", False).first())
        candidates.append(last.date())
    # Conservative among freshest optical/climate: earlier of the two lasts
    end = ee.Date(candidates[0])
    for d in candidates[1:]:
        end = ee.Date(ee.Algorithms.If(d.millis().lt(end.millis()), d, end))
    return end.advance(-1, "month").format("YYYY-MM-01").getInfo()


def analysis_window(
    ee: Any, polygon: dict[str, Any], years: int = ANALYSIS_YEARS
) -> tuple[str, str]:
    """Return (start, end) as YYYY-MM-01 for the last ``years`` of freshest S2/ERA5 data."""
    end = analysis_end_date(ee, polygon)
    start = ee.Date(end).advance(-years, "year").format("YYYY-MM-01").getInfo()
    return start, end


def _cap_end(global_end: str, dataset_last: str) -> str:
    """Return the earlier of two YYYY-MM-01 strings."""
    return min(global_end[:10], dataset_last[:10])


def _empty_masked(ee: Any, band: str) -> Any:
    """Fully masked constant image so reduceRegion returns null, not a crash."""
    return ee.Image.constant(0).rename(band).updateMask(ee.Image.constant(0))


def _reduce_region(
    ee: Any,
    image: Any,
    geom: Any,
    scale: float,
    *,
    reducer: Any | None = None,
) -> Any:
    """``reduceRegion`` that still returns a value when the field is smaller than ``scale``.

    Coarse products (IMERG / ERA5 / SMAP / GRACE) have pixels ≫ a 60 ha field. If no
    pixel center falls inside the polygon, EE returns null — so for small fields we
    sample the centroid (still the correct field-cell value at that resolution).
    """
    red = reducer if reducer is not None else ee.Reducer.mean()
    region = ee.Algorithms.If(
        geom.area(maxError=1).lt(float(scale) * float(scale)),
        geom.centroid(maxError=1),
        geom,
    )
    return image.reduceRegion(
        reducer=red,
        geometry=region,
        scale=scale,
        bestEffort=True,
        maxPixels=1e9,
    )


def _s2_cs_linked(ee: Any, geom: Any, start_d: Any, end_d: Any) -> Any:
    """Sentinel-2 SR filtered to AOI/date with Cloud Score+ bands joined."""
    cs_plus = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
    return (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geom)
        .filterDate(start_d, end_d)
        .linkCollection(cs_plus, ["cs"])
    )


def _mask_s2_with_cs(ee: Any, s2: Any) -> Any:
    """Apply Cloud Score+ cs ≥ 0.6 (expects ``cs`` from ``linkCollection``)."""
    # linkCollection adds a fully-masked cs band when no match exists.
    return s2.updateMask(s2.select("cs").gte(0.6))


def extract_s2_monthly(ee: Any, polygon: dict[str, Any], start: str, end: str) -> pd.DataFrame:
    """Monthly median Sentinel-2 NDVI (Cloud Score+ masked). Unitless NDVI."""
    geom = _geom(ee, polygon)
    months = _month_list(ee, start, end)

    def per_month(m: Any) -> Any:
        m = ee.Date(m)
        col = _s2_cs_linked(ee, geom, m, m.advance(1, "month")).map(
            lambda img: _mask_s2_with_cs(ee, img)
        )

        def add_ndvi(img: Any) -> Any:
            nd = img.normalizedDifference(["B8", "B4"]).rename("ndvi")
            return nd.copyProperties(img, ["system:time_start"])

        ndvi = ee.Image(
            ee.Algorithms.If(
                col.size().gt(0),
                col.map(add_ndvi).median().rename("ndvi"),
                _empty_masked(ee, "ndvi"),
            )
        )
        stats = _reduce_region(
            ee, ndvi, geom, 10, reducer=ee.Reducer.median()
        )
        return ee.Feature(
            None,
            {
                "month": m.format("YYYY-MM"),
                "ndvi_s2": stats.get("ndvi"),
                "n_obs": col.size(),
            },
        )

    fc = ee.FeatureCollection(months.map(per_month))
    info = fc.getInfo()
    df = _fc_to_df(info, ["ndvi_s2"])
    # attach n_obs
    n_rows = [
        {
            "month": f["properties"]["month"],
            "variable": "ndvi_s2_n_obs",
            "value": f["properties"].get("n_obs"),
        }
        for f in info.get("features", [])
    ]
    return pd.concat([df, pd.DataFrame(n_rows)], ignore_index=True) if n_rows else df


def _landsat_ndvi(ee: Any, img: Any) -> Any:
    """Landsat C2 L2 surface reflectance → NDVI with scale factors + QA_PIXEL mask."""
    qa = img.select("QA_PIXEL")
    # Clear: bits 1 (dilated cloud), 3 (cloud), 4 (cloud shadow) clear
    mask = (
        qa.bitwiseAnd(1 << 1).eq(0)
        .And(qa.bitwiseAnd(1 << 3).eq(0))
        .And(qa.bitwiseAnd(1 << 4).eq(0))
    )
    sr = img.select(["SR_B4", "SR_B5"]).multiply(0.0000275).add(-0.2)
    ndvi = sr.normalizedDifference(["SR_B5", "SR_B4"]).rename("ndvi").updateMask(mask)
    return ndvi.copyProperties(img, ["system:time_start"])


def extract_landsat_monthly(ee: Any, polygon: dict[str, Any], start: str, end: str) -> pd.DataFrame:
    """Monthly median Landsat 8/9 NDVI. Unitless."""
    geom = _geom(ee, polygon)
    months = _month_list(ee, start, end)
    l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
    l9 = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")

    def per_month(m: Any) -> Any:
        m = ee.Date(m)
        col = (
            l8.merge(l9)
            .filterBounds(geom)
            .filterDate(m, m.advance(1, "month"))
            .map(lambda img: _landsat_ndvi(ee, img))
        )
        med = ee.Image(
            ee.Algorithms.If(
                col.size().gt(0),
                col.median().select("ndvi"),
                _empty_masked(ee, "ndvi"),
            )
        )
        stats = _reduce_region(
            ee, med, geom, 30, reducer=ee.Reducer.median()
        )
        return ee.Feature(
            None, {"month": m.format("YYYY-MM"), "ndvi_landsat": stats.get("ndvi")}
        )

    return _fc_to_df(
        ee.FeatureCollection(months.map(per_month)).getInfo(), ["ndvi_landsat"]
    )


def extract_modis_monthly(ee: Any, polygon: dict[str, Any], start: str, end: str) -> pd.DataFrame:
    """Monthly mean MODIS NDVI (scale 0.0001). Unitless."""
    geom = _geom(ee, polygon)
    months = _month_list(ee, start, end)

    def per_month(m: Any) -> Any:
        m = ee.Date(m)
        col = (
            ee.ImageCollection("MODIS/061/MOD13Q1")
            .filterBounds(geom)
            .filterDate(m, m.advance(1, "month"))
            .select("NDVI")
        )
        img = ee.Image(
            ee.Algorithms.If(
                col.size().gt(0),
                col.mean().multiply(0.0001).rename("ndvi_modis"),
                _empty_masked(ee, "ndvi_modis"),
            )
        )
        stats = _reduce_region(ee, img, geom, 250)
        return ee.Feature(
            None,
            {"month": m.format("YYYY-MM"), "ndvi_modis": stats.get("ndvi_modis")},
        )

    return _fc_to_df(ee.FeatureCollection(months.map(per_month)).getInfo(), ["ndvi_modis"])


def extract_smap_monthly(ee: Any, polygon: dict[str, Any], start: str, end: str) -> pd.DataFrame:
    """Monthly mean SMAP L4 surface + rootzone soil moisture (m³/m³)."""
    geom = _geom(ee, polygon)
    months = _month_list(ee, start, end)

    def per_month(m: Any) -> Any:
        m = ee.Date(m)
        col = (
            ee.ImageCollection("NASA/SMAP/SPL4SMGP/008")
            .filterBounds(geom)
            .filterDate(m, m.advance(1, "month"))
            .select(["sm_surface", "sm_rootzone"])
        )
        img = ee.Image(
            ee.Algorithms.If(
                col.size().gt(0),
                col.mean(),
                _empty_masked(ee, "sm_surface").addBands(_empty_masked(ee, "sm_rootzone")),
            )
        )
        stats = _reduce_region(ee, img, geom, 11000)
        return ee.Feature(
            None,
            {
                "month": m.format("YYYY-MM"),
                "sm_surface": stats.get("sm_surface"),
                "sm_rootzone": stats.get("sm_rootzone"),
            },
        )

    return _fc_to_df(
        ee.FeatureCollection(months.map(per_month)).getInfo(),
        ["sm_surface", "sm_rootzone"],
    )


def extract_imerg_monthly(ee: Any, polygon: dict[str, Any], start: str, end: str) -> pd.DataFrame:
    """Monthly IMERG precipitation. Band is mm/hr → convert to mm/month via days×24."""
    geom = _geom(ee, polygon)
    months = _month_list(ee, start, end)

    def per_month(m: Any) -> Any:
        m = ee.Date(m)
        col = (
            ee.ImageCollection("NASA/GPM_L3/IMERG_MONTHLY_V07")
            .filterBounds(geom)
            .filterDate(m, m.advance(1, "month"))
        )
        days = m.advance(1, "month").difference(m, "day")
        rain = ee.Image(
            ee.Algorithms.If(
                col.size().gt(0),
                ee.Image(col.first())
                .select("precipitation")
                .multiply(days)
                .multiply(24)
                .rename("rain_mm"),
                _empty_masked(ee, "rain_mm"),
            )
        )
        stats = _reduce_region(ee, rain, geom, 11132)
        return ee.Feature(
            None, {"month": m.format("YYYY-MM"), "rain_mm": stats.get("rain_mm")}
        )

    return _fc_to_df(ee.FeatureCollection(months.map(per_month)).getInfo(), ["rain_mm"])


def extract_era5_monthly(ee: Any, polygon: dict[str, Any], start: str, end: str) -> pd.DataFrame:
    """ERA5-Land monthly: precip, ET, PET (m → mm), temperature_2m (°C)."""
    geom = _geom(ee, polygon)
    months = _month_list(ee, start, end)
    bands = [
        "total_precipitation_sum",
        "total_evaporation_sum",
        "potential_evaporation_sum",
        "temperature_2m",
        "volumetric_soil_water_layer_1",
    ]
    out_bands = [
        "era5_precip_mm",
        "era5_evap_mm",
        "era5_pet_mm",
        "era5_t2m_c",
        "era5_soil_water",
    ]

    def per_month(m: Any) -> Any:
        m = ee.Date(m)
        col = (
            ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY_AGGR")
            .filterBounds(geom)
            .filterDate(m, m.advance(1, "month"))
        )

        def scale_img(raw: Any) -> Any:
            img = ee.Image(raw).select(bands)
            flows = (
                img.select(
                    [
                        "total_precipitation_sum",
                        "total_evaporation_sum",
                        "potential_evaporation_sum",
                    ]
                )
                .multiply(1000)
                .rename(["era5_precip_mm", "era5_evap_mm", "era5_pet_mm"])
            )
            t2m = img.select("temperature_2m").subtract(273.15).rename("era5_t2m_c")
            soil = img.select("volumetric_soil_water_layer_1").rename("era5_soil_water")
            return flows.addBands(t2m).addBands(soil)

        empty = (
            _empty_masked(ee, out_bands[0])
            .addBands(_empty_masked(ee, out_bands[1]))
            .addBands(_empty_masked(ee, out_bands[2]))
            .addBands(_empty_masked(ee, out_bands[3]))
            .addBands(_empty_masked(ee, out_bands[4]))
        )
        scaled = ee.Image(
            ee.Algorithms.If(col.size().gt(0), scale_img(col.first()), empty)
        )
        stats = _reduce_region(ee, scaled, geom, 11132)
        return ee.Feature(
            None,
            {
                "month": m.format("YYYY-MM"),
                "era5_precip_mm": stats.get("era5_precip_mm"),
                "era5_evap_mm": stats.get("era5_evap_mm"),
                "era5_pet_mm": stats.get("era5_pet_mm"),
                "era5_t2m_c": stats.get("era5_t2m_c"),
                "era5_soil_water": stats.get("era5_soil_water"),
            },
        )

    return _fc_to_df(
        ee.FeatureCollection(months.map(per_month)).getInfo(),
        out_bands,
    )


def extract_srtm(ee: Any, polygon: dict[str, Any]) -> pd.DataFrame:
    """SRTM elevation (m) and slope (degrees → percent). Static — one row month=static."""
    geom = _geom(ee, polygon)
    dem = ee.Image("USGS/SRTMGL1_003")
    slope_deg = ee.Terrain.slope(dem).rename("slope_deg")
    # percent slope = tan(degrees) × 100
    slope_pct = slope_deg.multiply(math.pi / 180).tan().multiply(100).rename("slope_pct")
    img = dem.rename("elevation_m").addBands(slope_pct).addBands(slope_deg)
    stats = _reduce_region(ee, img, geom, 30).getInfo()
    rows = [
        {"month": "static", "variable": k, "value": stats.get(k)}
        for k in ("elevation_m", "slope_pct", "slope_deg")
    ]
    return pd.DataFrame(rows)


def extract_grace_monthly(ee: Any, polygon: dict[str, Any], start: str, end: str) -> pd.DataFrame:
    """GRACE/FO mascon liquid water equivalent thickness (cm). Regional context only."""
    geom = _geom(ee, polygon)
    months = _month_list(ee, start, end)

    def per_month(m: Any) -> Any:
        m = ee.Date(m)
        col = (
            ee.ImageCollection("NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI")
            .filterBounds(geom)
            .filterDate(m, m.advance(1, "month"))
        )
        img = ee.Image(
            ee.Algorithms.If(
                col.size().gt(0),
                col.mean().select("lwe_thickness").rename("grace_lwe_cm"),
                _empty_masked(ee, "grace_lwe_cm"),
            )
        )
        stats = _reduce_region(ee, img, geom, 100000)
        return ee.Feature(
            None,
            {"month": m.format("YYYY-MM"), "grace_lwe_cm": stats.get("grace_lwe_cm")},
        )

    return _fc_to_df(
        ee.FeatureCollection(months.map(per_month)).getInfo(), ["grace_lwe_cm"]
    )


def extract_ee_field(
    polygon: dict[str, Any],
    *,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, pd.DataFrame]:
    """Run all Phase-2 EE extractions for a field polygon.

    Returns
    -------
    dict[str, pd.DataFrame]
        Keys: s2, landsat, modis, smap, imerg, era5, srtm, grace.
        Each DF has columns month, variable, value (partial tidy).
    """
    ee = _require_ee()
    if start is None or end is None:
        start, end = analysis_window(ee, polygon)

    # Cap lagging archives to their own last month (do not shrink S2/ERA5/POWER).
    imerg_last = collection_last_month(ee, polygon, "NASA/GPM_L3/IMERG_MONTHLY_V07")
    grace_last = collection_last_month(ee, polygon, "NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI")
    imerg_end = _cap_end(end, imerg_last)
    grace_end = _cap_end(end, grace_last)

    return {
        "s2": extract_s2_monthly(ee, polygon, start, end),
        "landsat": extract_landsat_monthly(ee, polygon, start, end),
        "modis": extract_modis_monthly(ee, polygon, start, end),
        "smap": extract_smap_monthly(ee, polygon, start, end),
        "imerg": extract_imerg_monthly(ee, polygon, start, imerg_end),
        "era5": extract_era5_monthly(ee, polygon, start, end),
        "srtm": extract_srtm(ee, polygon),
        "grace": extract_grace_monthly(ee, polygon, start, grace_end),
        "_window": pd.DataFrame(
            [
                {
                    "start": start,
                    "end": end,
                    "imerg_end": imerg_end,
                    "grace_end": grace_end,
                }
            ]
        ),
    }
