"""User-facing renderer for one exact Research Universe analysis run."""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from src.navigation import request_navigation
from src.research_repository import research_repository_from_env
from src.universe_analysis import (
    PRESENTATION_EXTENSION_THRESHOLDS,
    analysis_explanation,
    analysis_summary,
    filter_analysis_rows,
    ranked_analysis_rows,
)


def _count_rows(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for row in rows:
        label = str(row.get(field) or "Unavailable")
        counts[label] = counts.get(label, 0) + 1
    return [{"State": label, "Count": count} for label, count in sorted(counts.items())]


def _percent(value: Any) -> str:
    try:
        return f"{float(value):+.1%}"
    except (TypeError, ValueError):
        return "Unavailable"


def _decimal(value: Any, *, prefix: str = "", places: int = 2) -> str:
    try:
        return f"{prefix}{float(value):,.{places}f}"
    except (TypeError, ValueError):
        return "Unavailable"


def _moving_average_interpretation(value: Any, period: int) -> str:
    try:
        distance = float(value)
    except (TypeError, ValueError):
        return "Relationship unavailable"
    horizon = {20: "short-term", 50: "intermediate", 200: "long-term"}[period]
    elevated = {20: 0.08, 50: 0.15, 200: 0.30}[period]
    moderate = {20: 0.04, 50: 0.08, 200: 0.15}[period]
    if distance < 0:
        return f"Below {horizon} trend"
    if distance >= elevated:
        return f"Above {horizon} trend; elevated extension caution"
    if distance >= moderate:
        return f"Above {horizon} trend; moderately extended"
    return f"Near or above {horizon} trend"


def core_factor_rows(row: dict[str, Any]) -> list[dict[str, str]]:
    """Investor-facing formatting only; stored observations remain untouched."""
    sma_labels = {20: "20-day SMA", 50: "50-day SMA", 200: "200-day SMA"}
    states = {
        "trend": row.get("trend_label") or "Unavailable",
        "momentum": row.get("momentum_label") or "Unavailable",
        "extension": row.get("extension_label") or "Unavailable",
        "volatility": row.get("volatility_label") or "Unavailable",
    }
    macd = str(row.get("macd_state") or "unavailable").casefold()
    rsi_regime = str(row.get("rsi_regime") or "unavailable").replace("_", " ")
    rows = [{
        "Group": "Trend & Position", "Factor": "Price",
        "Value": _decimal(row.get("price"), prefix="$"), "Interpretation": "Current observed price",
    }]
    for period in (20, 50, 200):
        distance = row.get(f"price_vs_sma_{period}")
        rows.extend(({
            "Group": "Trend & Position", "Factor": f"Price vs. {sma_labels[period]}",
            "Value": _percent(distance),
            "Interpretation": _moving_average_interpretation(distance, period),
        }, {
            "Group": "Trend & Position", "Factor": sma_labels[period],
            "Value": _decimal(row.get(f"sma_{period}"), prefix="$"),
            "Interpretation": "Moving-average level",
        }))
    rows.extend((
        {"Group": "Trend & Position", "Factor": "Trend", "Value": str(states["trend"]), "Interpretation": str(states["trend"])},
        {"Group": "Momentum", "Factor": "RSI", "Value": _decimal(row.get("rsi_14")), "Interpretation": f"{rsi_regime.capitalize()} RSI"},
        {"Group": "Momentum", "Factor": "MACD histogram", "Value": _decimal(row.get("macd_histogram")), "Interpretation": f"{macd.capitalize()} MACD"},
        {"Group": "Momentum", "Factor": "Momentum", "Value": str(states["momentum"]), "Interpretation": f"{states['momentum']} momentum"},
        {"Group": "Risk / Positioning", "Factor": "Extension", "Value": str(states["extension"]), "Interpretation": f"{states['extension']} — consider entry positioning"},
        {"Group": "Risk / Positioning", "Factor": "Volatility", "Value": str(states["volatility"]), "Interpretation": f"{states['volatility']} price variability"},
        {"Group": "Technical Data", "Factor": "Technical Profile Score", "Value": _decimal(row.get("technical_profile_score"), places=1), "Interpretation": "Experimental descriptive score"},
    ))
    return rows


def _semantic_color(value: Any) -> str:
    label = str(value or "").casefold()
    if "elevated" in label or "mixed" in label or "neutral" in label:
        return "color: #9a6700"
    if any(token in label for token in ("bullish", "positive", "constructive")):
        return "color: #137333"
    if any(token in label for token in ("bearish", "negative", "deteriorating", "below")):
        return "color: #b3261e"
    return ""


def _reset_filters() -> None:
    for key in ("tam_ticker_search", "tam_profiles", "tam_trend_states", "tam_momentum_states", "tam_volatility_states"):
        st.session_state.pop(key, None)


def render_universe_analysis() -> None:
    handoff = st.session_state.get("active_universe_analysis_handoff")
    run = st.session_state.get("active_universe_analysis_run")
    if st.button("Back to Research Universe", icon=":material/arrow_back:"):
        request_navigation("Research Universe")
    if handoff is None or run is None:
        st.title("Universe Analysis")
        st.error(
            "No exact Research Universe analysis run is selected. Return to the Research "
            "Universe and choose Analyze Universe; historical scans are not substituted."
        )
        return
    if run.universe_id != handoff.universe_id or run.universe_version != handoff.universe_version:
        st.title("Universe Analysis")
        st.error("The selected run does not match the active Research Universe version.")
        return

    unavailable = tuple(entry for entry in run.ledger if entry.status.value != "analyzed")
    if len(run.ledger) != run.requested_constituent_count or len(run.analyzed_tickers) + len(unavailable) != run.requested_constituent_count:
        st.title("Universe Analysis")
        st.error("The analysis ledger does not reconcile to exact Research Universe membership.")
        return

    st.title(run.universe_title)
    st.subheader("Universe Analysis")
    if run.research_question:
        st.caption("Original research question")
        st.write(f'“{run.research_question}”')
    st.caption(
        f"{run.requested_constituent_count} universe members · {len(run.analyzed_tickers)} analyzed · "
        f"{len(unavailable)} unavailable · Updated {run.timestamp}"
    )
    selection_scope = f"{run.universe_id}:v{run.universe_version}:{run.scan_id}"
    active_key = "universe_analysis_active_company"
    active = st.session_state.get(active_key)
    if not isinstance(active, dict) or active.get("scope") != selection_scope:
        active = None
        st.session_state.pop(active_key, None)
    try:
        repository = research_repository_from_env()
        observations = repository.technical_analysis_observations(
            tickers=list(run.analyzed_tickers), latest_scan_only=False, scan_id=run.scan_id,
        )
    except Exception as error:
        st.error("The exact Research Universe analysis could not be loaded: " + str(error))
        return
    raw_rows = list(observations["rows"])
    observed = [str(row.get("ticker") or "").upper() for row in raw_rows]
    if len(raw_rows) != len(run.analyzed_tickers) or set(observed) != set(run.analyzed_tickers):
        st.error(
            "Exact-universe execution is incomplete: stored observations do not reconcile to "
            "the analyzed-member ledger. Historical observations will not be substituted."
        )
        return

    names = {
        str(entry.ticker_or_identifier or "").upper(): entry.company_name
        for entry in run.ledger if entry.ticker_or_identifier
    }
    ranked = ranked_analysis_rows(raw_rows, names)
    try:
        summary = analysis_summary(ranked)
    except ValueError as error:
        st.error(str(error))
        return
    profiles = summary["profiles"]
    bullish = summary["bullish_trends"]
    with st.container(horizontal=True):
        st.metric("Companies analyzed", len(ranked), border=True)
        for label in ("Strong", "Constructive", "Mixed", "Weak"):
            st.metric(label + " profiles", profiles[label], border=True)
        st.metric("Bullish trends", bullish, border=True)
    if profiles["Strong"] + profiles["Constructive"] > len(ranked) / 2:
        st.write("Most analyzed members currently show strong or constructive technical characteristics.")
    else:
        st.write("The analyzed population currently shows a mix of technical characteristics.")
    st.caption(
        "Rankings compare current technical characteristics within this Research Universe. "
        "They are not buy/sell recommendations and do not evaluate companies outside the universe."
    )

    with st.expander("Population Details"):
        with st.container(horizontal=True):
            st.metric("Average RSI", f"{summary['average_rsi']:.1f}" if summary["average_rsi"] is not None else "Unavailable")
            st.metric("Above 200-day SMA", summary["above_200_day_sma"])
            st.metric("Bullish MACD", summary["bullish_macd"])
            st.metric("High volatility", summary["high_volatility"])

    st.subheader("Company comparison")
    st.caption("Legend: green = positive trend evidence · red = negative trend evidence · amber = mixed or extension caution. Text labels carry the meaning.")
    with st.container(horizontal=True):
        search = st.text_input("Search", key="tam_ticker_search", placeholder="Company or ticker")
        profile_filter = st.multiselect("Profile", sorted({row["technical_profile"] for row in ranked}), key="tam_profiles")
        trend_filter = st.multiselect("Trend", sorted({row["trend_label"] for row in ranked}), key="tam_trend_states")
        momentum_filter = st.multiselect("Momentum", sorted({row["momentum_label"] for row in ranked}), key="tam_momentum_states")
        volatility_filter = st.multiselect("Volatility", sorted({row["volatility_label"] for row in ranked}), key="tam_volatility_states")
    st.button("Reset filters", icon=":material/restart_alt:", on_click=_reset_filters)
    visible = filter_analysis_rows(
        ranked, search=search, profiles=profile_filter, trends=trend_filter,
        momentum=momentum_filter, volatility=volatility_filter,
    )
    st.caption(f"Showing {len(visible)} of {len(ranked)} analyzed members")
    comparison = pd.DataFrame([{
        "Rank": row["rank"], "Company": row["company_name"], "Ticker": row["ticker"],
        "Technical Profile": row["technical_profile"], "Trend": row["trend_label"],
        "Momentum": row["momentum_label"], "Extension / Positioning": row["extension_label"],
        "Volatility": row["volatility_label"], "Key signal": row["key_signal"], "Status": "Analyzed",
    } for row in visible])
    styled_comparison = comparison.style.map(
        _semantic_color,
        subset=["Technical Profile", "Trend", "Momentum", "Extension / Positioning"],
    ) if not comparison.empty else comparison
    event = st.dataframe(
        styled_comparison,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"universe_company_comparison_{selection_scope}",
    )
    selected_rows = tuple(event.selection.rows)
    if selected_rows:
        selected_index = selected_rows[-1]
        if 0 <= selected_index < len(visible):
            active = {"scope": selection_scope, "ticker": visible[selected_index]["ticker"]}
            st.session_state[active_key] = active
    else:
        st.session_state.pop(active_key, None)
        active = None
    visible_tickers = {row["ticker"] for row in visible}
    if active and active.get("ticker") not in visible_tickers:
        st.session_state.pop(active_key, None)
        active = None

    if active:
        selected = active["ticker"]
        row = next(item for item in visible if item["ticker"] == selected)
        explanation = analysis_explanation(row)
        with st.container():
            st.write(f"Rank #{row['rank']} of {len(ranked)} analyzed")
            st.metric("Current Technical Profile", row["technical_profile"])
            st.write(explanation["summary"])
            st.markdown("**Why it ranks here**")
            for item in explanation["positives"] or ("No positive factor is fully supported by the available indicators.",):
                st.write("✓ " + item)
            st.markdown("**Watch-outs**")
            for item in explanation["watchouts"] or ("No significant extension or momentum concerns are currently identified.",):
                st.write("⚠ " + item)
            st.markdown("**Core factors**")
            factor_frame = pd.DataFrame(core_factor_rows(row))
            st.dataframe(
                factor_frame.style.map(_semantic_color, subset=["Interpretation"]),
                hide_index=True,
            )
            st.caption(f"Observation timestamp: {row.get('technical_timestamp') or 'Unavailable'}")
            if st.button("View Company Analysis", key="view_company_analysis"):
                st.session_state.company_analysis_context = {
                    "ticker": selected, "company_name": row["company_name"], "row": row,
                    "parent_handoff": handoff, "parent_universe_id": run.universe_id,
                    "parent_universe_version": run.universe_version,
                    "parent_universe_title": run.universe_title,
                    "analysis_run_reference": run.scan_id,
                    "observation_timestamp": row.get("technical_timestamp"),
                    "return_destination": "Universe Analysis",
                }
                request_navigation("Company Analysis")

    if unavailable:
        st.subheader("Needs Attention")
        st.dataframe(pd.DataFrame([{
            "Company": entry.company_name,
            "Ticker or identifier": entry.ticker_or_identifier or "Unresolved",
            "Status": entry.status.value, "Reason": entry.reason,
        } for entry in unavailable]), hide_index=True)
        st.caption("These members remain part of the Research Universe and are not ranked.")

    with st.expander("Universe distribution", expanded=False, icon=":material/bar_chart:"):
        st.caption("Optional population-level diagnostics for the currently visible companies.")
        columns = st.columns(2)
        for index, (label, field) in enumerate((
            ("Technical Profile Distribution", "technical_profile"),
            ("Trend Distribution", "trend_label"),
            ("Momentum Distribution", "momentum_label"),
            ("Volatility Distribution", "volatility_label"),
        )):
            with columns[index % 2]:
                st.markdown("**" + label + "**")
                chart_rows = _count_rows(visible, field)
                if chart_rows:
                    st.bar_chart(pd.DataFrame(chart_rows).set_index("State"), y="Count")

    with st.expander("Technical Data & Diagnostics", icon=":material/database:"):
        st.caption(f"Current exact run/scan ID: {run.scan_id}")
        st.caption(
            "Extension thresholds are experimental presentation-only labels and do not change TAM scores: "
            + str(PRESENTATION_EXTENSION_THRESHOLDS)
        )
        st.dataframe(pd.DataFrame(raw_rows), hide_index=True)
        history = repository.technical_analysis_observations(latest_scan_only=False)
        historical_ids = [item for item in history["available_scan_ids"] if item != run.scan_id]
        if historical_ids:
            st.markdown("**Historical scans (compatibility only)**")
            historical_id = st.selectbox("Historical scan ID", [""] + historical_ids, key="tam_scan_id")
            if historical_id:
                historical = repository.technical_analysis_observations(latest_scan_only=False, scan_id=historical_id)
                st.caption("Historical data below does not redefine the current Research Universe analysis.")
                st.dataframe(pd.DataFrame(historical["rows"]), hide_index=True)
