"""Plotly chart helpers for conditions and strategy scores."""

from __future__ import annotations

import plotly.graph_objects as go
from fieldshift.models import FieldConditions, ScoreSet

MONTH_LABELS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]


def conditions_figure(conditions: FieldConditions) -> go.Figure:
    """12-month NDVI / soil moisture / rain / water-balance chart."""
    profile = conditions.monthly_profile
    labels = [MONTH_LABELS[p.month - 1] for p in profile]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[p.ndvi for p in profile],
            name="NDVI",
            mode="lines",
            line={"color": "#6b7c3c", "width": 2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[p.soil_moisture for p in profile],
            name="Soil moisture",
            mode="lines",
            line={"color": "#4a7c9b", "width": 2},
        )
    )
    fig.add_trace(
        go.Bar(
            x=labels,
            y=[p.rain_mm for p in profile],
            name="Rain (mm)",
            marker_color="#c5dce8",
            yaxis="y2",
            opacity=0.85,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=[p.water_balance_mm for p in profile],
            name="Water balance (mm)",
            mode="lines",
            line={"color": "#6e4b2e", "width": 2, "dash": "dash"},
            yaxis="y2",
        )
    )
    fig.update_layout(
        margin={"l": 40, "r": 40, "t": 30, "b": 30},
        height=360,
        legend={"orientation": "h", "y": 1.12},
        yaxis={"title": "NDVI / moisture", "range": [0, 1]},
        yaxis2={"title": "mm", "overlaying": "y", "side": "right"},
        plot_bgcolor="#f6f3ec",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def scores_bar(scores: ScoreSet) -> go.Figure:
    """Small horizontal-ish criterion score bar chart."""
    names = ["Water", "Soil", "Erosion", "Pest", "Climate", "Income"]
    values = [
        scores.water,
        scores.soil_health,
        scores.erosion,
        scores.pest_break,
        scores.climate_fit,
        scores.income,
    ]
    fig = go.Figure(
        go.Bar(x=names, y=values, marker_color="#6b7c3c", name="Score")
    )
    fig.update_layout(
        margin={"l": 20, "r": 10, "t": 10, "b": 30},
        height=200,
        yaxis={"range": [0, 1]},
        showlegend=False,
        plot_bgcolor="#f6f3ec",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig
