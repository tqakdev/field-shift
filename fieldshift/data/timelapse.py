"""Monthly Sentinel-2 NDVI / RGB composites → GIF via getVideoThumbURL."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.request import urlretrieve

from fieldshift.data.ee_client import init_ee
from fieldshift.data.extract_ee import _geom, _mask_s2_with_cs, _s2_cs_linked

CACHE_DIR = Path(__file__).resolve().parents[1] / "cache"


def _month_starts_client(start: str, end: str) -> list[tuple[str, str]]:
    """Inclusive month windows as (YYYY-MM-01, next-month) pairs (client-side)."""
    import pandas as pd

    idx = pd.date_range(start=start[:10], end=end[:10], freq="MS")
    pairs: list[tuple[str, str]] = []
    for ts in idx:
        m0 = ts.strftime("%Y-%m-%d")
        m1 = (ts + pd.offsets.MonthBegin(1)).strftime("%Y-%m-%d")
        pairs.append((m0, m1))
    return pairs


def _s2_monthly_collection(
    ee: Any,
    polygon: dict[str, Any],
    start: str,
    end: str,
    *,
    mode: str = "ndvi",
) -> Any:
    """Build a monthly mosaic ImageCollection for video (NDVI or RGB)."""
    geom = _geom(ee, polygon)
    months = _month_starts_client(start, end)
    s2 = _s2_cs_linked(ee, geom, start, end).map(lambda img: _mask_s2_with_cs(ee, img))

    images = []
    for m0, m1 in months:
        month_col = s2.filterDate(m0, m1)
        if mode == "ndvi":
            mosaic = (
                month_col.map(
                    lambda img: img.normalizedDifference(["B8", "B4"]).rename("NDVI")
                )
                .median()
                .clip(geom)
                .visualize(
                    min=0,
                    max=0.8,
                    palette=["#a6611a", "#dfc27d", "#f5f5f5", "#80cdc1", "#018571"],
                )
            )
        else:
            mosaic = (
                month_col.median()
                .clip(geom)
                .visualize(bands=["B4", "B3", "B2"], min=0, max=3000)
            )
        mosaic = mosaic.set("system:time_start", ee.Date(m0).millis())
        images.append(mosaic)

    return ee.ImageCollection(images)


def make_s2_gif_url(
    polygon: dict[str, Any],
    start: str,
    end: str,
    *,
    mode: str = "ndvi",
    dimensions: int = 512,
    frames_per_second: int = 2,
) -> str:
    """Return Earth Engine video thumb URL for monthly S2 composites."""
    ee_mod = init_ee()
    if not ee_mod.initialized:
        raise RuntimeError(ee_mod.error or "Earth Engine is not initialized")
    import ee

    geom = _geom(ee, polygon)
    col = _s2_monthly_collection(ee, polygon, start, end, mode=mode)
    region = geom.bounds().getInfo()["coordinates"]
    return col.getVideoThumbURL(
        {
            "dimensions": dimensions,
            "region": region,
            "framesPerSecond": frames_per_second,
            "format": "gif",
        }
    )


def download_s2_gif(
    polygon: dict[str, Any],
    start: str,
    end: str,
    *,
    mode: str = "ndvi",
    field_id: str = "demo",
    cache_dir: Path | None = None,
) -> Path:
    """Download GIF into fieldshift/cache/ and return the local path."""
    out_dir = Path(cache_dir) if cache_dir is not None else CACHE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{field_id}_{mode}_{start[:7]}_{end[:7]}.gif"
    if path.exists() and path.stat().st_size > 0:
        return path
    url = make_s2_gif_url(polygon, start, end, mode=mode)
    urlretrieve(url, path)
    return path
