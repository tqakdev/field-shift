"""IsolationForest 'SI' anomaly detection on field-month feature vectors.

Pure sklearn — fixed random_state. Growing-season flags = crop vulnerability;
off-season flags are reported separately (not as crop stress).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

RANDOM_STATE = 42
CONTAMINATION = 0.08


def _month_feature_frame(features: dict[str, Any]) -> pd.DataFrame:
    series = features.get("series", {})
    ndvi = series.get("ndvi", pd.Series(dtype=float))
    sm = series.get("sm_surface", pd.Series(dtype=float))
    rain = series.get("rain", pd.Series(dtype=float))
    wb = series.get("water_balance", pd.Series(dtype=float))
    t2m = series.get("t2m_max_mean_daily", series.get("t2m_max", pd.Series(dtype=float)))

    def z(s: pd.Series) -> pd.Series:
        if s.empty:
            return s
        cal = s.index.month
        mu = s.groupby(cal).transform("mean")
        sd = s.groupby(cal).transform("std").replace(0, np.nan)
        return (s - mu) / sd

    frame = pd.DataFrame(
        {
            "ndvi_anom": z(ndvi),
            "sm_anom": z(sm),
            "rain_anom": z(rain),
            "wb_anom": z(wb),
            "heat": t2m.reindex(ndvi.index) if not ndvi.empty else t2m,
        }
    ).dropna(how="all")
    return frame


def detect_anomalies(features: dict[str, Any]) -> dict[str, Any]:
    """Fit IsolationForest; split growing-season vs off-season flags."""
    frame = _month_feature_frame(features)
    gs_months = set(features.get("growing_season_months") or [])
    if not gs_months:
        # fallback from series climatology
        ndvi = features.get("series", {}).get("ndvi", pd.Series(dtype=float))
        t2m = features.get("series", {}).get("t2m_mean", pd.Series(dtype=float))
        for m in range(1, 13):
            ndvi_m = ndvi[ndvi.index.month == m] if not ndvi.empty else pd.Series(dtype=float)
            t_m = t2m[t2m.index.month == m] if not t2m.empty else pd.Series(dtype=float)
            if (len(ndvi_m) and float(ndvi_m.mean()) > 0.4) or (
                len(t_m) and float(t_m.mean()) > 5.0
            ):
                gs_months.add(m)

    if len(frame) < 24:
        return {
            "flagged_growing_season": [],
            "flagged_off_season": [],
            "vulnerable_seasons": [],
            "contamination": CONTAMINATION,
            "n_months": int(len(frame)),
            "n_years": int(frame.index.year.nunique()) if len(frame) else 0,
            "uncertainty": (
                "Too few months to fit the anomaly model reliably; "
                "treat SI flags as unavailable."
            ),
        }

    X = frame.fillna(0.0).to_numpy()
    model = IsolationForest(
        contamination=CONTAMINATION,
        random_state=RANDOM_STATE,
        n_estimators=100,
    )
    pred = model.fit_predict(X)
    scores = model.decision_function(X)
    growing, off = [], []
    for i, (idx, row) in enumerate(frame.iterrows()):
        if pred[i] != -1:
            continue
        contrib = sorted(
            (
                (name, float(abs(row[name])) if pd.notna(row[name]) else 0.0)
                for name in ("ndvi_anom", "sm_anom", "rain_anom", "wb_anom", "heat")
            ),
            key=lambda t: t[1],
            reverse=True,
        )
        entry = {
            "month": str(idx),
            "calendar_month": int(idx.month),
            "score": float(scores[i]),
            "contributing_variables": [c[0] for c in contrib[:3]],
            "contributor_magnitudes": {c[0]: c[1] for c in contrib[:3]},
        }
        if int(idx.month) in gs_months:
            growing.append(entry)
        else:
            entry["label"] = "off-season"
            off.append(entry)

    if growing:
        cal = pd.Series([f["calendar_month"] for f in growing])
        counts = cal.value_counts().sort_index()
        vulnerable = [
            {"calendar_month": int(m), "n_flags": int(n)} for m, n in counts.items()
        ]
    else:
        vulnerable = []

    n_years = int(frame.index.year.nunique())
    return {
        "flagged_growing_season": growing,
        "flagged_off_season": off,
        "vulnerable_seasons": vulnerable,
        "contamination": CONTAMINATION,
        "n_months": int(len(frame)),
        "n_years": n_years,
        "uncertainty": (
            f"IsolationForest (contamination={CONTAMINATION}, years={n_years}) "
            "flags unusual patterns, not causes. Growing-season flags = crop "
            "vulnerability; winter/off-season flags are separate."
        ),
    }
