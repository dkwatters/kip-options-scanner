"""Minimal research-only Streamlit surface for typed signal evidence."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.model_performance import model_performance_scorecard, volatility_performance_scorecard
from src.signal_repository import signal_repository_from_env
from src.signals import SignalDirection, SignalFamily


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
        st.info("No signals have been recorded yet. Signals will appear here after supported analytical models generate and persist research observations.")
        return

    families = sorted({signal.signal_family for signal in all_signals}, key=lambda value: value.value)
    family = st.selectbox("Signal family", families, format_func=lambda value: value.value.capitalize())
    family_signals = tuple(signal for signal in all_signals if signal.signal_family is family)
    identities = sorted({(signal.model_id, signal.model_version) for signal in family_signals})
    selected = st.selectbox("Model and version", identities, format_func=lambda value: f"{value[0]} · {value[1]}")
    signals = tuple(signal for signal in family_signals if (signal.model_id, signal.model_version) == selected)
    outcomes = repository.list_outcomes(signal_ids=[signal.signal_id for signal in signals])

    scorecard = None
    if family is SignalFamily.DIRECTIONAL:
        scorecard = model_performance_scorecard(signals, outcomes, model_id=selected[0], model_version=selected[1])
        with st.container(horizontal=True):
            st.metric("Signals", scorecard["signal_count"], border=True)
            for direction, count in scorecard["direction_counts"].items():
                st.metric(direction.capitalize(), count, border=True)
    else:
        scorecard = volatility_performance_scorecard(signals, outcomes)
        with st.container(horizontal=True):
            st.metric("Volatility Signals", len(signals), border=True)
            if selected[0] != "volatility-family-smoke":
                for regime, count in sorted(scorecard["regime_counts"].items()):
                    st.metric(regime.capitalize(), count, border=True)
        st.caption("Trend distribution: " + ", ".join(f"{name} {count}" for name, count in sorted(scorecard["trend_counts"].items())))
        if selected[0] == "volatility-family-smoke":
            st.info("No volatility outcome metrics are implemented for this architecture-validation smoke model.")

    if scorecard is not None and scorecard["horizons"] and family is SignalFamily.DIRECTIONAL:
        rows = [{"Horizon (trading days)": horizon, **metrics} for horizon, metrics in scorecard["horizons"].items()]
        st.subheader("Forward outcome statistics")
        st.dataframe(pd.DataFrame(rows), hide_index=True, column_config={"coverage": st.column_config.NumberColumn("Coverage", format="percent"), "directional_hit_rate": st.column_config.NumberColumn("Directional hit rate", format="percent"), "average_forward_return": st.column_config.NumberColumn("Average return", format="percent"), "median_forward_return": st.column_config.NumberColumn("Median return", format="percent")})
        if outcomes:
            st.subheader("Outcome ledger")
            st.dataframe(
                pd.DataFrame([{
                    "Signal ID": outcome.signal_id,
                    "Outcome family": outcome.outcome_family.value,
                    "Horizon": outcome.horizon_trading_days,
                    "Status": outcome.status.value,
                    "Start date": outcome.start_date,
                    "End date": outcome.end_date,
                    "Start price": outcome.start_price,
                    "End price": outcome.end_price,
                    "Forward return": outcome.absolute_return,
                    "Directional correctness": outcome.directional_correct,
                    "Components": dict(outcome.components),
                    "Error": outcome.error,
                } for outcome in outcomes]),
                hide_index=True,
                column_config={"Forward return": st.column_config.NumberColumn(format="percent")},
            )
    elif family is SignalFamily.DIRECTIONAL:
        st.info("Signals exist, but no forward outcomes have been evaluated yet.")
    elif scorecard["horizons"]:
        st.subheader("Subsequent realized volatility")
        st.dataframe(pd.DataFrame([{"Horizon (trading days)": horizon, **metrics} for horizon, metrics in scorecard["horizons"].items()]), hide_index=True,
                     column_config={"coverage": st.column_config.NumberColumn("Outcome coverage", format="percent"), "average_realized_volatility": st.column_config.NumberColumn("Average realized volatility", format="percent"), "median_realized_volatility": st.column_config.NumberColumn("Median realized volatility", format="percent")})
        if scorecard["by_regime"]:
            st.subheader("Subsequent volatility by starting regime")
            st.dataframe(pd.DataFrame([{"Horizon and regime": label, **metrics} for label, metrics in scorecard["by_regime"].items()]), hide_index=True)

    st.subheader("Signal ledger")
    st.dataframe(pd.DataFrame([{
        "As of": signal.as_of,
        "Security": signal.ticker,
        "Signal family": signal.signal_family.value,
        "Direction": "N/A" if signal.direction is SignalDirection.NOT_APPLICABLE else signal.direction.value,
        "Conviction": signal.conviction,
        "Regime": signal.metadata.get("regime"),
        "Volatility trend": signal.metadata.get("volatility_trend"),
        "Volatility percentile": signal.components.get("volatility_percentile"),
        "Realized volatility 10d": signal.components.get("realized_volatility_10d"),
        "Realized volatility 20d": signal.components.get("realized_volatility_20d"),
        "ATR % (14d)": signal.components.get("atr_pct_14d"),
        "Bollinger bandwidth (20d)": signal.components.get("bollinger_bandwidth_20d"),
        "Data quality": signal.metadata.get("data_quality"),
        "Reasoning": signal.reasoning,
        "Signal ID": signal.signal_id,
    } for signal in signals]), hide_index=True)
    if family is SignalFamily.VOLATILITY:
        with st.expander("Raw volatility diagnostics"):
            st.json([{"signal_id": signal.signal_id, "components": dict(signal.components), "metadata": dict(signal.metadata)} for signal in signals])
    st.caption(scorecard["disclaimer"] if scorecard is not None else "Descriptive research evidence only; not investment advice.")
