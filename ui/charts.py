"""Plotly chart helpers — Okabe–Ito colour-blind-safe palette."""

from __future__ import annotations

import plotly.graph_objects as go
from fieldshift.models import FieldConditions, ScoreSet

from ui.theme import (
    BACKGROUND,
    CARD_BORDER,
    CHART_COLORS,
    MUTED,
    PRIMARY,
    SCORE_COLORS,
    SIDEBAR,
    SURFACE,
    TEXT,
)

MONTH_LABELS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]

_FONT = {
    "family": "Source Sans 3, Helvetica Neue, Helvetica, Arial, sans-serif",
    "size": 13,
    "color": TEXT,
}


def conditions_takeaway(conditions: FieldConditions) -> str:
    """One-sentence takeaway above the seasonal chart."""
    feat = conditions.features
    bare = feat.bare_months_label.split("(")[0].strip() if feat.bare_months_label else ""
    rain = feat.rain_annual_mm
    if bare and rain:
        return (
            f"Satellites show {bare.lower()}, with about {rain:.0f} mm of rain "
            f"in a typical year across this field."
        )
    if rain:
        return (
            f"This field receives about {rain:.0f} mm of rain in a typical year; "
            f"greenness peaks in the main growing season."
        )
    return (
        "Plant greenness, rainfall, and water balance together show when the "
        "field is covered, wet, or under stress."
    )


def conditions_figure(conditions: FieldConditions) -> go.Figure:
    """Combined 12-month chart: plant greenness, rain, water balance + windows."""
    profile = sorted(conditions.monthly_profile, key=lambda p: p.month)
    xs = list(range(1, 13))
    fig = go.Figure()

    bare = set(conditions.features.bare_months or [])
    stress = set(conditions.features.stress_months or [])
    for m in bare:
        fig.add_vrect(
            x0=m - 0.5,
            x1=m + 0.5,
            fillcolor="rgba(230, 159, 0, 0.12)",
            line_width=0,
            layer="below",
        )
    for m in stress:
        fig.add_vrect(
            x0=m - 0.5,
            x1=m + 0.5,
            fillcolor="rgba(213, 94, 0, 0.10)",
            line_width=0,
            layer="below",
        )

    ndvi_vals = [p.ndvi for p in profile]
    rain_vals = [p.rain_mm for p in profile]
    wb_vals = [p.water_balance_mm for p in profile]
    green = CHART_COLORS["greenness"]
    rain_c = CHART_COLORS["rain"]
    wb_c = CHART_COLORS["water_balance"]

    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ndvi_vals,
            name="Plant greenness (0–1)",
            mode="lines+markers",
            line={"color": green, "width": 2.5},
            marker={"size": 7, "symbol": "circle", "color": green},
            hovertemplate=(
                "Plant greenness %{y:.2f}<br>"
                "Source: Sentinel-2 NDVI<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Bar(
            x=xs,
            y=rain_vals,
            name="Rain (mm)",
            marker_color=rain_c,
            opacity=0.45,
            yaxis="y2",
            hovertemplate=(
                "Rain %{y:.0f} mm<br>"
                "Source: best available rainfall<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=wb_vals,
            name="Water balance (mm)",
            mode="lines",
            line={"color": wb_c, "width": 2, "dash": "dash"},
            yaxis="y2",
            hovertemplate=(
                "Water balance %{y:.0f} mm<br>"
                "Rain minus evaporative demand · source: field water balance"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        margin={"l": 64, "r": 72, "t": 40, "b": 48},
        height=400,
        legend={
            "orientation": "h",
            "y": 1.14,
            "x": 0,
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"size": 13, "color": TEXT},
        },
        xaxis={
            "tickmode": "array",
            "tickvals": xs,
            "ticktext": MONTH_LABELS,
            "title": {"text": "Month", "font": {"size": 13, "color": MUTED}},
            "gridcolor": "rgba(0,0,0,0)",
            "zeroline": False,
        },
        yaxis={
            "title": {
                "text": "Plant greenness (0–1)",
                "font": {"size": 13, "color": MUTED},
            },
            "range": [0, 1],
            "gridcolor": SIDEBAR,
            "zeroline": False,
        },
        yaxis2={
            "title": {
                "text": "Rain / water balance (mm)",
                "font": {"size": 13, "color": MUTED},
            },
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
            "zeroline": False,
        },
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=_FONT,
        hovermode="x unified",
    )
    return fig


def scores_bar(scores: ScoreSet, *, height: int = 175) -> go.Figure:
    """Compact horizontal criterion score bar (6 criteria, fixed colours)."""
    items = [
        ("Water", scores.water, SCORE_COLORS["water"]),
        ("Soil", scores.soil_health, SCORE_COLORS["soil_health"]),
        ("Erosion", scores.erosion, SCORE_COLORS["erosion"]),
        ("Pest", scores.pest_break, SCORE_COLORS["pest_break"]),
        ("Climate", scores.climate_fit, SCORE_COLORS["climate_fit"]),
        ("Income", scores.income, SCORE_COLORS["income"]),
    ]
    fig = go.Figure(
        go.Bar(
            y=[i[0] for i in items],
            x=[i[1] for i in items],
            orientation="h",
            marker_color=[i[2] for i in items],
            text=[f"{i[1]:.2f}" for i in items],
            textposition="outside",
            cliponaxis=False,
        )
    )
    fig.update_layout(
        margin={"l": 58, "r": 36, "t": 6, "b": 6},
        height=height,
        xaxis={
            "range": [0, 1.2],
            "title": None,
            "showticklabels": False,
            "gridcolor": SIDEBAR,
        },
        yaxis={"autorange": "reversed"},
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font={**_FONT, "size": 12},
    )
    return fig


def pipeline_figure() -> go.Figure:
    """Simple left-to-right pipeline diagram for How it works."""
    steps = [
        "Earth\ndata",
        "Field ×\nmonth",
        "Bare /\nstress",
        "SI\nanomalies",
        "Rotation\ncandidates",
        "Scored\ncards",
    ]
    fig = go.Figure()
    for i, label in enumerate(steps):
        fig.add_shape(
            type="rect",
            x0=i * 1.35,
            x1=i * 1.35 + 1.15,
            y0=0,
            y1=1,
            fillcolor=SURFACE if i % 2 == 0 else BACKGROUND,
            line={"color": CARD_BORDER, "width": 1},
        )
        fig.add_annotation(
            x=i * 1.35 + 0.575,
            y=0.5,
            text=label,
            showarrow=False,
            font={"size": 12, "color": TEXT, "family": _FONT["family"]},
        )
        if i < len(steps) - 1:
            fig.add_annotation(
                x=i * 1.35 + 1.22,
                y=0.5,
                text="→",
                showarrow=False,
                font={"size": 16, "color": PRIMARY},
            )
    fig.update_layout(
        height=110,
        margin={"l": 8, "r": 8, "t": 8, "b": 8},
        xaxis={"visible": False, "range": [-0.1, 8.2]},
        yaxis={"visible": False, "range": [-0.2, 1.2]},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig
