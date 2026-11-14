"""Strategy card rendering — NASA mission-report layout."""

from __future__ import annotations

import streamlit as st
from fieldshift.models import StrategyCard

from ui.charts import scores_bar
from ui.components import confidence_badge, season_pills
from ui.source_caption import source_caption


def render_strategy_cards(
    cards: list[StrategyCard],
    *,
    show_climate_delta: bool = False,
) -> None:
    """Render 3–4 strategy cards side by side (stack on narrow layouts)."""
    if not cards:
        st.info("No strategies available.")
        return

    cols = st.columns(len(cards), gap="medium")
    for col, card in zip(cols, cards, strict=True):
        is_baseline = card.id == "current"
        with col:
            with st.container(border=True):
                if is_baseline:
                    st.caption("YOUR ROTATION TODAY")
                st.markdown(f"**{card.name}**")
                season_pills(card.sequence)
                confidence_badge(card.confidence)

                delta = card.delta_vs_current.get("total")
                st.metric(
                    "Total score",
                    f"{card.scores.total:.2f}",
                    delta=(f"{delta:+.2f} vs current" if delta is not None else None),
                )
                if show_climate_delta and delta is not None:
                    st.caption(f"Change vs today’s climate: {delta:+.2f}")
                source_caption("Field Shift scoring engine")

                st.plotly_chart(
                    scores_bar(card.scores),
                    use_container_width=True,
                    key=f"scores-{card.id}-{hash(card.name) % 10_000}",
                    config={"displayModeBar": False},
                )

                with st.expander("Why"):
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
                with st.expander("Risks to check locally"):
                    for r in card.risks_for_local_review:
                        st.write(f"• {r}")
