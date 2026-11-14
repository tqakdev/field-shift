"""Plotly chart helpers — NASA mission palette."""

from __future__ import annotations

import plotly.graph_objects as go
from fieldshift.models import FieldConditions, ScoreSet

from ui.theme import EARTH, NASA_BLUE, PANEL, PAPER, SCORE_COLORS

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

_FONT = {"family": "IBM Plex Sans, Helvetica, sans-serif", "size": 13, "color": "#0B1220"}


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
            fillcolor="rgba(139, 105, 20, 0.10)",
            line_width=0,
            layer="below",
        )
    for m in stress:
        fig.add_vrect(
            x0=m - 0.5,
            x1=m + 0.5,
            fillcolor="rgba(224, 60, 49, 0.08)",
            line_width=0,
            layer="below",
        )

    ndvi_vals = [p.ndvi for p in profile]
    rain_vals = [p.rain_mm for p in profile]
    wb_vals = [p.water_balance_mm for p in profile]

    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ndvi_vals,
            name="Plant greenness (0–1)",
            mode="lines+markers",
            line={"color": EARTH, "width": 2.5},
            marker={"size": 6, "color": EARTH},
            hovertemplate=(
                "Plant greenness %{y:.2f}<br>"
                "Leafiness from space (higher = greener)<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Bar(
            x=xs,
            y=rain_vals,
            name="Rain (mm)",
            marker_color="rgba(47, 111, 237, 0.40)",
            yaxis="y2",
            hovertemplate="Rain %{y:.0f} mm that month<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=wb_vals,
            name="Water balance (mm)",
            mode="lines",
            line={"color": NASA_BLUE, "width": 2, "dash": "dash"},
            yaxis="y2",
            hovertemplate=(
                "Water balance %{y:.0f} mm<br>"
                "Rain minus evaporative demand (negative = short)<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        margin={"l": 56, "r": 56, "t": 36, "b": 40},
        height=400,
        legend={
            "orientation": "h",
            "y": 1.16,
            "x": 0,
            "bgcolor": "rgba(0,0,0,0)",
        },
        xaxis={
            "tickmode": "array",
            "tickvals": xs,
            "ticktext": MONTH_LABELS,
            "title": "Month",
            "gridcolor": PANEL,
        },
        yaxis={
            "title": "Plant greenness (0–1)",
            "range": [0, 1],
            "gridcolor": PANEL,
        },
        yaxis2={
            "title": "Rain / water balance (mm)",
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
        },
        plot_bgcolor=PAPER,
        paper_bgcolor="rgba(0,0,0,0)",
        font=_FONT,
        hovermode="x unified",
    )
    return fig


def scores_bar(scores: ScoreSet, *, height: int = 175) -> go.Figure:
    """Compact horizontal criterion score bar (6 criteria, fixed colors)."""
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
        xaxis={"range": [0, 1.2], "title": None, "showticklabels": False, "gridcolor": PANEL},
        yaxis={"autorange": "reversed"},
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font={**_FONT, "size": 11},
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
            fillcolor=PANEL if i % 2 == 0 else "#F5F8FD",
            line={"color": NASA_BLUE, "width": 1},
        )
        fig.add_annotation(
            x=i * 1.35 + 0.575,
            y=0.5,
            text=label,
            showarrow=False,
            font={"size": 11, "color": "#0B1220", "family": "IBM Plex Sans"},
        )
        if i < len(steps) - 1:
            fig.add_annotation(
                x=i * 1.35 + 1.22,
                y=0.5,
                text="→",
                showarrow=False,
                font={"size": 16, "color": NASA_BLUE},
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
