"""Strategy card rendering for Streamlit (columns + metrics + expanders)."""

from __future__ import annotations

import streamlit as st
from fieldshift.models import StrategyCard

from ui.charts import scores_bar
from ui.source_caption import source_caption

_CONF_COLORS = {
    "high": "#3f4a28",
    "medium": "#92400e",
    "low": "#6e4b2e",
}


def _confidence_badge(level: str) -> None:
    color = _CONF_COLORS.get(level, "#6e4b2e")
    st.markdown(
        f'<span style="display:inline-block;padding:0.15rem 0.55rem;border-radius:4px;'
        f"border:1px solid {color};color:{color};font-size:0.75rem;font-weight:600;"
        f'text-transform:uppercase;letter-spacing:0.04em;">{level} confidence</span>',
        unsafe_allow_html=True,
    )


def render_strategy_cards(cards: list[StrategyCard]) -> None:
    """Render 3–4 strategy cards side by side (stacked on narrow layouts)."""
    if not cards:
        st.info("No strategies available.")
        return

    cols = st.columns(len(cards))
    for col, card in zip(cols, cards, strict=True):
        is_baseline = card.id == "current"

        with col:
            border = "2px solid #6b7c3c" if is_baseline else "1px solid #d6c8a8"
            st.markdown(
                f'<div style="border:{border};padding:0.75rem;border-radius:6px;'
                f'background:{"#ebe4d4" if is_baseline else "#fffef9"};">',
                unsafe_allow_html=True,
            )
            if is_baseline:
                st.caption("BASELINE — current rotation")
            st.subheader(card.name)
            _confidence_badge(card.confidence)

            delta = card.delta_vs_current.get("total")
            st.metric(
                "Total score",
                f"{card.scores.total:.2f}",
                delta=(f"{delta:+.2f} vs current" if delta is not None else None),
            )
            source_caption("Field Shift scoring engine")

            st.plotly_chart(
                scores_bar(card.scores),
                use_container_width=True,
                key=f"scores-{card.id}",
            )
            source_caption("criterion scores (0–1)")

            st.write(card.why)

            with st.expander("Evidence"):
                for item in card.evidence:
                    st.write(f"• {item.text}")
                    source_caption(item.source, getattr(item, "data_through", None))
            with st.expander("Benefits"):
                for b in card.benefits:
                    st.write(f"• {b}")
            with st.expander("Data gaps"):
                for g in card.data_gaps:
                    st.write(f"• {g}")
            with st.expander("Risks for local review"):
                for r in card.risks_for_local_review:
                    st.write(f"• {r}")

            st.markdown("</div>", unsafe_allow_html=True)
