"""Monthly Sentinel-2 NDVI / RGB composites → GIF.

Prefers EE video / thumb URLs. When the Cloud project lacks map/thumbnail
permission (common for locked-down service accounts), falls back to an
animated GIF built from already-extracted Sentinel-2 field-mean NDVI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.request import urlretrieve

import pandas as pd

from fieldshift.data.ee_client import init_ee
from fieldshift.data.extract_ee import _geom, _mask_s2_with_cs, _s2_cs_linked

CACHE_DIR = Path(__file__).resolve().parents[1] / "cache"

# NDVI brown→green palette (matches EE visualize defaults)
_NDVI_PALETTE = [
    (166, 97, 26),
    (223, 194, 125),
    (245, 245, 245),
    (128, 205, 193),
    (1, 133, 113),
]


def _month_starts_client(start: str, end: str) -> list[tuple[str, str]]:
    """Inclusive month windows as (YYYY-MM-01, next-month) pairs (client-side)."""
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


def _ndvi_to_rgb(ndvi: float, *, mode: str = "ndvi") -> tuple[int, int, int]:
    """Map NDVI [0, 0.8] onto the brown→green palette (or soft RGB green-up)."""
    t = max(0.0, min(1.0, float(ndvi) / 0.8))
    n = len(_NDVI_PALETTE) - 1
    x = t * n
    i = int(x)
    f = x - i
    if i >= n:
        r, g, b = _NDVI_PALETTE[-1]
    else:
        c0, c1 = _NDVI_PALETTE[i], _NDVI_PALETTE[i + 1]
        r = int(c0[0] + f * (c1[0] - c0[0]))
        g = int(c0[1] + f * (c1[1] - c0[1]))
        b = int(c0[2] + f * (c1[2] - c0[2]))
    if mode == "rgb":
        # Soft true-color-ish: soil brown → canopy green
        soil = (120, 95, 70)
        canopy = (45, 120, 55)
        r = int(soil[0] + t * (canopy[0] - soil[0]))
        g = int(soil[1] + t * (canopy[1] - soil[1]))
        b = int(soil[2] + t * (canopy[2] - soil[2]))
    return r, g, b


def render_gif_from_tidy(
    tidy: pd.DataFrame,
    path: Path,
    *,
    mode: str = "ndvi",
    start: str | None = None,
    end: str | None = None,
    size: tuple[int, int] = (480, 360),
) -> Path:
    """Build an animated GIF from Sentinel-2 field-mean NDVI in ``tidy``.

    Used when EE thumbnail/video APIs are unavailable. Each frame is a solid
    NDVI-coloured panel labelled with the month — values come from the same
    ``ndvi_s2`` series the engine uses.
    """
    from PIL import Image, ImageDraw, ImageFont

    sub = tidy[tidy["variable"] == "ndvi_s2"].dropna(subset=["value"]).copy()
    if sub.empty:
        sub = tidy[tidy["variable"] == "ndvi_modis"].dropna(subset=["value"]).copy()
    if sub.empty:
        raise RuntimeError("No NDVI series in tidy for GIF render")
    sub["month"] = sub["month"].astype(str)
    sub = sub.sort_values("month")
    if start:
        sub = sub[sub["month"] >= start[:7]]
    if end:
        sub = sub[sub["month"] <= end[:7]]
    # Cap at 18 frames
    if len(sub) > 18:
        sub = sub.iloc[-18:]

    frames: list[Image.Image] = []
    w, h = size
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
        font_sm = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    except OSError:
        font = ImageFont.load_default()
        font_sm = font

    for _, row in sub.iterrows():
        ndvi = float(row["value"])
        color = _ndvi_to_rgb(ndvi, mode=mode)
        img = Image.new("RGB", (w, h), color)
        draw = ImageDraw.Draw(img)
        # Dark band for text
        draw.rectangle([0, h - 56, w, h], fill=(20, 24, 18))
        label = f"{row['month']}  NDVI {ndvi:.2f}"
        title = (
            "Sentinel-2 NDVI (field mean)"
            if mode == "ndvi"
            else "S2 vegetation tone (from NDVI)"
        )
        draw.text((12, 12), title, fill=(255, 255, 255), font=font_sm)
        draw.text((12, h - 42), label, fill=(255, 255, 255), font=font)
        frames.append(img)

    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=450,
        loop=0,
        optimize=True,
    )
    return path


def download_s2_gif(
    polygon: dict[str, Any],
    start: str,
    end: str,
    *,
    mode: str = "ndvi",
    field_id: str = "demo",
    cache_dir: Path | None = None,
    out_name: str | None = None,
    tidy: pd.DataFrame | None = None,
) -> Path:
    """Download or render GIF into fieldshift/cache/ and return the local path."""
    out_dir = Path(cache_dir) if cache_dir is not None else CACHE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / (
        out_name or f"{field_id}_{mode}_{start[:7]}_{end[:7]}.gif"
    )
    if path.exists() and path.stat().st_size > 0:
        return path

    # Prefer EE video thumb when the project allows it.
    try:
        url = make_s2_gif_url(polygon, start, end, mode=mode)
        urlretrieve(url, path)
        if path.exists() and path.stat().st_size > 0:
            return path
    except Exception as video_exc:  # noqa: BLE001
        print(f"  EE video/thumb unavailable ({video_exc})")

    if tidy is None:
        raise RuntimeError(
            "EE GIF unavailable and no tidy NDVI provided for local render"
        )
    print("  rendering GIF from Sentinel-2 field-mean NDVI …")
    return render_gif_from_tidy(tidy, path, mode=mode, start=start, end=end)
