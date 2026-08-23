"""Minimal research-only Streamlit surface for signal performance evidence."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.model_performance import model_performance_scorecard
from src.signal_repository import signal_repository_from_env


def render_model_lab() -> None:
    st.title("Model Lab")
    st.caption("Inspect historical analytical signals and observed forward outcomes. Signals are research observations, not recommendations or trade instructions.")
    try:
        repository = signal_repository_from_env()
        all_signals = repository.list_signals()
    except Exception as error:
        st.error("Model Lab is unavailable: " + str(error))
        return
    if not all_signals:
        st.info("No signals have been recorded yet. Future Technical Analysis Model scans will add versioned signals here.")
        return
    identities = sorted({(signal.model_id, signal.model_version) for signal in all_signals})
    selected = st.selectbox("Model and version", identities, format_func=lambda value: f"{value[0]} · {value[1]}")
    signals = tuple(signal for signal in all_signals if (signal.model_id, signal.model_version) == selected)
    outcomes = repository.list_outcomes(signal_ids=[signal.signal_id for signal in signals])
    scorecard = model_performance_scorecard(signals, outcomes, model_id=selected[0], model_version=selected[1])
    with st.container(horizontal=True):
        st.metric("Signals", scorecard["signal_count"], border=True)
        for direction, count in scorecard["direction_counts"].items():
            st.metric(direction.capitalize(), count, border=True)
    if scorecard["horizons"]:
        rows = [{"Horizon (trading days)": horizon, **metrics} for horizon, metrics in scorecard["horizons"].items()]
        st.subheader("Forward outcome statistics")
        st.dataframe(pd.DataFrame(rows), hide_index=True, column_config={"coverage": st.column_config.NumberColumn("Coverage", format="percent"), "directional_hit_rate": st.column_config.NumberColumn("Directional hit rate", format="percent"), "average_forward_return": st.column_config.NumberColumn("Average return", format="percent"), "median_forward_return": st.column_config.NumberColumn("Median return", format="percent")})
    else:
        st.info("Signals exist, but no forward outcomes have been evaluated yet.")
    st.subheader("Signal ledger")
    st.dataframe(pd.DataFrame([{"As of": signal.as_of, "Security": signal.ticker, "Direction": signal.direction.value, "Conviction": signal.conviction, "Reasoning": signal.reasoning, "Signal ID": signal.signal_id} for signal in signals]), hide_index=True)
    st.caption(scorecard["disclaimer"])
