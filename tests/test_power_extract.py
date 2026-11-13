"""NASA POWER parse / −999 / monthly aggregation (fixture only, no network)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fieldshift.data.extract_power import monthly_from_daily, parse_power_payload

FIXTURE = Path(__file__).parent / "fixtures" / "power_iowa_sample.json"


@pytest.fixture
def power_payload() -> dict:
    return json.loads(FIXTURE.read_text())


def test_parse_power_replaces_fill_with_nan(power_payload: dict) -> None:
    daily = parse_power_payload(power_payload)
    assert not daily.empty
    t2m_fill = daily.loc[pd.Timestamp("2024-01-02", tz="UTC"), "T2M"]
    rain_fill = daily.loc[pd.Timestamp("2024-01-03", tz="UTC"), "PRECTOTCORR"]
    assert np.isnan(t2m_fill)
    assert np.isnan(rain_fill)
    assert daily.loc[pd.Timestamp("2024-01-01", tz="UTC"), "T2M"] == pytest.approx(1.5)


def test_monthly_aggregation_rules(power_payload: dict) -> None:
    daily = parse_power_payload(power_payload)
    monthly = monthly_from_daily(daily)
    jan = monthly.loc[pd.Period("2024-01", freq="M")]
    # PRECTOTCORR sum: 1+2+NaN+3+4 = 10 (pandas skipna)
    assert jan["PRECTOTCORR"] == pytest.approx(10.0)
    # T2M mean over non-NaN: 1.5, 2.0, 3.0, 4.0 → 2.625
    assert jan["T2M"] == pytest.approx(2.625)
    # Monthly T2M_MAX/MIN are means of daily max/min (not monthly extremes)
    assert jan["T2M_MAX"] == pytest.approx((5.0 + 6.0 + 7.0 + 8.0 + 9.0) / 5.0)
    assert jan["T2M_MIN"] == pytest.approx((-2.0 + -1.0 + 0.0 + 1.0 + 2.0) / 5.0)
    feb = monthly.loc[pd.Period("2024-02", freq="M")]
    assert feb["PRECTOTCORR"] == pytest.approx(2.0)
