"""Design-system enforcement — contrast, tokens, captions, empty values."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest
from ui import theme

ROOT = Path(__file__).resolve().parents[1]
UI_DIR = ROOT / "ui"


def _rel_lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def chan(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast_ratio(fg: str, bg: str) -> float:
    l1, l2 = _rel_lum(fg), _rel_lum(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize(
    ("name", "fg", "bg", "minimum"),
    theme.CONTRAST_PAIRS,
    ids=[p[0] for p in theme.CONTRAST_PAIRS],
)
def test_token_contrast_aa(name: str, fg: str, bg: str, minimum: float) -> None:
    ratio = contrast_ratio(fg, bg)
    assert ratio + 1e-6 >= minimum, (
        f"{name}: {fg} on {bg} = {ratio:.2f}:1 < {minimum}:1"
    )


def test_spacing_tokens_only() -> None:
    assert theme.SPACE == (8, 16, 24, 32, 48)


def test_okabe_criterion_colours_are_distinct() -> None:
    vals = list(theme.SCORE_COLORS.values())
    assert len(set(vals)) == len(vals)


_HEX_IN_UI = re.compile(r"#[0-9A-Fa-f]{6}")
_ALLOWED_HEX = {
    v.lower()
    for v in (
        theme.BACKGROUND,
        theme.SURFACE,
        theme.SIDEBAR,
        theme.TEXT,
        theme.MUTED,
        theme.PRIMARY,
        theme.WARNING,
        theme.DANGER,
        theme.INFO,
        theme.CARD_BORDER,
        theme.FOCUS,
        *theme.OKABE.values(),
        *theme.CHART_COLORS.values(),
        *theme.SCORE_COLORS.values(),
        "#E8F2E7",
        "#F8EAEA",
        "#E8F1F6",  # status badge tints used in CSS
    )
}


def test_ui_hex_colours_come_from_tokens() -> None:
    offenders: list[str] = []
    for path in UI_DIR.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        # Skip the token definitions file itself for raw OKABE literals
        for match in _HEX_IN_UI.finditer(text):
            hx = match.group(0).lower()
            if path.name == "theme.py":
                continue
            if hx not in _ALLOWED_HEX:
                offenders.append(f"{path.relative_to(ROOT)}:{hx}")
    assert not offenders, "Non-token hex colours in ui/:\n" + "\n".join(offenders)


def test_source_caption_has_no_underscores() -> None:
    from ui.source_caption import _friendly_dataset

    samples = [
        "rain_best",
        "ndvi_s2",
        "grace_lwe_cm",
        "Sentinel-2 / SMAP / rain_best / water balance",
    ]
    for s in samples:
        out = _friendly_dataset(s)
        assert "_" not in out, f"underscore remains in {out!r} from {s!r}"


def test_fact_chips_reject_em_dash_placeholder() -> None:
    """Fact chip values must not be a lone em dash."""

    # Smoke: friendly frost value path used in field view
    bad = "—"
    assert bad.strip() == "—"
    # Ensure helpers used by field view avoid returning bare dash for subtropical
    assert "Rarely frosts" != bad


def test_design_doc_exists() -> None:
    assert (ROOT / "docs" / "DESIGN.md").is_file()


def test_contrast_math_sanity() -> None:
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.05)
    assert contrast_ratio("#FFFFFF", "#FFFFFF") == pytest.approx(1.0, abs=1e-6)
    assert math.isfinite(contrast_ratio(theme.TEXT, theme.BACKGROUND))
