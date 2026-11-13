"""Unit conversion formulas + harmonize schema / climatology (no network)."""

from __future__ import annotations

import math

import pandas as pd
import pytest
from fieldshift.data.harmonize import VARIABLE_META, add_water_balance, harmonize


def test_imerg_mm_hr_to_mm_month() -> None:
    """IMERG monthly band is mean mm/hr → mm/month = mm/hr × days × 24."""
    mm_hr = 0.1
    days = 31
    assert mm_hr * days * 24 == pytest.approx(74.4)


def test_era5_m_to_mm_and_kelvin_to_c() -> None:
    precip_m = 0.05
    assert precip_m * 1000 == pytest.approx(50.0)
    kelvin = 293.15
    assert kelvin - 273.15 == pytest.approx(20.0)


def test_modis_ndvi_scale() -> None:
    raw = 5000
    assert raw * 0.0001 == pytest.approx(0.5)


def test_landsat_sr_scale() -> None:
    dn = 10000
    assert dn * 0.0000275 + (-0.2) == pytest.approx(0.075)


def test_slope_percent_from_degrees() -> None:
    deg = 45.0
    pct = math.tan(math.radians(deg)) * 100
    assert pct == pytest.approx(100.0)


def test_harmonize_schema_and_climatology() -> None:
    ee_tables = {
        "imerg": pd.DataFrame(
            [
                {"month": "2023-01", "variable": "rain_mm", "value": 40.0},
                {"month": "2023-02", "variable": "rain_mm", "value": 30.0},
                {"month": "2024-01", "variable": "rain_mm", "value": 50.0},
            ]
        ),
        "era5": pd.DataFrame(
            [
                {"month": "2023-01", "variable": "era5_pet_mm", "value": -20.0},
                {"month": "2023-02", "variable": "era5_pet_mm", "value": -10.0},
                {"month": "2024-01", "variable": "era5_pet_mm", "value": -25.0},
            ]
        ),
        "srtm": pd.DataFrame(
            [{"month": "static", "variable": "elevation_m", "value": 300.0}]
        ),
        "_window": pd.DataFrame([{"start": "2023-01-01", "end": "2024-01-01"}]),
    }
    power_monthly = pd.DataFrame(
        {"T2M": [1.0, 2.0]},
        index=pd.PeriodIndex(["2023-01", "2023-02"], freq="M"),
    )
    tidy, clim = harmonize(ee_tables, power_monthly)

    assert list(tidy.columns) == ["month", "variable", "value", "unit", "source", "n_obs"]
    assert "water_balance_mm" in set(tidy["variable"])
    # Jan 2023: 40 - abs(-20) = 20
    wb = tidy[(tidy["variable"] == "water_balance_mm") & (tidy["month"] == "2023-01")]
    assert float(wb["value"].iloc[0]) == pytest.approx(20.0)

    for var in tidy["variable"].unique():
        if var in VARIABLE_META:
            unit, source = VARIABLE_META[var]
            sub = tidy[tidy["variable"] == var]
            assert (sub["unit"] == unit).all()
            assert (sub["source"] == source).all()

    # Climatology: calendar month 1 mean rain = (40+50)/2 = 45
    jan_rain = clim[(clim["calendar_month"] == 1) & (clim["variable"] == "rain_mm")]
    assert float(jan_rain["mean"].iloc[0]) == pytest.approx(45.0)
    assert float(jan_rain["n"].iloc[0]) == pytest.approx(2.0)
    assert "std" in clim.columns


def test_add_water_balance_empty() -> None:
    empty = pd.DataFrame(columns=["month", "variable", "value", "unit", "source", "n_obs"])
    out = add_water_balance(empty)
    assert out.empty
