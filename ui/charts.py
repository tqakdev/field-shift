"""Plotly chart helpers for conditions and strategy scores."""

from __future__ import annotations

import plotly.graph_objects as go
from fieldshift.models import FieldConditions, ScoreSet

from ui.theme import LEAF, PAPER, SCORE_COLORS, SOIL, WHEAT_BG

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


def conditions_figure(conditions: FieldConditions) -> go.Figure:
    """Combined 12-month chart: plant greenness, rain, water balance + windows."""
    profile = sorted(conditions.monthly_profile, key=lambda p: p.month)
    xs = list(range(1, 13))
    labels = MONTH_LABELS
    fig = go.Figure()

    bare = set(conditions.features.bare_months or [])
    stress = set(conditions.features.stress_months or [])
    for m in bare:
        fig.add_vrect(
            x0=m - 0.5,
            x1=m + 0.5,
            fillcolor="rgba(139, 94, 60, 0.14)",
            line_width=0,
            layer="below",
            annotation_text="bare" if m == min(bare) else None,
            annotation_position="top left",
            annotation_font_size=10,
        )
    for m in stress:
        fig.add_vrect(
            x0=m - 0.5,
            x1=m + 0.5,
            fillcolor="rgba(178, 58, 58, 0.12)",
            line_width=0,
            layer="below",
        )

    fig.add_trace(
        go.Scatter(
            x=xs,
            y=[p.ndvi for p in profile],
            name="Plant greenness",
            mode="lines+markers",
            line={"color": LEAF, "width": 2.5},
            marker={"size": 6},
        )
    )
    fig.add_trace(
        go.Bar(
            x=xs,
            y=[p.rain_mm for p in profile],
            name="Rain",
            marker_color="rgba(58, 124, 165, 0.45)",
            yaxis="y2",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=[p.water_balance_mm for p in profile],
            name="Water balance",
            mode="lines",
            line={"color": SOIL, "width": 2, "dash": "dash"},
            yaxis="y2",
        )
    )

    fig.update_layout(
        margin={"l": 48, "r": 48, "t": 36, "b": 36},
        height=400,
        legend={
            "orientation": "h",
            "y": 1.14,
            "x": 0,
            "bgcolor": "rgba(0,0,0,0)",
        },
        xaxis={
            "tickmode": "array",
            "tickvals": xs,
            "ticktext": labels,
            "title": None,
        },
        yaxis={"title": "Plant greenness", "range": [0, 1]},
        yaxis2={"title": "mm", "overlaying": "y", "side": "right"},
        plot_bgcolor=PAPER,
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#2B2B2B", "size": 13},
        hovermode="x unified",
    )
    return fig


def scores_bar(scores: ScoreSet, *, height: int = 180) -> go.Figure:
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
        margin={"l": 60, "r": 36, "t": 8, "b": 8},
        height=height,
        xaxis={"range": [0, 1.15], "title": None, "showticklabels": False},
        yaxis={"autorange": "reversed"},
        showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font={"size": 12, "color": "#2B2B2B"},
    )
    return fig


def pipeline_figure() -> go.Figure:
    """Simple left-to-right pipeline diagram for How it works."""
    steps = [
        "Satellites &\nweather",
        "Field × month\nvalues",
        "Bare / stress\n/ frost",
        "SI anomalies",
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
            fillcolor=WHEAT_BG if i % 2 == 0 else "#e8f0e4",
            line={"color": LEAF, "width": 1},
        )
        fig.add_annotation(
            x=i * 1.35 + 0.575,
            y=0.5,
            text=label,
            showarrow=False,
            font={"size": 12, "color": "#2B2B2B"},
        )
        if i < len(steps) - 1:
            fig.add_annotation(
                x=i * 1.35 + 1.22,
                y=0.5,
                text="→",
                showarrow=False,
                font={"size": 18, "color": LEAF},
            )
    fig.update_layout(
        height=120,
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        xaxis={"visible": False, "range": [-0.1, 8.2]},
        yaxis={"visible": False, "range": [-0.2, 1.2]},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig
