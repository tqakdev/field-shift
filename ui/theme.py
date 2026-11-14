"""Field Shift design system — NASA-inspired mission UI."""

from __future__ import annotations

import streamlit as st

# NASA brand-adjacent tokens (official blue / worm-era red, mission neutrals)
NASA_BLUE = "#0B3D91"
NASA_BLUE_MID = "#1A4FA0"
NASA_RED = "#E03C31"
INK = "#0B1220"
MUTED = "#5B6577"
PAPER = "#FFFFFF"
PANEL = "#EEF2F7"
HAIRLINE = "#D5DCE6"
EARTH = "#1B7A4E"  # vegetation / soil health (data, not brand)
SKY = "#2F6FED"  # rain / water series
SOIL = "#8B6914"
ALERT = NASA_RED
WHEAT = "#C4A035"
LEAF = EARTH  # alias used by charts/components
WHEAT_BG = PANEL

SCORE_COLORS = {
    "water": SKY,
    "soil_health": EARTH,
    "erosion": SOIL,
    "pest_break": "#0B3D91",
    "climate_fit": "#3D7EA6",
    "income": "#6B5B3E",
}

_THEME_VERSION = "nasa-v5"


def inject_theme() -> None:
    """Inject global CSS on every run (Streamlit clears custom HTML on rerun)."""
    st.session_state["_fs_theme_ver"] = _THEME_VERSION
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, button, input, label {{
  font-family: "IBM Plex Sans", "Helvetica Neue", Helvetica, Arial, sans-serif !important;
}}

/* Hide Streamlit chrome noise */
#MainMenu {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}
footer {{ visibility: hidden; }}
div[data-testid="stDecoration"] {{ display: none; }}
.stDeployButton, [data-testid="stToolbar"], [data-testid="stAppDeployButton"] {{
  display: none !important;
}}

.block-container {{
  max-width: 1080px;
  padding-top: 1.1rem;
  padding-bottom: 3.5rem;
}}

/* Sidebar — mission strip */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] {{
  background-color: {NASA_BLUE} !important;
  background-image: none !important;
  border-right: none !important;
}}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] a {{
  color: #F4F7FB !important;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {{
  border-radius: 4px;
  margin: 0.15rem 0.4rem;
  padding: 0.5rem 0.7rem !important;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"],
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {{
  background: rgba(255,255,255,0.14) !important;
}}

h1, .fs-title {{
  font-size: 2.35rem !important;
  font-weight: 700 !important;
  color: {INK} !important;
  letter-spacing: -0.03em;
  line-height: 1.12 !important;
  margin-bottom: 0.35rem !important;
}}
h2, .fs-section-title {{
  font-size: 1.35rem !important;
  font-weight: 600 !important;
  color: {INK} !important;
  letter-spacing: -0.01em;
}}
h3 {{
  font-size: 1.05rem !important;
  font-weight: 600 !important;
  color: {INK} !important;
}}
p, .stMarkdown p {{
  font-size: 1.02rem;
  line-height: 1.5;
  color: {INK};
}}
[data-testid="stCaptionContainer"], .fs-caption {{
  font-size: 0.82rem !important;
  color: {MUTED} !important;
  font-family: "IBM Plex Sans", sans-serif !important;
}}

/* Hero — NASA meatball bar + mission copy */
.fs-hero {{
  position: relative;
  background: linear-gradient(180deg, #F7F9FC 0%, {PAPER} 100%);
  border: 1px solid {HAIRLINE};
  border-radius: 4px;
  padding: 1.65rem 1.75rem 1.4rem 1.75rem;
  margin-bottom: 1.75rem;
  overflow: hidden;
}}
.fs-hero::before {{
  content: "";
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 5px;
  background: linear-gradient(180deg, {NASA_BLUE} 0%, {NASA_RED} 100%);
}}
.fs-eyebrow {{
  font-family: "IBM Plex Mono", monospace;
  font-size: 0.72rem;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: {NASA_BLUE};
  margin: 0 0 0.55rem 0;
}}
.fs-hero-promise {{
  font-size: 1.12rem;
  margin: 0.55rem 0 0.4rem 0;
  max-width: 40rem;
  color: {INK};
  font-weight: 500;
}}
.fs-hero-sub {{
  color: {MUTED};
  font-size: 0.92rem;
  margin: 0;
}}
.fs-mode-pill {{
  display: inline-block;
  margin-top: 0.9rem;
  padding: 0.28rem 0.75rem;
  border-radius: 2px;
  background: {NASA_BLUE};
  color: white !important;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-family: "IBM Plex Mono", monospace;
}}
.fs-mode-pill.demo {{
  background: {MUTED};
}}

.fs-section {{
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin: 2rem 0 0.45rem 0;
  padding-bottom: 0.45rem;
  border-bottom: 1px solid {HAIRLINE};
}}
.fs-section-sub {{
  color: {MUTED};
  font-size: 0.92rem;
  margin: 0 0 1rem 0;
}}
.fs-step {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.55rem;
  height: 1.55rem;
  margin-right: 0.25rem;
  padding: 0 0.35rem;
  border-radius: 2px;
  background: {NASA_BLUE};
  color: white !important;
  font-size: 0.78rem;
  font-weight: 700;
  font-family: "IBM Plex Mono", monospace;
}}

.fs-chip {{
  background: {PANEL};
  border: 1px solid {HAIRLINE};
  border-top: 3px solid {NASA_BLUE};
  border-radius: 2px;
  padding: 0.85rem 0.95rem;
  min-height: 5.2rem;
}}
.fs-chip-label {{
  font-size: 0.72rem;
  color: {MUTED};
  margin: 0 0 0.35rem 0;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-family: "IBM Plex Mono", monospace;
  font-weight: 500;
}}
.fs-chip-value {{
  font-size: 1.02rem;
  font-weight: 600;
  color: {INK};
  margin: 0;
  line-height: 1.3;
}}

.fs-banner {{
  background: {PANEL};
  border-left: 4px solid {NASA_BLUE};
  border-radius: 2px;
  padding: 1rem 1.15rem;
  margin: 0.5rem 0 1.15rem 0;
  font-size: 1.02rem;
  color: {INK};
}}
.fs-banner strong {{ color: {NASA_BLUE}; }}

.fs-card {{
  border: 1px solid {HAIRLINE};
  border-radius: 2px;
  padding: 1rem 1.05rem 0.85rem;
  background: {PAPER};
  height: 100%;
  box-shadow: 0 1px 0 rgba(11, 61, 145, 0.04);
}}
.fs-card.baseline {{
  border: 1px solid {NASA_BLUE};
  box-shadow: inset 0 0 0 1px {NASA_BLUE};
  background: #F5F8FD;
}}
.fs-card.demo-pick {{
  transition: box-shadow 0.2s ease;
}}
.fs-card.demo-pick img {{
  border-radius: 2px;
  border: 1px solid {HAIRLINE};
}}

.fs-pills {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin: 0.45rem 0 0.55rem 0;
  align-items: center;
}}
.fs-pill {{
  display: inline-block;
  background: {PANEL};
  border: 1px solid {HAIRLINE};
  border-radius: 2px;
  padding: 0.18rem 0.5rem;
  font-size: 0.75rem;
  color: {INK};
  font-family: "IBM Plex Mono", monospace;
}}
.fs-pill-arrow {{
  color: {MUTED};
  font-size: 0.75rem;
  padding: 0 0.1rem;
}}

.fs-badge {{
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.18rem 0.5rem;
  border-radius: 2px;
  border: 1px solid;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-family: "IBM Plex Mono", monospace;
}}
.fs-badge.high {{ color: {EARTH}; border-color: {EARTH}; background: #EDF7F1; }}
.fs-badge.medium {{ color: {NASA_BLUE}; border-color: {NASA_BLUE}; background: #EEF3FB; }}
.fs-badge.low {{ color: {NASA_RED}; border-color: {NASA_RED}; background: #FDF0EF; }}

div[data-testid="stMetricValue"] {{
  font-size: 1.45rem !important;
  font-weight: 700 !important;
  font-family: "IBM Plex Mono", monospace !important;
  color: {INK} !important;
}}
div[data-testid="stMetricLabel"] {{
  font-size: 0.78rem !important;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: {MUTED} !important;
}}

/* Primary buttons — white label on NASA blue (high contrast) */
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"],
button[kind="primary"],
button[data-testid="baseButton-primary"] {{
  background-color: {NASA_BLUE} !important;
  background-image: none !important;
  border: 1px solid {NASA_BLUE} !important;
  border-radius: 2px !important;
  font-weight: 600 !important;
  letter-spacing: 0.02em;
  color: #FFFFFF !important;
}}
.stButton > button[kind="primary"] *,
.stButton > button[data-testid="baseButton-primary"] *,
button[kind="primary"] *,
button[data-testid="baseButton-primary"] * {{
  color: #FFFFFF !important;
  fill: #FFFFFF !important;
}}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover,
button[kind="primary"]:hover {{
  background-color: {NASA_BLUE_MID} !important;
  color: #FFFFFF !important;
  border-color: {NASA_BLUE_MID} !important;
}}

/* Equal-height demo field cards */
.fs-demo-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin: 0.5rem 0 1.25rem 0;
}}
.fs-demo-card {{
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 100%;
  border: 1px solid {HAIRLINE};
  border-radius: 2px;
  background: {PAPER};
  overflow: hidden;
}}
.fs-demo-card img {{
  width: 100%;
  aspect-ratio: 5 / 4;
  object-fit: cover;
  display: block;
  border-bottom: 1px solid {HAIRLINE};
}}
.fs-demo-card-body {{
  display: flex;
  flex-direction: column;
  flex: 1;
  padding: 0.85rem 0.9rem 0.95rem;
  gap: 0.25rem;
}}
.fs-demo-card-title {{
  font-weight: 600;
  font-size: 1.02rem;
  color: {INK};
  margin: 0;
  line-height: 1.3;
  min-height: 2.6em;
}}
.fs-demo-card-meta {{
  color: {MUTED};
  font-size: 0.85rem;
  margin: 0;
  line-height: 1.35;
  min-height: 2.7em;
}}
.fs-demo-card-rot {{
  color: {INK};
  font-size: 0.85rem;
  margin: 0 0 0.65rem 0;
  font-family: "IBM Plex Mono", monospace;
}}
.fs-demo-card-spacer {{
  flex: 1 1 auto;
}}
.fs-demo-copy {{
  min-height: 7.2rem;
  margin: 0.35rem 0 0.15rem 0;
}}
.fs-demo-copy .fs-demo-card-title {{
  margin-bottom: 0.2rem;
}}
.fs-demo-copy .fs-demo-card-meta {{
  margin-bottom: 0.35rem;
}}

div[data-testid="stSlider"] label {{
  font-size: 0.92rem !important;
}}

@media (max-width: 400px) {{
  .block-container {{ padding-left: 0.7rem; padding-right: 0.7rem; }}
  h1, .fs-title {{ font-size: 1.65rem !important; }}
  .fs-chip-value {{ font-size: 0.95rem; }}
}}
</style>
        """,
        unsafe_allow_html=True,
    )
