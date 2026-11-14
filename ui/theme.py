"""Field Shift design system — theme CSS + shared color tokens."""

from __future__ import annotations

import streamlit as st

# Accent tokens (primary/backgrounds live in .streamlit/config.toml)
LEAF = "#3F7D3A"
SOIL = "#8B5E3C"
SKY = "#3A7CA5"
WHEAT = "#D9A441"
ALERT = "#B23A3A"
MUTED = "#6B6B6B"
PAPER = "#FBF8F2"
WHEAT_BG = "#F0EAD9"
INK = "#2B2B2B"

SCORE_COLORS = {
    "water": SKY,
    "soil_health": SOIL,
    "erosion": WHEAT,
    "pest_break": LEAF,
    "climate_fit": "#5A8F6B",
    "income": "#9A7B4F",
}


def inject_theme() -> None:
    """Inject global CSS once per session (advisory-report look)."""
    if st.session_state.get("_fs_theme_injected"):
        return
    st.session_state["_fs_theme_injected"] = True
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap');

html, body, [class*="css"] {{
  font-family: "Source Sans 3", "Source Sans Pro", sans-serif;
}}
.block-container {{
  max-width: 1100px;
  padding-top: 1.25rem;
  padding-bottom: 3rem;
}}
h1, .fs-title {{
  font-size: 2.2rem !important;
  font-weight: 700 !important;
  color: {INK} !important;
  letter-spacing: -0.02em;
  line-height: 1.15 !important;
}}
h2, .fs-section-title {{
  font-size: 1.4rem !important;
  font-weight: 700 !important;
  color: {INK} !important;
  margin-top: 0.25rem !important;
}}
h3 {{
  font-size: 1.15rem !important;
  font-weight: 600 !important;
}}
p, .stMarkdown, .stText {{
  font-size: 1.05rem;
  line-height: 1.45;
  color: {INK};
}}
.fs-caption, [data-testid="stCaptionContainer"] {{
  font-size: 0.85rem !important;
  color: {MUTED} !important;
}}
.fs-hero {{
  background: linear-gradient(135deg, {WHEAT_BG} 0%, {PAPER} 55%, #e8f0e4 100%);
  border: 1px solid #e2d8c0;
  border-radius: 12px;
  padding: 1.5rem 1.75rem;
  margin-bottom: 1.5rem;
}}
.fs-hero-promise {{
  font-size: 1.15rem;
  margin: 0.6rem 0 0.35rem 0;
  max-width: 42rem;
}}
.fs-hero-sub {{
  color: {MUTED};
  font-size: 0.95rem;
  margin: 0;
}}
.fs-mode-pill {{
  display: inline-block;
  margin-top: 0.85rem;
  padding: 0.25rem 0.7rem;
  border-radius: 999px;
  background: {LEAF};
  color: white;
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.02em;
}}
.fs-mode-pill.demo {{
  background: {SOIL};
}}
.fs-section {{
  margin: 1.75rem 0 1rem 0;
}}
.fs-section-sub {{
  color: {MUTED};
  font-size: 0.95rem;
  margin-top: -0.35rem;
  margin-bottom: 0.85rem;
}}
.fs-chip-row {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
  margin: 0.5rem 0 1rem 0;
}}
.fs-chip {{
  background: {WHEAT_BG};
  border: 1px solid #e0d5bb;
  border-radius: 10px;
  padding: 0.85rem 1rem;
}}
.fs-chip-label {{
  font-size: 0.8rem;
  color: {MUTED};
  margin: 0 0 0.25rem 0;
}}
.fs-chip-value {{
  font-size: 1.05rem;
  font-weight: 700;
  color: {INK};
  margin: 0;
}}
.fs-banner {{
  background: #e8f0e4;
  border-left: 4px solid {LEAF};
  border-radius: 8px;
  padding: 1rem 1.15rem;
  margin: 0.75rem 0 1.25rem 0;
  font-size: 1.05rem;
}}
.fs-banner strong {{ color: {LEAF}; }}
.fs-card {{
  border: 1px solid #e0d5bb;
  border-radius: 10px;
  padding: 0.9rem 1rem;
  background: #fffef9;
  height: 100%;
}}
.fs-card.baseline {{
  border: 2px solid {LEAF};
  background: #f3f7ef;
}}
.fs-card.demo-pick {{
  background: #fffef9;
}}
.fs-pills {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin: 0.4rem 0 0.6rem 0;
}}
.fs-pill {{
  display: inline-block;
  background: {WHEAT_BG};
  border: 1px solid #dccfae;
  border-radius: 999px;
  padding: 0.15rem 0.55rem;
  font-size: 0.8rem;
  color: {INK};
}}
.fs-badge {{
  display: inline-block;
  padding: 0.15rem 0.55rem;
  border-radius: 4px;
  border: 1px solid;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}}
.fs-badge.high {{ color: {LEAF}; border-color: {LEAF}; }}
.fs-badge.medium {{ color: {SOIL}; border-color: {SOIL}; }}
.fs-badge.low {{ color: {ALERT}; border-color: {ALERT}; }}
.fs-step {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.6rem;
  height: 1.6rem;
  border-radius: 999px;
  background: {LEAF};
  color: white;
  font-size: 0.85rem;
  font-weight: 700;
  margin-right: 0.45rem;
}}
div[data-testid="stMetricValue"] {{
  font-size: 1.35rem !important;
}}
@media (max-width: 400px) {{
  .block-container {{ padding-left: 0.75rem; padding-right: 0.75rem; }}
  h1, .fs-title {{ font-size: 1.7rem !important; }}
}}
</style>
        """,
        unsafe_allow_html=True,
    )
