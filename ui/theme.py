"""Field Shift design system — single source of truth for tokens + CSS."""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Colour tokens (docs/DESIGN.md)
# ---------------------------------------------------------------------------
BACKGROUND = "#FBF8F2"
SURFACE = "#FFFFFF"
SIDEBAR = "#F0EAD9"
TEXT = "#2B2B2B"
MUTED = "#5C5C5C"  # darkened from #6B6B6B for WCAG AA on BACKGROUND/SURFACE
PRIMARY = "#3F7D3A"
WARNING = "#B26A00"
DANGER = "#B23A3A"
INFO = "#3A7CA5"
CARD_BORDER = "#E3DDCF"
HAIRLINE = CARD_BORDER
FOCUS = "#2F5E2C"

# Spacing scale (px)
SPACE = (8, 16, 24, 32, 48)

# Okabe–Ito colour-blind-safe palette (fixed roles)
OKABE = {
    "black": "#000000",
    "orange": "#E69F00",
    "sky": "#56B4E9",
    "bluish_green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
}

# Chart / criterion colours — one fixed colour per variable app-wide
CHART_COLORS = {
    "greenness": OKABE["bluish_green"],
    "rain": OKABE["sky"],
    "water_balance": OKABE["blue"],
    "bare": OKABE["orange"],
    "stress": OKABE["vermillion"],
}
SCORE_COLORS = {
    "water": OKABE["sky"],
    "soil_health": OKABE["bluish_green"],
    "erosion": OKABE["orange"],
    "pest_break": OKABE["purple"],
    "climate_fit": OKABE["blue"],
    "income": OKABE["vermillion"],
    "total": PRIMARY,
}

# Back-compat aliases used across the codebase
PAPER = SURFACE
PANEL = SIDEBAR
INK = TEXT
NASA_BLUE = PRIMARY
NASA_BLUE_MID = FOCUS
NASA_RED = DANGER
EARTH = PRIMARY
SKY = INFO
SOIL = WARNING
ALERT = DANGER
WHEAT = WARNING
LEAF = PRIMARY
WHEAT_BG = SIDEBAR

# Text/background pairs that must meet WCAG 2.2 AA (used by tests)
CONTRAST_PAIRS: list[tuple[str, str, str, float]] = [
    # (name, fg, bg, min_ratio)
    ("text_on_background", TEXT, BACKGROUND, 4.5),
    ("text_on_surface", TEXT, SURFACE, 4.5),
    ("muted_on_background", MUTED, BACKGROUND, 4.5),
    ("muted_on_surface", MUTED, SURFACE, 4.5),
    ("primary_on_background", PRIMARY, BACKGROUND, 3.0),  # large / UI chrome
    ("primary_on_surface", PRIMARY, SURFACE, 3.0),
    ("warning_on_background", WARNING, BACKGROUND, 3.0),
    ("danger_on_background", DANGER, BACKGROUND, 3.0),
    ("info_on_background", INFO, BACKGROUND, 3.0),
    ("text_on_sidebar", TEXT, SIDEBAR, 4.5),
]

_THEME_VERSION = "design-v2"


def inject_theme() -> None:
    """Inject global CSS on every run (Streamlit clears custom HTML on rerun)."""
    st.session_state["_fs_theme_ver"] = _THEME_VERSION
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, button, input, label, textarea {{
  font-family: "Source Sans 3", "Helvetica Neue", Helvetica, Arial, sans-serif !important;
}}

#MainMenu {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}
footer {{ visibility: hidden; }}
div[data-testid="stDecoration"] {{ display: none; }}
.stDeployButton, [data-testid="stToolbar"], [data-testid="stAppDeployButton"] {{
  display: none !important;
}}

.stApp, [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"] {{
  background: {BACKGROUND} !important;
}}
.block-container,
[data-testid="stMainBlockContainer"] {{
  max-width: 1100px !important;
  padding-top: 24px;
  padding-bottom: 48px;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}}

/* Strip Streamlit page / fragment chrome — borders only on real cards */
div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stMainBlockContainer"],
section.main .block-container {{
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"] {{
  background: transparent !important;
  overflow: visible !important;
  height: auto !important;
  border-radius: 0 !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"] > div {{
  height: auto !important;
}}
/* Fragments sometimes draw a panel; keep them borderless on Field */
[data-testid="stVerticalBlockBorderWrapper"]:not(:has(.fs-strat)):not(:has(.fs-chip)) {{
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
}}

/* Sidebar */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] {{
  background-color: {SIDEBAR} !important;
  background-image: none !important;
  border-right: 1px solid {CARD_BORDER} !important;
}}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] a {{
  color: {TEXT} !important;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {{
  border-radius: 8px;
  margin: 4px 8px;
  padding: 12px 16px !important;
  min-height: 44px;
}}
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"][aria-current="page"],
section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"]:hover {{
  background: {SURFACE} !important;
  box-shadow: inset 0 0 0 1px {CARD_BORDER};
}}

/* Typography scale */
h1, .fs-title {{
  font-size: 32px !important;
  font-weight: 700 !important;
  color: {TEXT} !important;
  letter-spacing: -0.02em;
  line-height: 1.2 !important;
  margin-bottom: 8px !important;
  text-wrap: balance;
}}
h2, .fs-section-title {{
  font-size: 22px !important;
  font-weight: 600 !important;
  color: {TEXT} !important;
  letter-spacing: -0.01em;
  line-height: 1.2 !important;
  text-wrap: balance;
}}
h3 {{
  font-size: 18px !important;
  font-weight: 600 !important;
  color: {TEXT} !important;
  line-height: 1.2 !important;
}}
p, .stMarkdown p {{
  font-size: 16px;
  line-height: 1.5;
  color: {TEXT};
}}
[data-testid="stCaptionContainer"], .fs-caption {{
  font-size: 13px !important;
  line-height: 1.45 !important;
  color: {MUTED} !important;
}}
.fs-prose {{
  max-width: 640px;
}}

/* Hero — no side stripe; soft surface card */
.fs-hero {{
  background: {SURFACE};
  border: 1px solid {CARD_BORDER};
  border-radius: 8px;
  padding: 24px;
  margin-bottom: 48px;
}}
.fs-eyebrow {{
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: {PRIMARY};
  margin: 0 0 8px 0;
}}
.fs-hero-promise {{
  font-size: 16px;
  margin: 8px 0;
  max-width: 640px;
  color: {TEXT};
  font-weight: 500;
  line-height: 1.5;
}}
.fs-hero-sub {{
  color: {MUTED};
  font-size: 13px;
  margin: 0;
  max-width: 640px;
  line-height: 1.45;
}}
.fs-mode-pill {{
  display: inline-block;
  margin-top: 16px;
  padding: 8px 16px;
  border-radius: 8px;
  background: {PRIMARY};
  color: {SURFACE} !important;
  font-size: 13px;
  font-weight: 600;
  min-height: 44px;
  line-height: 28px;
}}
.fs-mode-pill.demo {{
  background: {MUTED};
}}

.fs-section {{
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 48px 0 8px 0;
  padding-bottom: 0;
  border-bottom: none;
}}
.fs-section-sub {{
  color: {MUTED};
  font-size: 16px;
  margin: 0 0 24px 0;
  max-width: 640px;
  line-height: 1.5;
}}
.fs-step {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 28px;
  padding: 0 6px;
  border-radius: 8px;
  background: {PRIMARY};
  color: {SURFACE} !important;
  font-size: 13px;
  font-weight: 700;
}}

/* Home steps */
.fs-home-steps {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin: 8px 0 32px 0;
}}
.fs-home-step {{
  background: {SURFACE};
  border: 1px solid {CARD_BORDER};
  border-radius: 8px;
  padding: 16px;
}}
.fs-home-step-num {{
  font-size: 13px;
  font-weight: 600;
  color: {PRIMARY};
  margin: 0 0 8px 0;
}}
.fs-home-step-title {{
  font-size: 16px;
  font-weight: 600;
  color: {TEXT};
  margin: 0 0 4px 0;
}}
.fs-home-step-body {{
  font-size: 13px;
  color: {MUTED};
  margin: 0;
  line-height: 1.45;
}}
@media (max-width: 700px) {{
  .fs-home-steps {{ grid-template-columns: 1fr; }}
}}

/* Fact chips */
.fs-chip-grid {{
  display: grid;
  grid-template-columns: repeat(var(--fs-chip-cols, 4), minmax(0, 1fr));
  gap: 16px;
  margin: 8px 0 32px 0;
  align-items: stretch;
}}
.fs-chip {{
  display: flex;
  flex-direction: column;
  background: {SURFACE};
  border: 1px solid {CARD_BORDER};
  border-radius: 8px;
  padding: 16px;
  min-height: 0;
  height: 100%;
  box-sizing: border-box;
  overflow: visible;
}}
.fs-chip-label {{
  font-size: 13px;
  color: {MUTED};
  margin: 0 0 8px 0;
  font-weight: 600;
}}
.fs-chip-value {{
  font-size: 26px;
  font-weight: 700;
  color: {TEXT};
  margin: 0 0 8px 0;
  line-height: 1.2;
  overflow: visible;
  font-variant-numeric: tabular-nums;
}}
.fs-chip-meaning {{
  font-size: 13px;
  color: {MUTED};
  margin: 0;
  line-height: 1.45;
  flex: 1 1 auto;
}}
.fs-chip-source {{
  margin: 16px 0 0 0;
  padding-top: 8px;
  border-top: 1px solid {CARD_BORDER};
  font-size: 13px;
  line-height: 1.35;
  color: {MUTED};
}}
@media (max-width: 700px) {{
  .fs-chip-grid {{ grid-template-columns: 1fr; }}
}}

/* Strategy cards */
.fs-strat {{
  margin: 0;
  padding-top: 0;
  overflow: visible;
}}
.fs-strat::before {{
  content: "";
  display: block;
  width: 32px;
  height: 3px;
  border-radius: 2px;
  background: {MUTED};
  margin: 0 0 12px 0;
}}
.fs-tier-best::before {{ background: {PRIMARY}; }}
.fs-tier-worth::before {{ background: {WARNING}; }}
.fs-tier-base::before {{ background: {INFO}; }}
.fs-tier-bad::before {{ background: {DANGER}; }}
.fs-strat-role {{
  font-size: 13px;
  font-weight: 600;
  color: {MUTED};
  margin: 0 0 8px 0;
  min-height: 20px;
}}
.fs-tier-best .fs-strat-role {{ color: {PRIMARY}; }}
.fs-tier-worth .fs-strat-role {{ color: {WARNING}; }}
.fs-tier-base .fs-strat-role {{ color: {INFO}; }}
.fs-tier-bad .fs-strat-role {{ color: {DANGER}; }}
.fs-strat-title {{
  font-size: 18px;
  font-weight: 700;
  color: {TEXT};
  margin: 0;
  line-height: 1.25;
  min-height: 2.5em;
  overflow: visible;
}}
.fs-tier-reason {{
  font-size: 13px;
  color: {MUTED};
  margin: 8px 0 0;
  line-height: 1.45;
  min-height: 2.9em;
}}
.fs-strat-flags {{
  min-height: 24px;
  margin: 8px 0;
  font-size: 13px;
  color: {MUTED};
  line-height: 1.35;
}}
.fs-strat-flags .bad {{ color: {DANGER}; }}
.fs-strat-summary {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin: 16px 0;
  padding: 16px;
  box-sizing: border-box;
  background: {BACKGROUND};
  border: 1px solid {CARD_BORDER};
  border-radius: 8px;
  overflow: visible;
}}
.fs-strat-score {{
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}}
.fs-strat-score-num {{
  font-size: 26px;
  font-weight: 700;
  color: {TEXT};
  line-height: 1.2;
  overflow: visible;
  font-variant-numeric: tabular-nums;
}}
.fs-strat-score-label {{
  font-size: 13px;
  color: {MUTED};
  font-weight: 500;
}}
.fs-strat-meta {{
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}}
.fs-card-delta {{
  font-size: 13px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 8px;
  white-space: nowrap;
}}
.fs-card-delta.up {{ color: {PRIMARY}; background: #E8F2E7; }}
.fs-card-delta.down {{ color: {DANGER}; background: #F8EAEA; }}
.fs-card-delta.flat {{ color: {MUTED}; background: {SIDEBAR}; }}
.fs-card-note {{
  font-size: 13px;
  color: {MUTED};
  margin: 0 0 8px 0;
}}
.fs-card-spacer {{
  flex: 1 1 auto;
  min-height: 8px;
  height: 8px;
}}

/* Equal-height strategy card rows only */
div[data-testid="stHorizontalBlock"] {{
  align-items: flex-start !important;
  gap: 16px !important;
}}
div[data-testid="stHorizontalBlock"]:has(.fs-strat) {{
  align-items: stretch !important;
}}
div[data-testid="stHorizontalBlock"]:has(.fs-strat) > div[data-testid="stColumn"] {{
  display: flex !important;
  flex-direction: column;
}}
div[data-testid="stHorizontalBlock"]:has(.fs-strat) > div[data-testid="stColumn"] > div {{
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.fs-strat) {{
  height: 100%;
  display: flex !important;
  flex-direction: column;
  border: 1px solid {CARD_BORDER} !important;
  border-radius: 8px !important;
  background: {SURFACE} !important;
  box-shadow: none !important;
  overflow: visible !important;
  padding: 4px;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.fs-strat) > div {{
  height: 100%;
  display: flex !important;
  flex-direction: column;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.fs-strat)
[data-testid="element-container"] {{
  flex: 0 0 auto !important;
  height: auto !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.fs-strat)
[data-testid="element-container"]:has(.fs-card-spacer) {{
  flex: 1 1 auto !important;
}}

.fs-sc-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin: 0;
}}
.fs-sc {{
  min-width: 0;
  cursor: help;
  min-height: 56px;
  overflow: visible;
}}
.fs-sc-top {{
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}}
.fs-sc-name {{
  font-size: 13px;
  font-weight: 600;
  color: {TEXT};
}}
.fs-sc-val {{
  font-size: 13px;
  font-weight: 600;
  color: {MUTED};
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}}
.fs-sc-track {{
  height: 8px;
  background: {SIDEBAR};
  border: 1px solid {CARD_BORDER};
  border-radius: 4px;
  overflow: hidden;
}}
.fs-sc-fill {{
  height: 100%;
  border-radius: 3px;
  min-width: 2px;
}}
.fs-sc-band {{
  display: block;
  margin-top: 4px;
  font-size: 13px;
  font-weight: 600;
  color: {MUTED};
  min-height: 18px;
}}
.fs-band-strong {{ color: {PRIMARY}; }}
.fs-band-good {{ color: {INFO}; }}
.fs-band-fair {{ color: {WARNING}; }}
.fs-band-needs-attention {{ color: {DANGER}; }}
@media (max-width: 700px) {{
  .fs-sc-grid {{ grid-template-columns: 1fr; }}
}}

.fs-banner {{
  background: {SURFACE};
  border: 1px solid {CARD_BORDER};
  border-radius: 8px;
  padding: 16px 24px;
  margin: 8px 0 24px 0;
  font-size: 16px;
  color: {TEXT};
  box-shadow: inset 0 3px 0 0 {PRIMARY};
  max-width: 100%;
}}
.fs-banner strong {{ color: {PRIMARY}; }}

.fs-pills {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
  align-items: center;
  min-height: 40px;
}}
.fs-pill {{
  display: inline-block;
  background: {SIDEBAR};
  border: 1px solid {CARD_BORDER};
  border-radius: 8px;
  padding: 4px 12px;
  font-size: 13px;
  color: {TEXT};
  line-height: 1.4;
}}
.fs-pill-arrow {{
  color: {MUTED};
  font-size: 13px;
}}

.fs-badge {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 8px;
  border: 1px solid;
  font-size: 13px;
  font-weight: 600;
}}
.fs-badge.high {{ color: {PRIMARY}; border-color: {PRIMARY}; background: #E8F2E7; }}
.fs-badge.medium {{ color: {INFO}; border-color: {INFO}; background: #E8F1F6; }}
.fs-badge.low {{ color: {DANGER}; border-color: {DANGER}; background: #F8EAEA; }}

/* Sliders — prevent value label clipping */
div[data-testid="stSlider"] {{
  padding-left: 8px;
  padding-right: 8px;
  overflow: visible !important;
}}
div[data-testid="stSlider"] [data-baseweb="slider"] {{
  overflow: visible !important;
}}
div[data-testid="stSlider"] label {{
  font-size: 16px !important;
}}

div[data-testid="stMetricValue"] {{
  font-size: 26px !important;
  font-weight: 700 !important;
  color: {TEXT} !important;
  line-height: 1.2 !important;
  overflow: visible !important;
}}
div[data-testid="stMetricLabel"] {{
  font-size: 13px !important;
  color: {MUTED} !important;
}}

.stButton > button {{
  border-radius: 8px !important;
  min-height: 44px !important;
  font-weight: 600 !important;
  transition: background-color 0.15s ease, border-color 0.15s ease !important;
}}
.stButton > button[kind="primary"],
button[kind="primary"] {{
  background-color: {PRIMARY} !important;
  border: 1px solid {PRIMARY} !important;
  color: {SURFACE} !important;
}}
.stButton > button[kind="primary"] *,
button[kind="primary"] * {{
  color: {SURFACE} !important;
}}
.stButton > button[kind="primary"]:hover,
button[kind="primary"]:hover {{
  background-color: {FOCUS} !important;
  border-color: {FOCUS} !important;
}}
.stButton > button:focus-visible,
input:focus-visible,
[data-baseweb="select"] *:focus-visible {{
  outline: 3px solid {FOCUS} !important;
  outline-offset: 2px !important;
}}

[data-testid="stExpander"] details {{
  border: 1px solid {CARD_BORDER} !important;
  border-radius: 8px !important;
  background: {SURFACE} !important;
}}
[data-testid="stExpander"] summary {{
  padding: 12px 16px !important;
  font-size: 16px !important;
  min-height: 44px;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.fs-strat)
[data-testid="stExpander"] details {{
  background: transparent !important;
  border: none !important;
  border-top: 1px solid {CARD_BORDER} !important;
  border-radius: 0 !important;
}}

div[data-testid="stDataFrame"] {{
  border: 1px solid {CARD_BORDER};
  border-radius: 8px;
  overflow: hidden;
}}

[data-testid="stImage"] img {{
  border-radius: 8px;
  border: 1px solid {CARD_BORDER};
}}
div[data-testid="stHorizontalBlock"] [data-testid="stImage"] img {{
  max-height: 320px;
  width: 100%;
  object-fit: contain;
  background: {SIDEBAR};
}}
.fs-demo-thumb-empty {{
  aspect-ratio: 5 / 4;
  background: {SIDEBAR};
  border: 1px solid {CARD_BORDER};
  border-radius: 8px;
}}
.fs-demo-copy {{
  min-height: 120px;
  margin: 8px 0;
}}
.fs-demo-card-title {{
  font-weight: 600;
  font-size: 16px;
  color: {TEXT};
  margin: 0 0 4px 0;
  line-height: 1.3;
  min-height: 2.6em;
}}
.fs-demo-card-meta {{
  color: {MUTED};
  font-size: 13px;
  margin: 0 0 8px 0;
  line-height: 1.35;
  min-height: 2.7em;
}}
.fs-demo-card-rot {{
  color: {TEXT};
  font-size: 13px;
  margin: 0;
}}

.fs-glossary {{
  display: grid;
  gap: 8px;
  margin: 8px 0 32px 0;
}}
.fs-glossary-row {{
  display: grid;
  grid-template-columns: minmax(7rem, 11rem) 1fr;
  gap: 16px;
  padding: 16px;
  background: {SURFACE};
  border: 1px solid {CARD_BORDER};
  border-radius: 8px;
}}
.fs-glossary-term {{
  font-size: 13px;
  font-weight: 700;
  color: {PRIMARY};
}}
.fs-glossary-def {{
  font-size: 16px;
  color: {TEXT};
  line-height: 1.5;
  margin: 0;
  max-width: 640px;
}}
@media (max-width: 700px) {{
  .fs-glossary-row {{ grid-template-columns: 1fr; gap: 4px; }}
}}

.fs-chart-takeaway {{
  font-size: 16px;
  color: {TEXT};
  margin: 0 0 16px 0;
  max-width: 640px;
  line-height: 1.5;
  font-weight: 500;
}}

@media (max-width: 400px) {{
  .block-container {{ padding-left: 16px; padding-right: 16px; }}
  h1, .fs-title {{ font-size: 28px !important; }}
  .fs-chip-value, .fs-strat-score-num {{ font-size: 22px; }}
}}
</style>
        """,
        unsafe_allow_html=True,
    )
