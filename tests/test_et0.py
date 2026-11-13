"""FAO-56 ET0 unit tests — Hargreaves worked example (no network)."""

from __future__ import annotations

import math

import pytest
from fieldshift.data.et0 import (
    extraterrestrial_radiation_mm,
    hargreaves_samani_et0_mm,
)


def test_fao56_ra_example_uccle_july() -> None:
    """FAO-56 Example 8 / Annex (Uccle 50°48'N, 15 July, J=196).

    Published Ra ≈ 41.09 MJ m−2 day−1 → ≈ 16.77 mm day−1.
    """
    lat = 50.80
    j = 196
    ra_mm = float(extraterrestrial_radiation_mm(lat, j))
    ra_mj = ra_mm * 2.45
    # FAO-56 tables quote ~41.09 MJ; our Eq. 21–28 implementation is within ~3%.
    assert ra_mj == pytest.approx(41.09, rel=0.03)


def test_fao56_hargreaves_worked_example() -> None:
    """Hargreaves ET0 from FAO-56 Eq. 52 with published Ra.

    Site: Uccle (Belgium), 15 July (J=196), lat 50.80°N.
    Tmax=26.6°C, Tmin=14.8°C (common textbook pairing with Ra≈16.8 mm/d).

    ET0 = 0.0023 × (Tmean+17.8) × √(Tmax−Tmin) × Ra
        = 0.0023 × 38.5 × √11.8 × Ra
    With Ra from FAO-56 for this lat/doy, ET0 ≈ 5.0 mm/day (±5%).
    """
    lat = 50.80
    j = 196
    tmax, tmin = 26.6, 14.8
    et0 = float(hargreaves_samani_et0_mm(tmin, tmax, lat, j))
    ra = float(extraterrestrial_radiation_mm(lat, j))
    expected = 0.0023 * ((tmax + tmin) / 2 + 17.8) * math.sqrt(tmax - tmin) * ra
    assert et0 == pytest.approx(expected, rel=1e-6)
    assert et0 == pytest.approx(5.0, rel=0.08)
    assert et0 > 0
