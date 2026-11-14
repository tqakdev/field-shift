"""Monthly Sentinel-2 NDVI / RGB composites → GIF.

Prefers EE monthly cloud-masked thumbs (with month labels). Falls back to
``getVideoThumbURL``, then to a chart-style GIF from field-mean NDVI when
thumbnail/video APIs are unavailable.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from urllib.request import urlretrieve

import pandas as pd

from fieldshift.data.ee_client import init_ee
from fieldshift.data.extract_ee import _geom, _mask_s2_with_cs, _s2_cs_linked

CACHE_DIR = Path(__file__).resolve().parents[1] / "cache"

_NDVI_PALETTE_HEX = ["#a6611a", "#dfc27d", "#f5f5f5", "#80cdc1", "#018571"]
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


def _visualize_month(
    ee: Any,
    month_col: Any,
    geom: Any,
    *,
    mode: str,
) -> Any:
    """3-band RGB visualize for one month; placeholder if the month is empty."""
    if mode == "ndvi":
        real = (
            month_col.map(
                lambda img: img.normalizedDifference(["B8", "B4"]).rename("NDVI")
            )
            .median()
            .clip(geom)
            .visualize(min=0, max=0.8, palette=_NDVI_PALETTE_HEX)
        )
        empty = (
            ee.Image.constant(0)
            .rename("NDVI")
            .clip(geom)
            .visualize(min=0, max=0.8, palette=_NDVI_PALETTE_HEX)
        )
    else:
        real = (
            month_col.median()
            .clip(geom)
            .visualize(bands=["B4", "B3", "B2"], min=0, max=3000)
        )
        empty = (
            ee.Image.constant([0, 0, 0])
            .rename(["B4", "B3", "B2"])
            .clip(geom)
            .visualize(bands=["B4", "B3", "B2"], min=0, max=3000)
        )
    return ee.Algorithms.If(month_col.size().gt(0), real, empty)


def _s2_monthly_collection(
    ee: Any,
    polygon: dict[str, Any],
    start: str,
    end: str,
    *,
    mode: str = "ndvi",
) -> Any:
    """Build a homogeneous monthly mosaic ImageCollection (NDVI or RGB)."""
    geom = _geom(ee, polygon)
    months = _month_starts_client(start, end)
    s2 = _s2_cs_linked(ee, geom, start, end).map(lambda img: _mask_s2_with_cs(ee, img))

    images = []
    for m0, m1 in months:
        month_col = s2.filterDate(m0, m1)
        mosaic = ee.Image(_visualize_month(ee, month_col, geom, mode=mode))
        mosaic = mosaic.set("system:time_start", ee.Date(m0).millis())
        mosaic = mosaic.set("month_label", m0[:7])
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
            "dimensions": min(512, int(dimensions)),
            "region": region,
            "framesPerSecond": frames_per_second,
            "format": "gif",
        }
    )


def _font(size: int = 22) -> Any:
    from PIL import ImageFont

    for path in (
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _label_frame(img: Any, month_label: str, *, mode: str) -> Any:
    """Draw a month label band on a Pillow RGB image."""
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img)
    w, h = img.size
    band_h = max(36, h // 10)
    draw.rectangle([0, h - band_h, w, h], fill=(20, 24, 18))
    title = "Sentinel-2 NDVI" if mode == "ndvi" else "Sentinel-2 RGB"
    draw.text((10, 8), title, fill=(255, 255, 255), font=_font(14))
    draw.text((10, h - band_h + 8), month_label, fill=(255, 255, 255), font=_font(22))
    return img


def _download_labeled_thumb_gif(
    polygon: dict[str, Any],
    start: str,
    end: str,
    path: Path,
    *,
    mode: str = "ndvi",
    dimensions: int = 512,
) -> Path:
    """Download monthly thumbs, add month labels, stitch into a GIF."""
    from PIL import Image

    ee_mod = init_ee()
    if not ee_mod.initialized:
        raise RuntimeError(ee_mod.error or "Earth Engine is not initialized")
    import ee

    geom = _geom(ee, polygon)
    region = geom.bounds().getInfo()["coordinates"]
    dim = min(512, int(dimensions))
    months = _month_starts_client(start, end)
    s2 = _s2_cs_linked(ee, geom, start, end).map(lambda img: _mask_s2_with_cs(ee, img))

    frames: list[Image.Image] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for i, (m0, m1) in enumerate(months):
            month_col = s2.filterDate(m0, m1)
            mosaic = ee.Image(_visualize_month(ee, month_col, geom, mode=mode))
            url = mosaic.getThumbURL(
                {"dimensions": dim, "region": region, "format": "png"}
            )
            frame_path = tmp_path / f"frame_{i:03d}.png"
            urlretrieve(url, frame_path)
            img = Image.open(frame_path).convert("RGB")
            frames.append(_label_frame(img, m0[:7], mode=mode))

    if not frames:
        raise RuntimeError("No monthly Sentinel-2 frames for GIF")
    path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=500,
        loop=0,
        optimize=True,
    )
    return path


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
    """Chart-style GIF from Sentinel-2 field-mean NDVI (offline fallback)."""
    from PIL import Image, ImageDraw

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
    if len(sub) > 18:
        sub = sub.iloc[-18:]

    frames: list[Image.Image] = []
    w, h = size
    font = _font(22)
    font_sm = _font(14)

    for _, row in sub.iterrows():
        ndvi = float(row["value"])
        color = _ndvi_to_rgb(ndvi, mode=mode)
        img = Image.new("RGB", (w, h), color)
        draw = ImageDraw.Draw(img)
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
    force: bool = False,
    dimensions: int = 512,
) -> Path:
    """Download or render GIF into fieldshift/cache/ and return the local path."""
    out_dir = Path(cache_dir) if cache_dir is not None else CACHE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / (
        out_name or f"{field_id}_{mode}_{start[:7]}_{end[:7]}.gif"
    )
    if path.exists() and path.stat().st_size > 0 and not force:
        return path
    if force and path.exists():
        path.unlink()

    dim = min(512, int(dimensions))

    # 1) Labeled monthly thumbs (preferred — month label on each frame)
    try:
        print(f"  EE monthly thumbs ({mode}, {dim}px) …")
        return _download_labeled_thumb_gif(
            polygon, start, end, path, mode=mode, dimensions=dim
        )
    except Exception as thumb_exc:  # noqa: BLE001
        print(f"  EE labeled thumbs unavailable ({thumb_exc})")

    # 2) Video thumb (no per-frame text label)
    try:
        print(f"  EE getVideoThumbURL ({mode}) …")
        url = make_s2_gif_url(polygon, start, end, mode=mode, dimensions=dim)
        urlretrieve(url, path)
        if path.exists() and path.stat().st_size > 0:
            return path
    except Exception as video_exc:  # noqa: BLE001
        print(f"  EE video thumb unavailable ({video_exc})")

    # 3) Chart-style fallback from tidy NDVI
    if tidy is None:
        raise RuntimeError(
            "EE GIF unavailable and no tidy NDVI provided for local render"
        )
    print("  rendering chart-GIF from Sentinel-2 field-mean NDVI …")
    return render_gif_from_tidy(tidy, path, mode=mode, start=start, end=end)
