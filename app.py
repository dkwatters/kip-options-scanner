import json
import os
from datetime import date, datetime, timezone
from hmac import compare_digest
from math import isfinite
from numbers import Number
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.contract_detail import (
    contract_detail_fields,
    contract_interpretation,
    contract_rule_explanations,
)
from src.contract_quality import (
    ANY_SINGLE_FAILED_TEST,
    CALL_DELTA_RANGE,
    MAX_SPREAD_PERCENT,
    MIN_OPEN_INTEREST,
    MIN_VOLUME,
    OPTION_TYPE_FILTERS,
    RULE_MARGIN_COLUMNS,
    TEST_SPECIFIC_NEAR_MISS_OPTIONS,
    calculate_mid_price,
    contract_quality,
    contract_quality_summary,
    filter_by_option_type,
    near_miss_contracts,
    opportunity_analysis,
    passing_contracts,
    test_specific_near_misses,
    ticker_diagnostics,
)
from src.contract_scoring import QUALITY_WEIGHTS
from src.evaluation_profile import (
    DEFAULT_EVALUATION_PROFILE,
    evaluation_profile_export_fields,
)
from src.opportunity_ranking import (
    NO_CANDIDATE,
    NO_MATCHING_CONTRACTS,
    no_matching_contracts_row,
    opportunity_table_rows,
    primary_contract_strength,
    primary_contract_weakness,
)
from src.quality_diagnostics import (
    DEFAULT_DISTRIBUTION_COMPARISON,
    DEFAULT_DISTRIBUTION_POPULATION,
    DISTRIBUTION_COMPARISONS,
    DISTRIBUTION_POPULATIONS,
    PASSING_CONTRACTS_POPULATION,
    REJECTED_CONTRACTS_POPULATION,
    TRUE_NEAR_MISS_CONTRACTS_POPULATION,
    average_rule_contribution,
    comparison_quality_variable_distributions,
    contract_fingerprint,
    dashboard_metadata,
    dashboard_observations,
    discovery_diagnostic_summary,
    distribution_population,
    distribution_population_summary,
    quality_variable_distributions,
    quality_score_distribution,
    rule_failure_distribution,
    status_distribution,
)
from src.navigation import apply_pending_navigation, request_navigation
from src.rce_benchmark_explorer_page import render_benchmark_explorer
from src.research_universe_builder_page import render_research_universe_builder, start_new_research
from src.research_universe_review_page import render_current_research_universe_page
from src.research_universe_repository import (
    recover_universe_from_snapshot,
    research_universe_repository_from_env,
)
from src.research_repository import (
    DATABASE_URL_ENV,
    RESEARCH_REPOSITORY_BACKEND_ENV,
    research_repository_from_env,
    research_repository_target_from_env,
)
from src.research_conversation import (
    ResearchConversationService,
    create_research_conversation_provider,
    research_conversation_confidence_threshold,
)
from src.study_protocol import DEFAULT_STUDY_PROTOCOL, RUN_MODE_MANUAL_UI, TAM_STUDY_PROTOCOL
from src.technical_analysis import (
    derived_technical_display_fields,
    technical_analysis_rows_for_symbols,
    technical_setup_grade,
    technical_setup_score,
)
from src.tradier_client import TradierAPIError, TradierClient, TradierConfigurationError
from src.universe import UniverseError, load_universe
from src.universe_analysis_page import render_universe_analysis

ROOT = Path(__file__).resolve().parent
EASTERN_TIME = ZoneInfo("America/New_York")
UNAVAILABLE = "-"
DEFAULT_DISCOVERY_MIN_DTE = DEFAULT_EVALUATION_PROFILE.default_scan_parameters["min_dte"]
DEFAULT_DISCOVERY_MAX_DTE = DEFAULT_EVALUATION_PROFILE.default_scan_parameters["max_dte"]
APP_PASSWORD_ENV = "APP_PASSWORD"
RCE_PROVIDER_ENV = "RCE_PROVIDER"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"

DISTRIBUTION_THRESHOLD_NOTES = {
    "Delta Distribution": (
        f"Pass threshold: Delta {CALL_DELTA_RANGE[0]:.2f} to "
        f"{CALL_DELTA_RANGE[1]:.2f} by absolute value."
    ),
    "Spread % Distribution": f"Pass threshold: Spread <= {MAX_SPREAD_PERCENT:.2%}.",
    "Volume Distribution": (
        f"Pass threshold: Volume >= {MIN_VOLUME:,}; pass-zone buckets begin at "
        "501-1,000."
    ),
    "Open Interest Distribution": (
        f"Pass threshold: Open Interest >= {MIN_OPEN_INTEREST:,}; pass-zone "
        "buckets begin at 1,001-2,500."
    ),
}


def style_all_passed(value):
    """Highlight the aggregate quality result without changing contract logic."""
    if value == "Yes":
        return "background-color: #d1fae5; color: #065f46"
    return "background-color: #fee2e2; color: #991b1b"


def format_eastern_timestamp(value):
    """Format Tradier epoch timestamps in the user's Eastern time zone."""
    if value is None or (isinstance(value, str) and value == ""):
        return UNAVAILABLE
    try:
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, timezone.utc).astimezone(EASTERN_TIME).strftime(
            "%Y-%m-%d %I:%M:%S %p %Z"
        )
    except (TypeError, ValueError, OverflowError, OSError):
        return UNAVAILABLE


def mid_price(quote):
    """Keep the quote display compatible with the shared pricing calculation."""
    return calculate_mid_price(quote.get("bid"), quote.get("ask"))


def format_whole_number(value):
    """Render count fields without changing their underlying values."""
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return value if value not in (None, "") else UNAVAILABLE


def format_decimal(value):
    """Render numeric values to two decimal places for table display."""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return value if value not in (None, "") else UNAVAILABLE


def percentage_distance(margin, threshold):
    """Express a rule margin relative to its threshold for display only."""
    try:
        return float(margin) / float(threshold)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def format_percentage_distance(margin, threshold):
    """Format a signed threshold-relative margin as a percentage."""
    distance = percentage_distance(margin, threshold)
    return f"{distance:.2%}" if distance is not None else UNAVAILABLE


def format_percent(value):
    """Render a decimal percentage with a consistent two-decimal precision."""
    if value is None or (isinstance(value, str) and value == ""):
        return UNAVAILABLE
    if not isinstance(value, Number) or isinstance(value, bool):
        return value
    try:
        numeric_value = float(value)
    except (TypeError, ValueError, OverflowError):
        return value
    return f"{numeric_value:.2%}" if isfinite(numeric_value) else value


def signed_strike_distance_percent(strike, underlying_price):
    """Return strike distance as a signed percentage of the underlying price."""
    try:
        strike_value = float(strike)
        underlying_value = float(underlying_price)
    except (TypeError, ValueError):
        return UNAVAILABLE
    if underlying_value <= 0:
        return UNAVAILABLE
    return (strike_value - underlying_value) / underlying_value


def as_list(value):
    """Normalize Tradier fields that can be a single item or a list."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def expiration_dates(payload):
    """Extract the available expiration dates from a Tradier response."""
    expirations = payload.get("expirations", {})
    if not isinstance(expirations, dict):
        return []
    return [str(date) for date in as_list(expirations.get("date")) if date]


def expiration_dte(expiration, today):
    """Return days to expiration for an ISO expiration date."""
    try:
        expiration_date = date.fromisoformat(str(expiration))
    except (TypeError, ValueError):
        return None
    return (expiration_date - today).days


def expirations_in_dte_range(payload, today, min_dte, max_dte):
    """Return listed expirations inside the selected DTE window."""
    return [
        expiration
        for expiration in sorted(expiration_dates(payload))
        if (dte := expiration_dte(expiration, today)) is not None
        and min_dte <= dte <= max_dte
    ]


def implied_volatility(greeks):
    """Return Tradier's preferred available implied-volatility value."""
    for field in ("mid_iv", "smv_vol", "ask_iv", "bid_iv"):
        value = greeks.get(field)
        if value not in (None, ""):
            return value
    return UNAVAILABLE


def format_contract_label(ticker, strike, option_type, expiration):
    """Return the trader-readable label for an option contract."""
    ticker_display = str(ticker).upper() if ticker not in (None, "") else UNAVAILABLE
    try:
        strike_display = f"{float(strike):g}"
    except (TypeError, ValueError):
        strike_display = strike if strike not in (None, "") else UNAVAILABLE
    type_display = (
        str(option_type).capitalize() if option_type not in (None, "") else UNAVAILABLE
    )
    try:
        expiration_display = datetime.fromisoformat(str(expiration)).strftime("%m/%d/%Y")
    except (TypeError, ValueError):
        expiration_display = expiration if expiration not in (None, "") else UNAVAILABLE
    return f"{ticker_display} {strike_display} {type_display} {expiration_display}"


def option_chain_rows(
    payload, expiration=None, today=None, underlying_price=None, ticker=None
):
    """Map the raw Tradier option response to the explorer's display schema."""
    options = payload.get("options", {})
    if not isinstance(options, dict):
        return []

    rows = []
    for option in as_list(options.get("option")):
        if not isinstance(option, dict):
            continue
        greeks = option.get("greeks")
        greeks = greeks if isinstance(greeks, dict) else {}
        underlying_symbol = ticker or option.get("root_symbol")
        quality = contract_quality(
            option,
            expiration=expiration,
            today=today,
            underlying_price=underlying_price,
        )
        expiration_value = expiration or option.get("expiration_date", UNAVAILABLE)
        option_type = option.get("option_type", UNAVAILABLE)
        rows.append(
            {
                "Ticker": normalized_symbol(underlying_symbol),
                "Underlying Symbol": normalized_symbol(option.get("root_symbol") or underlying_symbol),
                "Symbol": option.get("symbol", UNAVAILABLE),
                "Strike": option.get("strike", UNAVAILABLE),
                "Expiration": expiration_value,
                "Option Type": option_type,
                "Underlying Price": underlying_price
                if underlying_price is not None
                else UNAVAILABLE,
                "Strike Distance (%)": signed_strike_distance_percent(
                    option.get("strike"), underlying_price
                ),
                "Contract": format_contract_label(
                    underlying_symbol,
                    option.get("strike"),
                    option_type,
                    expiration_value,
                ),
                "Bid": option.get("bid", UNAVAILABLE),
                "Ask": option.get("ask", UNAVAILABLE),
                "Delta": greeks.get("delta", UNAVAILABLE),
                "Implied Volatility": implied_volatility(greeks),
                "IV": implied_volatility(greeks),
                "Volume": option.get("volume", UNAVAILABLE),
                "Open Interest": option.get("open_interest", UNAVAILABLE),
                **quality,
            }
        )
    return rows


def drilldown_contract_columns(include_failure=False):
    """Return the compact display schema shared by diagnostics drilldowns."""
    columns = [
        "Contract",
        "Quality Score",
        "DTE",
        "Delta",
        "IV",
        "Bid",
        "Ask",
        "Spread %",
    ]
    return columns + (["Failed Test", "Relevant Rule Detail"] if include_failure else [])


def format_drilldown_dataframe(rows, columns):
    return pd.DataFrame(rows).reindex(columns=columns).style.format(
        {
            "Strike": format_decimal,
            "Quality Score": "{:,.0f}",
            "Bid": format_decimal,
            "Ask": format_decimal,
            "Mid Price": format_decimal,
            "Spread": format_decimal,
            "Delta": format_decimal,
            "IV": format_percent,
            "Spread %": format_percent,
            "Strike Distance %": format_percent,
            "Volume": "{:,.0f}",
            "Open Interest": "{:,.0f}",
        }
    )


def failure_label(row):
    """Return the single failed test's readable label for near-miss rows."""
    for label, check in TEST_SPECIFIC_NEAR_MISS_OPTIONS.items():
        if row.get(check) == "Fail":
            return label
    return UNAVAILABLE


def margin_from_passing(selected_test, row):
    """Describe a selected test's shortfall without changing rule results."""
    margin = row.get(RULE_MARGIN_COLUMNS[TEST_SPECIFIC_NEAR_MISS_OPTIONS[selected_test]])
    try:
        shortfall = abs(float(margin))
    except (TypeError, ValueError):
        return UNAVAILABLE
    if selected_test == "Spread":
        relative_shortfall = shortfall / MAX_SPREAD_PERCENT
        return (
            f"{relative_shortfall:.2%} above the {MAX_SPREAD_PERCENT:.2%} threshold "
            f"({shortfall * 100:.2f} percentage points)"
        )
    if selected_test == "Delta":
        return f"{shortfall:.2f} delta outside the target range"
    threshold = MIN_OPEN_INTEREST if selected_test == "Open Interest" else MIN_VOLUME
    relative_shortfall = shortfall / threshold
    return f"{relative_shortfall:.2%} below the {threshold:,.0f} threshold ({shortfall:,.0f} contracts)"


def rule_detail_for_display(selected_test, row):
    """Format the selected rule's detail for a diagnostics table."""
    if selected_test == "Spread":
        margin = row.get("Spread Margin")
        return (
            f"Actual {format_percent(row.get('Spread %'))} / "
            f"Required {MAX_SPREAD_PERCENT:.2%} / "
            f"Margin {format_percentage_distance(margin, MAX_SPREAD_PERCENT)}"
        )
    if selected_test == "Open Interest":
        actual, margin, threshold = row.get("Open Interest"), row.get("OI Margin"), MIN_OPEN_INTEREST
    elif selected_test == "Volume":
        actual, margin, threshold = row.get("Volume"), row.get("Volume Margin"), MIN_VOLUME
    else:
        return row.get("Delta Rule Detail", UNAVAILABLE)
    return (
        f"Actual {format_whole_number(actual)} / Required {threshold:,.0f} / "
        f"Margin {format_percentage_distance(margin, threshold)}"
    )


def opportunity_candidate_display(candidate, selected_test=None):
    """Format a shortfall and contract label for an opportunity card.

    Count-based margins are normalized to their existing rule thresholds so
    every card presents a percentage, without changing candidate selection.
    """
    if candidate is None:
        return "None", UNAVAILABLE
    failed_test = selected_test or failure_label(candidate)
    check = TEST_SPECIFIC_NEAR_MISS_OPTIONS.get(failed_test)
    margin = candidate.get(RULE_MARGIN_COLUMNS[check]) if check else None
    try:
        shortfall = abs(float(margin))
    except (TypeError, ValueError):
        return UNAVAILABLE, candidate.get("Contract", UNAVAILABLE)

    if failed_test == "Open Interest":
        shortfall /= MIN_OPEN_INTEREST
    elif failed_test == "Volume":
        shortfall /= MIN_VOLUME

    return f"{shortfall:.2%} from passing", candidate.get("Contract", UNAVAILABLE)


def quality_score_display(candidate):
    """Return a candidate's already-calculated quality score for display."""
    if candidate is None:
        return UNAVAILABLE
    return format_whole_number(candidate.get("Quality Score"))


def quality_score_sort_value(row):
    """Return a stable sort value for already-calculated quality scores."""
    value = row.get("Quality Score")
    try:
        score = float(value)
    except (TypeError, ValueError):
        return float("-inf")
    return score if isfinite(score) else float("-inf")


def sort_by_quality_score_desc(rows):
    """Order display rows by quality score without changing quality logic."""
    return sorted(rows, key=quality_score_sort_value, reverse=True)


def parse_universe_symbols(value):
    """Return uppercase symbols from a newline/comma separated symbol list."""
    symbols = []
    seen = set()
    for raw_symbol in value.replace(",", "\n").splitlines():
        symbol = raw_symbol.strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return symbols


parse_watchlist = parse_universe_symbols


def filter_by_dte_range(rows, min_dte, max_dte):
    """Return rows whose already-calculated DTE is inside the selected window."""
    filtered_rows = []
    for row in rows:
        try:
            dte = int(row.get("DTE"))
        except (TypeError, ValueError):
            continue
        if min_dte <= dte <= max_dte:
            filtered_rows.append(row)
    return filtered_rows


def discover_universe_opportunities(
    client,
    universe_symbols,
    today,
    option_type="Calls",
    min_dte=DEFAULT_DISCOVERY_MIN_DTE,
    max_dte=DEFAULT_DISCOVERY_MAX_DTE,
):
    """Fetch and evaluate option chains matching the discovery filters."""
    evaluated_rows = {}
    evaluated_contract_rows = []
    placeholder_rows = []
    errors = {}
    for symbol in universe_symbols:
        try:
            expiration_payload = client.get_option_expirations(symbol)
            quote_payload = client.get_quote(symbol)
            underlying_price = quote_last_price(quote_payload)
            expirations = expirations_in_dte_range(
                expiration_payload, today, min_dte, max_dte
            )
            if not expirations:
                placeholder_rows.append(no_matching_contracts_row(symbol, underlying_price))
                continue
            rows = []
            for expiration in expirations:
                chain_payload = client.get_option_chain(symbol, expiration)
                rows.extend(
                    option_chain_rows(
                        chain_payload,
                        expiration=expiration,
                        today=today,
                        underlying_price=underlying_price,
                        ticker=symbol,
                    )
                )
            rows = filter_by_option_type(
                filter_by_dte_range(rows, min_dte, max_dte), option_type
            )
            if not rows:
                placeholder_rows.append(no_matching_contracts_row(symbol, underlying_price))
                continue
            evaluated_rows[symbol] = rows
            evaluated_contract_rows.extend(rows)
        except (TradierAPIError, ValueError) as error:
            errors[symbol] = str(error)
    return opportunity_table_rows(evaluated_rows, placeholder_rows), errors, evaluated_contract_rows


discover_watchlist_opportunities = discover_universe_opportunities


def format_opportunity_table(rows):
    """Format the ranked opportunity table without changing selected row data."""
    columns = [
        "Rank",
        "Ticker",
        "Contract",
        "Quality Score",
        "Underlying Price",
        "Strike Distance (%)",
        "Status",
        "Primary Weakness",
        "Primary Strength",
    ]
    return pd.DataFrame(rows).reindex(columns=columns).style.format(
        {
            "Rank": format_whole_number,
            "Quality Score": format_whole_number,
            "Underlying Price": format_decimal,
            "Strike Distance (%)": format_percent,
        }
    )


def format_contract_detail_value(label, value):
    """Format a summary value according to its displayed contract field."""
    if label in {"Strike", "Bid", "Ask", "Mid Price", "Delta"}:
        return format_decimal(value)
    if label in {"Spread %", "IV"}:
        return format_percent(value)
    if label in {"DTE", "Open Interest", "Volume", "Quality Score"}:
        return format_whole_number(value)
    return value if value not in (None, "") else UNAVAILABLE


def format_rule_explanations_dataframe(explanations):
    """Format the rule explanation table without changing rule values."""
    formatted_rows = []
    for explanation in explanations:
        row = dict(explanation)
        if row["Rule"] == "Spread":
            for field in ("Actual Value", "Required Value", "Margin"):
                row[field] = format_percent(row[field])
        elif row["Rule"] == "Delta Fit":
            row["Actual Value"] = format_decimal(row["Actual Value"])
            row["Margin"] = format_decimal(row["Margin"])
        else:
            for field in ("Actual Value", "Required Value", "Margin"):
                row[field] = format_whole_number(row[field])
        formatted_rows.append(row)
    return pd.DataFrame(formatted_rows)


def format_quality_score_breakdown_dataframe(breakdown):
    """Format score components while retaining their existing rule margins."""
    formatted_rows = []
    for item in breakdown:
        row = dict(item)
        row["Score"] = f"{row.pop('Points')} / {row.pop('Weight')}"
        if row["Rule"] == "Spread":
            row["Margin"] = format_percent(row["Margin"])
        elif row["Rule"] == "Delta Fit":
            row["Margin"] = format_decimal(row["Margin"])
        else:
            row["Margin"] = format_whole_number(row["Margin"])
        formatted_rows.append(row)
    return pd.DataFrame(formatted_rows).reindex(
        columns=["Rule", "Score", "Pass/Fail", "Margin"]
    )


def selected_dataframe_row(selection_event, rows):
    """Return the selected row from a single-row dataframe selection event."""
    selected_rows = selection_event.selection.rows
    if not selected_rows:
        return None
    selected_index = selected_rows[0]
    return rows[selected_index] if selected_index < len(rows) else None


def render_contract_detail_summary(contract, source_label):
    """Render a selected contract's details in its originating drilldown section."""
    if contract is None:
        return
    st.subheader("Contract Detail Summary")
    st.markdown(f"**{contract.get('Contract', UNAVAILABLE)}**")
    st.caption(f"Source: {source_label}")
    detail_fields = contract_detail_fields(contract)
    detail_columns = st.columns(3)
    for index, (label, value) in enumerate(detail_fields.items()):
        detail_columns[index % 3].metric(label, format_contract_detail_value(label, value))
    st.markdown("Quality Score Breakdown")
    st.dataframe(
        format_quality_score_breakdown_dataframe(
            contract.get("Quality Score Breakdown", [])
        ),
        hide_index=True,
        width="stretch",
    )
    st.markdown("Rule-by-rule explanation")
    st.dataframe(
        format_rule_explanations_dataframe(contract_rule_explanations(contract)),
        hide_index=True,
        width="stretch",
    )
    st.caption(contract_interpretation(contract))


def render_selectable_drilldown(rows, columns, source_label, key):
    """Render one drilldown table and the detail summary for its selected row."""
    selection_event = st.dataframe(
        format_drilldown_dataframe(rows, columns),
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        key=key,
    )
    render_contract_detail_summary(selected_dataframe_row(selection_event, rows), source_label)


def format_diagnostic_metric(label, value):
    """Render diagnostic aggregate values without changing their calculations."""
    if value is None:
        return UNAVAILABLE
    if label in {
        "Contracts Evaluated",
        "Population Count",
        "Passing Contracts Count",
        "True Near Miss Count",
        "Rejected Count",
        "Highest Quality Score",
        "Lowest Quality Score",
        "Average DTE",
        "Average Open Interest",
        "Average Volume",
        "Tickers Characterized",
        "Bullish Trend Count",
        "Bearish Trend Count",
        "Neutral/Mixed Count",
        "SAM Error Count",
        "TAM Error Count",
    }:
        return format_whole_number(value)
    if label in {
        "Average Strike Distance %",
        "Average Spread %",
        "Passing %",
        "True Near Miss %",
        "Rejected %",
    }:
        return format_percent(value)
    return format_decimal(value)


def render_metric_grid(metrics, columns_per_row=4):
    """Render a compact metric grid from an ordered mapping."""
    metric_items = list(metrics.items())
    for start in range(0, len(metric_items), columns_per_row):
        for column, (label, value) in zip(
            st.columns(columns_per_row), metric_items[start : start + columns_per_row]
        ):
            column.metric(label, format_diagnostic_metric(label, value))


def render_bar_chart(rows, index_column, value_column):
    """Render a Streamlit-native bar chart from diagnostic rows."""
    chart_data = pd.DataFrame(rows).set_index(index_column)
    st.bar_chart(chart_data, y=value_column)


def render_distribution_bar_chart(rows):
    """Render distribution buckets in their configured order."""
    chart_data = pd.DataFrame(rows)
    chart = (
        alt.Chart(chart_data)
        .mark_bar()
        .encode(
            x=alt.X("Bucket:N", sort=list(chart_data["Bucket"]), title=None),
            y=alt.Y("Count:Q", title="Count"),
            tooltip=[
                alt.Tooltip("Bucket:N"),
                alt.Tooltip("Zone:N"),
                alt.Tooltip("Count:Q", format=","),
                alt.Tooltip("Percentage:Q", format=".1%"),
            ],
        )
    )
    st.altair_chart(chart, use_container_width=True)


def render_distribution_table(rows):
    """Render bucket count and percentage for one selected diagnostic distribution."""
    st.dataframe(
        pd.DataFrame(rows)
        .reindex(columns=["Bucket", "Zone", "Count", "Percentage"])
        .style.format(
            {
                "Count": format_whole_number,
                "Percentage": format_percent,
            }
        ),
        hide_index=True,
        width="stretch",
    )


def render_comparison_distribution_table(rows):
    """Render bucket count and percentage for two diagnostic populations."""
    columns = list(rows[0].keys()) if rows else []
    percentage_columns = [column for column in columns if column.endswith(" %")]
    count_columns = [column for column in columns if column.endswith(" Count")]
    st.dataframe(
        pd.DataFrame(rows)
        .reindex(columns=columns)
        .style.format(
            {
                **{column: format_whole_number for column in count_columns},
                **{column: format_percent for column in percentage_columns},
            }
        ),
        hide_index=True,
        width="stretch",
    )


def render_comparison_distribution_bar_chart(rows):
    """Render grouped count bars for two population distributions."""
    chart_data = pd.DataFrame(rows)
    count_columns = [column for column in chart_data.columns if column.endswith(" Count")]
    if chart_data.empty or not count_columns:
        return

    long_data = chart_data.melt(
        id_vars=["Bucket", "Zone"],
        value_vars=count_columns,
        var_name="Population",
        value_name="Count",
    )
    long_data["Population"] = long_data["Population"].str.removesuffix(" Count")
    chart = (
        alt.Chart(long_data)
        .mark_bar()
        .encode(
            x=alt.X("Bucket:N", sort=list(chart_data["Bucket"]), title=None),
            xOffset=alt.XOffset("Population:N"),
            y=alt.Y("Count:Q", title="Count"),
            color=alt.Color("Population:N", title=None),
            tooltip=[
                alt.Tooltip("Bucket:N"),
                alt.Tooltip("Zone:N"),
                alt.Tooltip("Population:N"),
                alt.Tooltip("Count:Q", format=","),
            ],
        )
    )
    st.altair_chart(chart, use_container_width=True)


def render_distribution_diagnostics(evaluated_rows):
    """Render population-level quality-variable distributions."""
    st.markdown("Distribution Diagnostics")
    mode = st.radio(
        "Mode",
        ("Single Population", "Comparison"),
        horizontal=True,
        key="quality_distribution_mode",
    )

    if mode == "Comparison":
        comparison_label = st.selectbox(
            "Comparison",
            tuple(DISTRIBUTION_COMPARISONS.keys()),
            index=tuple(DISTRIBUTION_COMPARISONS.keys()).index(
                DEFAULT_DISTRIBUTION_COMPARISON
            ),
            key="quality_distribution_comparison",
        )
        population_a, population_b = DISTRIBUTION_COMPARISONS[comparison_label]
        rows_a = distribution_population(evaluated_rows, population_a)
        rows_b = distribution_population(evaluated_rows, population_b)

        left_summary, right_summary = st.columns(2)
        with left_summary:
            st.markdown(population_a)
            render_metric_grid(distribution_population_summary(rows_a), columns_per_row=2)
        with right_summary:
            st.markdown(population_b)
            render_metric_grid(distribution_population_summary(rows_b), columns_per_row=2)

        if not rows_a or not rows_b:
            st.info("One or both comparison populations have no contracts.")

        distributions = comparison_quality_variable_distributions(
            evaluated_rows,
            population_a,
            population_b,
        )
        for left_label, right_label in (
            ("Delta Distribution", "Spread % Distribution"),
            ("Volume Distribution", "Open Interest Distribution"),
        ):
            left_column, right_column = st.columns(2)
            with left_column:
                st.markdown(left_label)
                st.caption(DISTRIBUTION_THRESHOLD_NOTES[left_label])
                render_comparison_distribution_table(distributions[left_label])
                render_comparison_distribution_bar_chart(distributions[left_label])
            with right_column:
                st.markdown(right_label)
                st.caption(DISTRIBUTION_THRESHOLD_NOTES[right_label])
                render_comparison_distribution_table(distributions[right_label])
                render_comparison_distribution_bar_chart(distributions[right_label])
        return

    population = st.selectbox(
        "Population",
        DISTRIBUTION_POPULATIONS,
        index=DISTRIBUTION_POPULATIONS.index(DEFAULT_DISTRIBUTION_POPULATION),
        key="quality_distribution_population",
    )
    selected_rows = distribution_population(evaluated_rows, population)
    render_metric_grid(distribution_population_summary(selected_rows), columns_per_row=3)

    if not selected_rows:
        st.info("No contracts are available for the selected population.")
        return

    distributions = quality_variable_distributions(selected_rows)
    for left_label, right_label in (
        ("Delta Distribution", "Spread % Distribution"),
        ("Volume Distribution", "Open Interest Distribution"),
    ):
        left_column, right_column = st.columns(2)
        with left_column:
            st.markdown(left_label)
            st.caption(DISTRIBUTION_THRESHOLD_NOTES[left_label])
            render_distribution_table(distributions[left_label])
            render_distribution_bar_chart(distributions[left_label])
        with right_column:
            st.markdown(right_label)
            st.caption(DISTRIBUTION_THRESHOLD_NOTES[right_label])
            render_distribution_table(distributions[right_label])
            render_distribution_bar_chart(distributions[right_label])


def render_rule_failure_distribution(rows):
    """Render failure counts and rates for each quality rule."""
    failure_rows = rule_failure_distribution(rows)
    st.dataframe(
        pd.DataFrame(failure_rows)
        .reindex(
            columns=[
                "Rule",
                "Failure Summary",
                "Failure Count",
                "Failure Percentage",
            ]
        )
        .style.format(
            {
                "Failure Count": format_whole_number,
                "Failure Percentage": format_percent,
            }
        ),
        hide_index=True,
        width="stretch",
    )
    render_bar_chart(failure_rows, "Rule", "Failure Percentage")


def render_dashboard_metadata(metadata):
    """Render scan context separately from numeric diagnostics."""
    rows = [{"Field": label, "Value": value} for label, value in metadata.items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def render_dashboard_observations(observations):
    """Render computed factual observations for the current scan."""
    if not observations:
        st.caption("No observations are available for the current scan.")
        return
    for observation in observations:
        st.caption(f"- {observation}")


def diagnostic_overview_metrics(evaluated_rows):
    """Return scan outcome metrics with percentage context for display only."""
    summary = discovery_diagnostic_summary(evaluated_rows)
    evaluated_count = summary["Contracts Evaluated"]

    def share(count):
        return count / evaluated_count if evaluated_count else None

    return {
        "Contracts Evaluated": evaluated_count,
        "Passing Contracts Count": summary["Passing Contracts Count"],
        "Passing %": share(summary["Passing Contracts Count"]),
        "True Near Miss Count": summary["True Near Miss Count"],
        "True Near Miss %": share(summary["True Near Miss Count"]),
        "Rejected Count": summary["Rejected Count"],
        "Rejected %": share(summary["Rejected Count"]),
        "Average Quality Score": summary["Average Quality Score"],
        "Median Quality Score": summary["Median Quality Score"],
        "Highest Quality Score": summary["Highest Quality Score"],
        "Lowest Quality Score": summary["Lowest Quality Score"],
    }


def scan_export_context(scan_id, scan_timestamp, universe_name):
    """Return stable Opportunity Scan fields shared by validation exports.

    The legacy model_name field is retained for export compatibility. The
    explicit contract_quality_model_* fields clarify that the current scoring
    model evaluates option contracts, while future Technical or Trade Fit
    models remain independent and optional.
    """
    return {
        "scan_id": scan_id,
        "scan_timestamp": scan_timestamp,
        "universe_name": universe_name,
        "model_name": "Quality Score",
        **evaluation_profile_export_fields(),
    }


def contract_classification(row):
    """Classify a contract from existing quality outcomes without changing rules."""
    if row.get("All Passed") == "Yes":
        return "Passing"
    if len([check for check in TEST_SPECIFIC_NEAR_MISS_OPTIONS.values() if row.get(check) == "Fail"]) == 1:
        return "True Near Miss"
    return "Rejected"


def failed_rule_names(row):
    """Return failed rule labels for future Contract Quality Model validation tests."""
    failed = [
        label
        for label, check in TEST_SPECIFIC_NEAR_MISS_OPTIONS.items()
        if row.get(check) == "Fail"
    ]
    return ", ".join(failed)


def dataframe_csv_download(rows, columns):
    """Serialize export rows to CSV bytes with a stable column order."""
    return pd.DataFrame(rows).reindex(columns=columns).to_csv(index=False).encode("utf-8")


def normalized_symbol(value):
    """Return a stable uppercase symbol or the unavailable marker."""
    if value in (None, ""):
        return UNAVAILABLE
    symbol = str(value).strip().upper()
    return symbol if symbol else UNAVAILABLE


def validate_evaluated_contract_tickers(evaluated_rows, active_universe_symbols=None):
    """Ensure evaluated contract rows retain a usable known-source ticker."""
    active_symbols = (
        {normalized_symbol(symbol) for symbol in active_universe_symbols}
        if active_universe_symbols is not None
        else None
    )
    for index, row in enumerate(evaluated_rows, start=1):
        ticker = normalized_symbol(row.get("Ticker"))
        contract_symbol = row.get("Symbol", UNAVAILABLE)
        if ticker in {UNAVAILABLE, "-"}:
            raise ValueError(
                f"Evaluated contract row {index} has a blank ticker for {contract_symbol}."
            )
        if active_symbols is not None and ticker not in active_symbols:
            raise ValueError(
                f"Evaluated contract row {index} ticker {ticker} is not in the active universe "
                f"for {contract_symbol}."
            )


def evaluated_contract_export_rows(
    evaluated_rows,
    scan_id,
    scan_timestamp,
    universe_name,
    active_universe_symbols=None,
):
    """Shape evaluated contracts for offline Contract Quality Model validation."""
    context = scan_export_context(scan_id, scan_timestamp, universe_name)
    validate_evaluated_contract_tickers(evaluated_rows, active_universe_symbols)
    return [
        {
            **context,
            "ticker": normalized_symbol(row.get("Ticker")),
            "option_type": row.get("Option Type", UNAVAILABLE),
            "expiration": row.get("Expiration", UNAVAILABLE),
            "strike": row.get("Strike", UNAVAILABLE),
            "contract_symbol": row.get("Symbol", UNAVAILABLE),
            "contract_label": row.get("Contract", UNAVAILABLE),
            "dte": row.get("DTE", UNAVAILABLE),
            "underlying_price": row.get("Underlying Price", UNAVAILABLE),
            "bid": row.get("Bid", UNAVAILABLE),
            "ask": row.get("Ask", UNAVAILABLE),
            "mid": row.get("Mid Price", UNAVAILABLE),
            "spread_pct": row.get("Spread %", UNAVAILABLE),
            "delta": row.get("Delta", UNAVAILABLE),
            "open_interest": row.get("Open Interest", UNAVAILABLE),
            "volume": row.get("Volume", UNAVAILABLE),
            "quality_score": row.get("Quality Score", UNAVAILABLE),
            "classification": contract_classification(row),
            "failed_rules": failed_rule_names(row),
            "primary_strength": primary_contract_strength(row),
            "primary_weakness": primary_contract_weakness(row),
        }
        for row in evaluated_rows
    ]


RULE_EXPORT_SPECS = (
    {
        "rule_name": "Delta Fit",
        "weight_key": "Delta Fit",
        "check": "Delta Fit",
        "actual": "Delta",
        "margin": "Delta Margin",
    },
    {
        "rule_name": "Spread",
        "weight_key": "Spread",
        "check": "Spread Pass",
        "actual": "Spread %",
        "margin": "Spread Margin",
        "target": f"<= {MAX_SPREAD_PERCENT}",
    },
    {
        "rule_name": "Open Interest",
        "weight_key": "Open Interest",
        "check": "Open Interest Pass",
        "actual": "Open Interest",
        "margin": "OI Margin",
        "target": f">= {MIN_OPEN_INTEREST}",
    },
    {
        "rule_name": "Volume",
        "weight_key": "Volume",
        "check": "Volume Pass",
        "actual": "Volume",
        "margin": "Volume Margin",
        "target": f">= {MIN_VOLUME}",
    },
)


def delta_target(row):
    """Return the existing delta target for the contract's option type."""
    option_type = str(row.get("Option Type", "")).lower()
    if option_type == "put":
        return "-0.7 to -0.5"
    if option_type == "call":
        return "0.5 to 0.7"
    return UNAVAILABLE


def score_breakdown_by_rule(row):
    """Index the existing per-rule score breakdown by rule name."""
    breakdown = row.get("Quality Score Breakdown")
    if not isinstance(breakdown, list):
        return {}
    return {
        item.get("Rule"): item
        for item in breakdown
        if isinstance(item, dict) and item.get("Rule")
    }


def rule_evaluation_export_rows(evaluated_rows, scan_id):
    """Export one row per existing rule evaluation for validation replay."""
    rows = []
    context = evaluation_profile_export_fields()
    for contract in evaluated_rows:
        breakdown = score_breakdown_by_rule(contract)
        contract_symbol = contract.get("Symbol", UNAVAILABLE)
        for spec in RULE_EXPORT_SPECS:
            score_item = breakdown.get(spec["rule_name"], {})
            rows.append(
                {
                    "scan_id": scan_id,
                    **context,
                    "contract_symbol": contract_symbol,
                    "rule_name": spec["rule_name"],
                    "rule_weight": QUALITY_WEIGHTS.get(spec["weight_key"], UNAVAILABLE),
                    "actual_value": contract.get(spec["actual"], UNAVAILABLE),
                    "target": delta_target(contract)
                    if spec["rule_name"] == "Delta Fit"
                    else spec["target"],
                    "pass_fail_status": contract.get(spec["check"], UNAVAILABLE),
                    "threshold_distance": contract.get(spec["margin"], UNAVAILABLE),
                    "rule_score": score_item.get("Points", UNAVAILABLE),
                    "max_rule_score": score_item.get(
                        "Weight", QUALITY_WEIGHTS.get(spec["weight_key"], UNAVAILABLE)
                    ),
                }
            )
    return rows


def json_safe(value):
    """Convert diagnostic values to strict JSON-safe primitives."""
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, Number):
        number = float(value)
        if not isfinite(number):
            return None
        return int(number) if number.is_integer() else number
    return value


def qed_summary_export(
    evaluated_rows,
    opportunity_rows,
    scan_id,
    scan_timestamp,
    universe_name,
):
    """Build nested QED metrics for Opportunity Scan diagnostics."""
    summary = discovery_diagnostic_summary(evaluated_rows)
    failure_rows = rule_failure_distribution(evaluated_rows)
    population_profiles = {
        "all_contracts": population_profile_metrics(evaluated_rows),
        "passing": population_profile_metrics(
            distribution_population(evaluated_rows, PASSING_CONTRACTS_POPULATION)
        ),
        "true_near_miss": population_profile_metrics(
            distribution_population(evaluated_rows, TRUE_NEAR_MISS_CONTRACTS_POPULATION)
        ),
        "rejected": population_profile_metrics(
            distribution_population(evaluated_rows, REJECTED_CONTRACTS_POPULATION)
        ),
        "top_opportunities": population_profile_metrics(
            sort_by_quality_score_desc(
                [
                    row
                    for row in opportunity_rows
                    if row.get("Status") in {"Passing", "True Near Miss"}
                    and row.get("Quality Score") not in (None, "")
                ]
            )[:10]
        ),
    }
    return json_safe(
        {
            **scan_export_context(scan_id, scan_timestamp, universe_name),
            "contracts_evaluated": summary["Contracts Evaluated"],
            "passing_count": summary["Passing Contracts Count"],
            "true_near_miss_count": summary["True Near Miss Count"],
            "rejected_count": summary["Rejected Count"],
            "average_quality_score": summary["Average Quality Score"],
            "median_quality_score": summary["Median Quality Score"],
            "highest_quality_score": summary["Highest Quality Score"],
            "lowest_quality_score": summary["Lowest Quality Score"],
            "rule_failure_counts": {
                row["Rule"]: row["Failure Count"] for row in failure_rows
            },
            "rule_failure_percentages": {
                row["Rule"]: row["Failure Percentage"] for row in failure_rows
            },
            "population_profiles": population_profiles,
            "distribution_diagnostics": quality_variable_distributions(evaluated_rows),
        }
    )


def render_quality_export_section(
    evaluated_rows,
    opportunity_rows,
    scan_id,
    scan_timestamp,
    universe_name,
    active_universe_symbols=None,
):
    """Render exports that let validation test cases run outside the UI."""
    st.markdown("Export Most Recent Opportunity Scan")
    st.caption(
        "These exports preserve evaluated rows and rule outcomes for offline validation."
    )
    safe_scan_id = str(scan_id).replace(":", "").replace(" ", "_")
    contract_rows = evaluated_contract_export_rows(
        evaluated_rows,
        scan_id,
        scan_timestamp,
        universe_name,
        active_universe_symbols,
    )
    rule_rows = rule_evaluation_export_rows(evaluated_rows, scan_id)
    summary = qed_summary_export(
        evaluated_rows,
        opportunity_rows,
        scan_id,
        scan_timestamp,
        universe_name,
    )
    contract_columns = [
        "scan_id",
        "scan_timestamp",
        "universe_name",
        "model_name",
        "evaluation_profile_name",
        "evaluation_profile_version",
        "contract_quality_model_name",
        "contract_quality_model_version",
        "ticker",
        "option_type",
        "expiration",
        "strike",
        "contract_symbol",
        "contract_label",
        "dte",
        "underlying_price",
        "bid",
        "ask",
        "mid",
        "spread_pct",
        "delta",
        "open_interest",
        "volume",
        "quality_score",
        "classification",
        "failed_rules",
        "primary_strength",
        "primary_weakness",
    ]
    rule_columns = [
        "scan_id",
        "evaluation_profile_name",
        "evaluation_profile_version",
        "contract_quality_model_name",
        "contract_quality_model_version",
        "contract_symbol",
        "rule_name",
        "rule_weight",
        "actual_value",
        "target",
        "pass_fail_status",
        "threshold_distance",
        "rule_score",
        "max_rule_score",
    ]
    contract_column, rule_column, summary_column = st.columns(3)
    contract_column.download_button(
        "Evaluated Contracts CSV",
        dataframe_csv_download(contract_rows, contract_columns),
        file_name=f"{safe_scan_id}_evaluated_contracts.csv",
        mime="text/csv",
    )
    rule_column.download_button(
        "Rule Evaluations CSV",
        dataframe_csv_download(rule_rows, rule_columns),
        file_name=f"{safe_scan_id}_rule_evaluations.csv",
        mime="text/csv",
    )
    summary_column.download_button(
        "OAE Summary JSON",
        json.dumps(summary, indent=2).encode("utf-8"),
        file_name=f"{safe_scan_id}_qed_summary.json",
        mime="application/json",
    )


def archive_current_opportunity_scan(
    evaluated_rows,
    scan_id,
    scan_timestamp,
    universe_name,
    option_type,
    dte_min,
    dte_max,
    active_universe_symbols=None,
    study_protocol=None,
):
    """Persist completed scans for future model validation and longitudinal analysis."""
    technical_rows = []
    if active_universe_symbols:
        try:
            technical_rows, _technical_errors = technical_analysis_rows_for_symbols(
                TradierClient(),
                active_universe_symbols,
                scan_id=scan_id,
                technical_timestamp=scan_timestamp,
                end_date=datetime.now(EASTERN_TIME).date(),
            )
        except Exception:
            technical_rows = []
    contract_rows = evaluated_contract_export_rows(
        evaluated_rows,
        scan_id,
        scan_timestamp,
        universe_name,
        active_universe_symbols,
    )
    rule_rows = rule_evaluation_export_rows(evaluated_rows, scan_id)
    repository = research_repository_from_env()
    return repository.archive_opportunity_scan(
        scan_id=scan_id,
        scan_timestamp=scan_timestamp,
        universe_name=universe_name,
        option_type=option_type,
        dte_min=dte_min,
        dte_max=dte_max,
        evaluation_profile=evaluation_profile_export_fields(),
        evaluated_contract_rows=evaluated_rows,
        contract_export_rows=contract_rows,
        rule_export_rows=rule_rows,
        technical_rows=technical_rows,
        study_protocol=study_protocol,
    )


def render_sidebar_metric(label, value):
    st.caption(label)
    st.write(format_whole_number(value) if isinstance(value, Number) else value)


def render_dashboard_section(title, key, expanded=True):
    if key not in st.session_state:
        st.session_state[key] = expanded
    return st.checkbox(title, key=key)


def _masked_database_location(location):
    if "://" not in str(location):
        return location
    return str(location).split("://", 1)[0] + "://..."


def repository_startup_check():
    target = research_repository_target_from_env()
    repository = research_repository_from_env()
    status = repository.status(study_id=DEFAULT_STUDY_PROTOCOL.study_id)
    return target.backend, status


def render_startup_check():
    st.header("Startup Check")
    try:
        backend, status = repository_startup_check()
    except Exception as error:
        configured_backend = os.getenv(RESEARCH_REPOSITORY_BACKEND_ENV, "").strip()
        inferred_backend = "postgres" if os.getenv(DATABASE_URL_ENV) else "sqlite"
        render_sidebar_metric("Repository Backend", configured_backend or inferred_backend)
        render_sidebar_metric("Database Connectivity", "failed")
        render_sidebar_metric("Latest Scan Timestamp", UNAVAILABLE)
        st.error("Repository startup check failed: " + str(error))
        return None

    render_sidebar_metric("Repository Backend", backend)
    render_sidebar_metric("Database Connectivity", "ok")
    render_sidebar_metric("Latest Scan Timestamp", status.latest_scan_timestamp or UNAVAILABLE)
    return status


def render_sidebar_distribution(label, rows, column_name):
    st.caption(label)
    distribution = tam_count_rows(rows, column_name)
    if distribution:
        st.dataframe(pd.DataFrame(distribution), hide_index=True, width="stretch")
    else:
        st.write(UNAVAILABLE)


def render_opportunity_research_sidebar(status, universe_path, security_count):
    """Render opportunity research metadata in the persistent left sidebar."""
    st.markdown("#### Opportunity Research")
    rows_written = sum(status.latest_rows_written.values())
    scheduled_slots = len(DEFAULT_STUDY_PROTOCOL.suggested_schedule_times_et)
    completed_slots = len(status.today_completed_schedule_times)

    render_sidebar_metric("Research Universe CSV", str(Path(universe_path).expanduser()))
    render_sidebar_metric("Research Universe Securities", security_count)
    render_sidebar_metric("Latest Opportunity Observation", status.latest_scan_timestamp or UNAVAILABLE)
    render_sidebar_metric("Latest Study Protocol Execution", status.latest_scan_timestamp or UNAVAILABLE)
    render_sidebar_metric(
        "Scheduled Observation Progress",
        f"{completed_slots}/{scheduled_slots}",
    )
    render_sidebar_metric("Repository Status", "available")
    render_sidebar_metric("Database Location", _masked_database_location(status.database_path))
    render_sidebar_metric("Run Mode", status.latest_run_mode or UNAVAILABLE)
    render_sidebar_metric(
        "Manual vs Scheduled",
        status.latest_run_mode or UNAVAILABLE,
    )
    render_sidebar_metric("Scan Identifier", status.latest_scan_id or UNAVAILABLE)
    render_sidebar_metric("Rows Written", rows_written)
    render_sidebar_metric("Opportunity Observations", status.total_scans)
    render_sidebar_metric("Contracts Evaluated", status.total_contracts_evaluated)
    render_sidebar_metric("Rule Evaluations", status.total_rule_evaluations)


def render_security_research_sidebar(repository, status):
    """Render security-level research context in the persistent left sidebar."""
    st.markdown("#### Security Research")
    try:
        observations = repository.technical_analysis_observations(latest_scan_only=True)
        rows = [tam_display_row(row) for row in observations["rows"]]
    except Exception as error:
        st.error("Security Research unavailable: " + str(error))
        return

    render_sidebar_metric(
        "Latest Security Observation",
        observations["latest_technical_timestamp"] or UNAVAILABLE,
    )
    render_sidebar_metric("Latest Scan Timestamp", status.latest_scan_timestamp or UNAVAILABLE)
    render_sidebar_metric(
        "Securities Characterized",
        len({row.get("ticker") for row in rows if row.get("ticker")}),
    )
    render_sidebar_metric("Repository Status", "available")
    render_sidebar_metric(
        "Security Study Protocol Status",
        "Active" if observations["latest_technical_timestamp"] else "No observations",
    )
    render_sidebar_metric("Latest Study Identifier", TAM_STUDY_PROTOCOL.study_id)
    render_sidebar_metric("Run Mode", status.latest_run_mode or UNAVAILABLE)
    render_sidebar_metric("Version", TAM_STUDY_PROTOCOL.study_version)
    render_sidebar_metric("Error Count", tam_error_count(rows))
    render_sidebar_metric(
        "Total Technical Characterizations",
        status.total_technical_characterizations,
    )


def render_future_research_sidebar(status):
    for title, key in (
        ("Security Passports", "dashboard_security_passports_open"),
        ("Outcome Tracking", "dashboard_outcome_tracking_open"),
        ("Research Metrics", "dashboard_research_metrics_open"),
    ):
        if render_dashboard_section(title, key, expanded=False):
            st.caption("Reserved for future enhancement.")

    if render_dashboard_section("Scan History", "dashboard_scan_history_open", expanded=False):
        if status.recent_observations:
            st.dataframe(
                pd.DataFrame(status.recent_observations).rename(
                    columns={
                        "scan_id": "scan_id",
                        "scan_timestamp": "actual scan timestamp",
                        "study_id": "study_id",
                        "scheduled_time_label": "scheduled_time_label",
                        "run_mode": "run_mode",
                    }
                ),
                hide_index=True,
                width="stretch",
            )
        else:
            st.write("No scans archived yet.")


def render_research_sidebar_metadata(selected_section, universe_path, security_count):
    """Render operational research context in the persistent left sidebar."""
    if not selected_section:
        return
    try:
        repository = research_repository_from_env()
        status = repository.status(study_id=DEFAULT_STUDY_PROTOCOL.study_id)
    except Exception as error:
        st.error("Research unavailable: " + str(error))
        return

    if selected_section == "Security Research":
        render_security_research_sidebar(repository, status)
    elif selected_section == "Opportunity Research":
        render_opportunity_research_sidebar(status, universe_path, security_count)


def render_recent_research():
    """Render recent archived observations without changing repository behavior."""
    try:
        status = research_repository_from_env().status(study_id=DEFAULT_STUDY_PROTOCOL.study_id)
    except Exception as error:
        st.info("Recent research is unavailable: " + str(error))
        return

    if not status.recent_observations:
        st.info("No recent research observations are available yet.")
        return

    recent_rows = pd.DataFrame(status.recent_observations).rename(
        columns={
            "scan_id": "Scan Identifier",
            "scan_timestamp": "Observation Timestamp",
            "study_id": "Study Identifier",
            "scheduled_time_label": "Scheduled Time",
            "run_mode": "Run Mode",
        }
    )
    st.table(recent_rows)


def render_saved_research_universes(active_universe_path, active_universe_symbols):
    """Render every durable universe plus legacy CSV and recoverable snapshots."""
    repository = research_universe_repository_from_env()
    persisted = repository.list_all()
    orphaned = repository.list_orphaned_snapshots()
    persisted_ids = {universe.universe_id for universe in persisted}

    for universe in persisted:
        with st.container(border=True):
            st.subheader(universe.title)
            st.caption(
                f"{len(universe.approved_membership)} companies · "
                f"{universe.state.value.replace('_', ' ').title()}"
            )
            if st.button(
                "Open Research Universe", key=f"open_persisted_universe_{universe.universe_id}",
            ):
                st.session_state.current_research_universe = repository.get(universe.universe_id)
                request_navigation("Research Universe")

    for orphan in orphaned:
        with st.container(border=True):
            st.subheader(orphan.title)
            st.caption(f"{orphan.member_count} companies · Recovered analysis available")
            st.info(
                "The original editable project record was not persisted. Opening this item "
                "recovers the exact membership captured by its latest analysis snapshot."
            )
            if st.button(
                "Open Research Universe", key=f"recover_snapshot_universe_{orphan.universe_id}",
            ):
                recovered = recover_universe_from_snapshot(orphan.snapshot)
                repository.save(recovered)
                st.session_state.current_research_universe = recovered
                request_navigation("Research Universe")

    universe_rows = []
    for universe_path in sorted((ROOT / "data").glob("*.csv")):
        if universe_path.stem.casefold() == "universe_default":
            continue
        try:
            universe = load_universe(str(universe_path))
            security_count = len(universe)
        except UniverseError:
            security_count = UNAVAILABLE
        universe_id = str(uuid5(NAMESPACE_URL, f"kip-options-scanner:{universe_path.resolve()}"))
        if universe_id in persisted_ids:
            continue
        universe_rows.append(
            {
                "Research Universe": universe_path.stem.replace("_", " ").title().removesuffix(" V1"),
                "Companies": security_count,
                "Availability": "Available",
                "_path": universe_path,
                "_universe_id": universe_id,
            }
        )

    if not persisted and not orphaned and not universe_rows and not active_universe_symbols:
        st.info("Your saved and recent Research Universes will appear here.")
        return

    if universe_rows:
        for index, row in enumerate(universe_rows):
            with st.container(border=True):
                st.subheader(row["Research Universe"])
                st.caption(f"{row['Companies']} companies · {row['Availability']}")
                if st.button("Open Research Universe", key=f"open_compatibility_universe_{index}"):
                    from src.research_universe import ResearchUniverseReviewService, UniverseType
                    from src.research_universe_builder_page import _saved_records, readable_universe_title

                    universe_id = row["_universe_id"]
                    imported = ResearchUniverseReviewService().assemble(
                        universe_id=universe_id,
                        title=readable_universe_title(None, row["Research Universe"], ""),
                        starting_companies=_saved_records(row["_path"], universe_id),
                        provenance={
                            "persistence": "compatibility_csv",
                            "universe_type": UniverseType.IMPORTED,
                            "saved_research_source": str(row["_path"]),
                            "source_summary": "Compatibility CSV data",
                        },
                    )
                    repository.save(imported)
                    st.session_state.current_research_universe = imported
                    request_navigation("Research Universe")

    if active_universe_symbols:
        st.caption(
            "Current active Research Universe contains "
            + str(len(active_universe_symbols))
            + " securities."
        )


def response_field(structured_response, field_name, default=UNAVAILABLE):
    value = structured_response.get(field_name)
    if value is None or value == "":
        return default
    return value


def render_list_items(items):
    if not items:
        st.caption(UNAVAILABLE)
        return
    for item in items:
        st.write("- " + str(item))


def render_research_map(research_map):
    if not research_map:
        st.caption(UNAVAILABLE)
        return
    for map_area in research_map:
        if isinstance(map_area, dict):
            area = map_area.get("area") or map_area.get("category") or UNAVAILABLE
            subdomains = map_area.get("subdomains") or []
            st.write("- " + str(area))
            for subdomain in subdomains:
                st.caption("  - " + str(subdomain))
        else:
            st.write("- " + str(map_area))


def rce_candidate_rows(candidates):
    candidate_rows = []
    for candidate in candidates or []:
        if not isinstance(candidate, dict):
            continue
        candidate_rows.append(
            {
                "Ticker": candidate.get("ticker") or UNAVAILABLE,
                "Company": candidate.get("company_name") or UNAVAILABLE,
                "Subdomain": candidate.get("subdomain") or candidate.get("category") or UNAVAILABLE,
                "Rationale": candidate.get("inclusion_rationale") or UNAVAILABLE,
                "Confidence": candidate.get("confidence"),
                "Validation": candidate.get("entity_validation_status") or UNAVAILABLE,
            }
        )
    return candidate_rows


def rce_user_presentation(structured_response):
    presentation = structured_response.get("user_presentation") or {}
    proposed_universe = structured_response.get("proposed_research_universe") or {}
    universe_review = structured_response.get("universe_review") or {}
    return {
        "understanding": (
            presentation.get("understanding")
            or structured_response.get("primary_intent")
            or UNAVAILABLE
        ),
        "approach": (
            presentation.get("approach")
            or structured_response.get("suggested_research_mission_summary")
            or UNAVAILABLE
        ),
        "areas_included": (
            presentation.get("areas_included")
            or structured_response.get("included_areas")
            or structured_response.get("candidate_security_categories")
            or []
        ),
        "areas_excluded": (
            presentation.get("areas_excluded")
            or structured_response.get("excluded_areas")
            or []
        ),
        "companies_to_start_with": (
            presentation.get("companies_to_start_with")
            or proposed_universe.get("candidate_securities")
            or structured_response.get("candidate_securities")
            or []
        ),
        "universe_review": (
            presentation.get("universe_review")
            or universe_review.get("coverage_assessment")
            or structured_response.get("coverage_assessment")
            or []
        ),
        "assumptions": (
            presentation.get("assumptions")
            or structured_response.get("assumptions")
            or []
        ),
        "ways_to_refine": (
            presentation.get("ways_to_refine")
            or structured_response.get("ways_to_refine")
            or [
                "Narrow or broaden the company list.",
                "Change geography, asset focus, or time horizon.",
                "Add exclusions, pure-play preference, or category weights.",
            ]
        ),
    }


def rce_debug_artifacts_enabled():
    return os.getenv("RCE_DEBUG_ARTIFACTS", "").strip().lower() in {"1", "true", "yes"}


def render_rce_diagnostics(response, displayed_candidate_count):
    diagnostics = response.metadata.diagnostics()
    diagnostics["displayed_candidate_count"] = displayed_candidate_count
    entity_validation = (response.structured_response or {}).get("entity_validation") or {}
    diagnostics["entity_validation_version"] = (
        entity_validation.get("version") or UNAVAILABLE
    )
    diagnostics["entity_validation_valid_count"] = (
        entity_validation.get("valid_candidate_count") or 0
    )
    diagnostics["entity_validation_invalid_count"] = (
        entity_validation.get("invalid_candidate_count") or 0
    )
    diagnostics["entity_validation_duplicate_tickers"] = (
        ", ".join(entity_validation.get("duplicate_tickers") or []) or UNAVAILABLE
    )
    marker = (response.structured_response or {}).get("provider_verification_marker")
    diagnostics["provider_verification_marker"] = marker or UNAVAILABLE
    diagnostics["provider_error_message"] = (
        diagnostics.get("provider_error_message") or UNAVAILABLE
    )
    diagnostics["provider_error_type"] = (
        diagnostics.get("provider_error_type") or UNAVAILABLE
    )
    diagnostics["provider_http_status"] = (
        diagnostics.get("provider_http_status") or UNAVAILABLE
    )
    diagnostics["fallback_provider_name"] = (
        diagnostics.get("fallback_provider_name") or UNAVAILABLE
    )
    st.markdown("#### RCE Diagnostics")
    st.dataframe(
        pd.DataFrame(
            [
                {"Field": field_name, "Value": field_value}
                for field_name, field_value in diagnostics.items()
            ]
        ),
        hide_index=True,
        width="stretch",
    )


def render_rce_response(response):
    structured_response = response.structured_response or {}
    presentation = rce_user_presentation(structured_response)
    st.markdown("### Conversation Complete")
    st.caption("Research Ready. This is a proposed research universe, not an investment recommendation.")

    if response.metadata.fallback_used:
        st.warning("OpenAI provider failed; using mock provider.")

    if response.metadata.provider_name == "openai" and response.has_errors:
        st.warning(
            "OpenAI RCE is configured but unavailable. Set OPENAI_API_KEY to enable "
            "live research interpretation."
        )

    if response.has_errors:
        for error in response.errors:
            st.error(error)

    summary_columns = st.columns(2)
    with summary_columns[0]:
        st.markdown("#### Here's how I understand your question")
        st.write(presentation["understanding"])
        st.caption(
            "Domain: "
            + str(response_field(structured_response, "primary_domain"))
            + " | Asset focus: "
            + str(response_field(structured_response, "asset_focus"))
        )
    with summary_columns[1]:
        st.markdown("#### How we'll approach it")
        st.write(response_field(structured_response, "suggested_research_mission_title"))
        st.caption(presentation["approach"])

    st.markdown("#### Proposed Research Universe")
    st.write(response_field(structured_response, "suggested_research_universe_name"))

    if rce_debug_artifacts_enabled():
        render_rce_diagnostics(
            response,
            len(rce_candidate_rows(presentation["companies_to_start_with"])),
        )
        st.markdown("#### Research Map")
        render_research_map(structured_response.get("research_map", []))

    st.markdown("#### Areas included")
    render_list_items(presentation["areas_included"])

    st.markdown("#### Areas excluded")
    render_list_items(presentation["areas_excluded"])

    st.markdown("#### Companies to start with")
    candidate_rows = rce_candidate_rows(presentation["companies_to_start_with"])
    if candidate_rows:
        candidate_frame = pd.DataFrame(candidate_rows)
        visible_candidate_rows = candidate_frame.head(25)
        st.dataframe(
            visible_candidate_rows,
            hide_index=True,
            width="stretch",
            height=min(910, 38 + (len(visible_candidate_rows) + 1) * 35),
        )
        if len(candidate_frame) > 25:
            with st.expander(f"Show all {len(candidate_frame)} companies"):
                st.dataframe(candidate_frame, hide_index=True, width="stretch")
    else:
        st.caption("No candidate securities proposed yet.")

    universe_review = presentation["universe_review"]
    if universe_review:
        st.markdown("#### Universe review")
        render_list_items(universe_review)

    assumptions = presentation["assumptions"]
    if assumptions:
        st.markdown("#### Assumptions")
        render_list_items(assumptions)

    st.markdown("#### Ways to refine this")
    render_list_items(presentation["ways_to_refine"])

    warnings_and_limitations = (
        list(response.warnings)
        + list(structured_response.get("warnings", []))
        + list(structured_response.get("limitations", []))
    )
    if warnings_and_limitations:
        st.markdown("#### Confidence and limitations")
        render_list_items(dict.fromkeys(warnings_and_limitations))

    st.caption(
        "Provider: "
        + response.metadata.provider_name
        + " | Model: "
        + response.metadata.model_name
        + " | Prompt: "
        + response.metadata.prompt_version
    )

    action_columns = st.columns(3)
    with action_columns[0]:
        st.button(
            "Build Research Universe",
            type="primary",
            disabled=True,
            help="Research Universe building is the next workflow step; this sprint preserves session-only output.",
        )
    with action_columns[1]:
        st.button("Modify Question", on_click=modify_research_question)
    with action_columns[2]:
        st.button("Start Over", on_click=reset_research_launch)


def start_research_conversation():
    """Capture the current question and run the configured RCE provider."""
    question = st.session_state.research_question.strip()
    st.session_state.submitted_research_question = question
    provider = create_research_conversation_provider()
    service = ResearchConversationService(
        provider,
        confidence_threshold=research_conversation_confidence_threshold(),
    )
    st.session_state.research_conversation_response = service.interpret(
        question,
        context={
            "selected_research_path": st.session_state.get("selected_research_path")
        },
    )
    st.session_state.show_research_workspace_preview = True


def modify_research_question():
    """Return to the launch prompt while preserving the current question."""
    st.session_state.research_conversation_response = None
    st.session_state.show_research_workspace_preview = False


def reset_research_launch():
    """Clear the launch prompt and session-only proposal."""
    st.session_state.research_question = ""
    st.session_state.submitted_research_question = ""
    st.session_state.selected_research_path = None
    st.session_state.research_conversation_response = None
    st.session_state.show_research_workspace_preview = False


def select_research_path(path, starter_phrase):
    """Use a starter path as coaching without leaving the workspace."""
    st.session_state.research_question = starter_phrase
    st.session_state.submitted_research_question = starter_phrase
    st.session_state.selected_research_path = path
    st.session_state.research_conversation_response = None
    st.session_state.show_research_workspace_preview = True


def render_research_workspace(active_universe_path, active_universe_symbols):
    st.title("Research Workspace")

    if "research_question" not in st.session_state:
        st.session_state.research_question = ""
    if "selected_research_path" not in st.session_state:
        st.session_state.selected_research_path = None
    if "submitted_research_question" not in st.session_state:
        st.session_state.submitted_research_question = ""
    if "show_research_workspace_preview" not in st.session_state:
        st.session_state.show_research_workspace_preview = False
    if "research_conversation_response" not in st.session_state:
        st.session_state.research_conversation_response = None

    st.markdown("## Every investment begins with curiosity.")
    st.markdown("### What are we researching?")
    st.text_area(
        "Question",
        key="research_question",
        height=220,
        label_visibility="collapsed",
        placeholder=(
            "Ask about a company, theme, opportunity, comparison, or concept.\n\n"
            "Example: I would like to learn about companies that may benefit from AI infrastructure."
        ),
    )
    st.caption(
        "Ask in your own words. You do not need to know investing terminology - "
        "the platform will turn your question into a proposed research universe."
    )
    st.button(
        "Launch Research",
        type="primary",
        on_click=start_research_conversation,
    )
    if (
        os.getenv(RCE_PROVIDER_ENV, "mock").strip().lower() == "openai"
        and not os.getenv(OPENAI_API_KEY_ENV)
    ):
        st.warning(
            "OpenAI RCE is selected, but OPENAI_API_KEY is not configured. Add the "
            "key to enable live interpretation, or set RCE_PROVIDER=mock."
        )
    else:
        st.info(
            "RCE output is session-only for now. It does not save Research Universes, "
            "create snapshots, or run SAM, OD, or OAM automatically."
        )

    if st.session_state.show_research_workspace_preview:
        with st.container(border=True):
            response = st.session_state.research_conversation_response
            if response is not None:
                render_rce_response(response)
            else:
                st.markdown("### Ready to Build Research Universe")
                question = st.session_state.submitted_research_question.strip()
                if question:
                    st.write("You want to start from:")
                    st.info(question)
                st.write("Launch Research will translate the question into:")
                preview_steps = [
                    "Interpretation",
                    "Proposed Research Mission",
                    "Research Map",
                    "Included Areas",
                    "Excluded Areas",
                    "Candidate Companies",
                    "Coverage Assessment",
                    "Assumptions",
                    "Ways to Refine",
                ]
                for step in preview_steps:
                    st.write("- " + step)
                st.caption("Conversation starts the process. Evidence completes it.")

    st.markdown("### Need a little inspiration?")
    st.caption("Choose a starting point if you are not sure what to ask.")
    starter_cards = [
        {
            "title": "Explore an Investment Idea",
            "description": "Help me discover companies around a theme.",
            "examples": [
                "Show me AI infrastructure companies.",
                "I'd like to learn about robotics.",
                "What companies benefit from lower interest rates?",
            ],
            "starter": "I'd like to understand companies that may benefit from __________.",
        },
        {
            "title": "Research a Company",
            "description": "Start with one company and build from there.",
            "examples": [
                "Is Caterpillar exposed to data center growth?",
                "Should I research GE Vernova?",
                "What makes Vertiv interesting?",
            ],
            "starter": (
                "I'd like to understand whether __________ is worth researching "
                "because __________."
            ),
        },
        {
            "title": "Find Investment Opportunities",
            "description": "I already know what I'm looking at.",
            "examples": [
                "Find attractive call options for Micron.",
                "Which names in my watchlist look strongest?",
                "Show me earnings opportunities.",
            ],
            "starter": (
                "I already know I'm interested in __________. "
                "Help me find attractive opportunities."
            ),
        },
        {
            "title": "Compare & Learn",
            "description": "Help me understand what I'm seeing.",
            "examples": [
                "Why wasn't Generac included?",
                "Compare AI and robotics.",
                "Explain why this stock ranked highly.",
            ],
            "starter": "I want to understand __________ and compare it with __________.",
        },
    ]
    for start in range(0, len(starter_cards), 2):
        for column, card in zip(st.columns(2), starter_cards[start : start + 2]):
            with column:
                with st.container(border=True):
                    st.markdown("#### " + card["title"])
                    st.caption(card["description"])
                    st.write("Example questions:")
                    for example in card["examples"]:
                        st.caption("- " + example)
                    st.button(
                        "Use this path",
                        key=f"research_start_{card['title']}",
                        on_click=select_research_path,
                        args=(card["title"], card["starter"]),
                    )

    if st.session_state.selected_research_path:
        st.info(
            "Selected starting point: "
            + st.session_state.selected_research_path
            + "."
        )

    st.markdown("### Continue Previous Research")
    saved_tab, observations_tab = st.tabs(["Research Universes", "Recent Observations"])
    with saved_tab:
        render_saved_research_universes(active_universe_path, active_universe_symbols)
    with observations_tab:
        render_recent_research()

    st.markdown("### Already know where you want to go?")
    advanced_columns = st.columns(3)
    advanced_targets = [
        (
            "Security Research",
            "Open Security Research",
            "Go to stock-level research.",
        ),
        (
            "Opportunity Research",
            "Open Opportunity Research",
            "Go to opportunity research.",
        ),
        (
            "Research Repository",
            "View Research Repository",
            "Review saved research history.",
        ),
    ]
    for column, (page, button_label, description) in zip(advanced_columns, advanced_targets):
        with column:
            st.markdown("#### " + page)
            st.caption(description)
            if st.button(button_label, key=f"open_{page}"):
                request_navigation(page)


def render_research_repository_page():
    st.title("History")
    st.caption("Archived research observations available through the current repository.")
    render_recent_research()


def render_home(active_universe_path, active_universe_symbols):
    """Render the product landing page without starting analytical work."""
    st.title("Home")
    st.markdown("## What would you like to research?")
    st.write("Start with an idea. We'll build a Research Universe, refine it together, and then analyze it.")
    st.space("small")

    market_column, company_column = st.columns(2, gap="large")
    with market_column:
        with st.container(border=True, height="stretch"):
            st.subheader("Build a Research Universe")
            st.write(
                "Research an industry, technology, investment theme, market segment, "
                "or competitive landscape."
            )
            st.space("small")
            if st.button(
                "Start Research",
                type="primary",
                width="stretch",
                key="home_launch_market_research",
            ):
                start_new_research()
    with company_column:
        with st.container(border=True, height="stretch"):
            st.subheader("Company")
            st.write("Analyze an individual publicly traded company.")
            st.space("small")
            if st.button(
                "Analyze Company",
                width="stretch",
                key="home_analyze_company",
            ):
                request_navigation("Company Analysis")

    st.space("medium")
    st.header("Continue Research")
    st.caption("Research Universes are living projects you can return to as your work develops.")
    current_universe = st.session_state.get("current_research_universe")
    if current_universe:
        research_universe_repository_from_env().save(current_universe)
    render_saved_research_universes(active_universe_path, active_universe_symbols)


def actual_time_label(scan_timestamp):
    if not scan_timestamp:
        return UNAVAILABLE
    parts = str(scan_timestamp).split()
    if len(parts) >= 4:
        return f"{parts[1]} {parts[2]} {parts[3]}"
    return scan_timestamp


def schedule_time_display(scheduled_time_label):
    if not scheduled_time_label:
        return UNAVAILABLE
    label = str(scheduled_time_label)
    return label if label.endswith(" ET") else f"{label} ET"


def render_quality_score_bucket_table(rows):
    """Render quality-score buckets alongside the existing distribution chart."""
    st.dataframe(
        pd.DataFrame(rows)
        .reindex(columns=["Score Bucket", "Contracts"])
        .style.format({"Contracts": format_whole_number}),
        hide_index=True,
        width="stretch",
    )


def most_common_failing_rule(failure_rows):
    """Return the most common failing rule label from existing failure rows."""
    highest_failure_count = max(
        (row["Failure Count"] for row in failure_rows),
        default=0,
    )
    if not highest_failure_count:
        return None
    rules = [
        row["Rule"] for row in failure_rows if row["Failure Count"] == highest_failure_count
    ]
    return ", ".join(rules)


def render_population_profile(label, metrics):
    """Render one population profile card using existing diagnostic fields."""
    with st.container(border=True):
        st.markdown(label)
        render_metric_grid(metrics, columns_per_row=2)


def population_profile_metrics(rows):
    """Return the profile fields required by the diagnostics population view."""
    summary = distribution_population_summary(rows)
    fingerprint = contract_fingerprint(rows)
    return {
        "Population Count": summary["Population Count"],
        "Average Quality Score": summary["Average Quality Score"],
        "Average DTE": fingerprint["Average DTE"],
        "Average Delta": summary["Average Delta"],
        "Average Spread %": summary["Average Spread %"],
        "Average Volume": summary["Average Volume"],
        "Average Open Interest": summary["Average Open Interest"],
        "Average Strike Distance %": fingerprint["Average Strike Distance %"],
    }


def render_quality_diagnostics_overview(evaluated_rows, opportunity_rows, metadata):
    st.caption("Question: What happened in this scan?")
    if metadata:
        st.markdown("Dashboard Metadata")
        render_dashboard_metadata(metadata)

    render_metric_grid(diagnostic_overview_metrics(evaluated_rows))

    st.markdown("Status Distribution")
    render_bar_chart(status_distribution(evaluated_rows), "Status", "Contracts")

    st.markdown("Observations")
    render_dashboard_observations(
        dashboard_observations(evaluated_rows, opportunity_rows)
    )


def render_quality_score_diagnostics(evaluated_rows):
    st.caption("Question: Is the scoring model producing a useful spread of scores?")
    score_distribution_rows = quality_score_distribution(evaluated_rows)
    st.markdown("Quality Score Distribution")
    render_bar_chart(score_distribution_rows, "Score Bucket", "Contracts")

    st.markdown("Quality Score Bucket Table")
    render_quality_score_bucket_table(score_distribution_rows)

    summary = discovery_diagnostic_summary(evaluated_rows)
    render_metric_grid(
        {
            "Average Quality Score": summary["Average Quality Score"],
            "Median Quality Score": summary["Median Quality Score"],
            "Highest Quality Score": summary["Highest Quality Score"],
            "Lowest Quality Score": summary["Lowest Quality Score"],
        }
    )


def render_rule_failure_diagnostics(evaluated_rows):
    st.caption("Question: Which rules are eliminating contracts?")
    failure_rows = rule_failure_distribution(evaluated_rows)

    st.markdown("Rule Failure Distribution")
    render_rule_failure_distribution(evaluated_rows)

    st.markdown("Average Rule Contribution")
    render_bar_chart(
        average_rule_contribution(evaluated_rows),
        "Rule",
        "Average Points",
    )

    common_rule = most_common_failing_rule(failure_rows)
    if common_rule:
        st.metric("Most Common Failing Rule", common_rule)


def render_population_profile_diagnostics(evaluated_rows, opportunity_rows):
    st.caption("Question: What does each evaluated population look like?")
    population_specs = (
        (
            "Passing Population",
            distribution_population(evaluated_rows, PASSING_CONTRACTS_POPULATION),
        ),
        (
            "True Near Miss Population",
            distribution_population(evaluated_rows, TRUE_NEAR_MISS_CONTRACTS_POPULATION),
        ),
        (
            "Rejected Population",
            distribution_population(evaluated_rows, REJECTED_CONTRACTS_POPULATION),
        ),
        (
            "Top Opportunity Population",
            sort_by_quality_score_desc(
                [
                    row
                    for row in opportunity_rows
                    if row.get("Status") in {"Passing", "True Near Miss"}
                    and row.get("Quality Score") not in (None, "")
                ]
            )[:10],
        ),
    )

    for left_spec, right_spec in zip(population_specs[::2], population_specs[1::2]):
        left_column, right_column = st.columns(2)
        with left_column:
            render_population_profile(
                left_spec[0],
                population_profile_metrics(left_spec[1]),
            )
        with right_column:
            render_population_profile(
                right_spec[0],
                population_profile_metrics(right_spec[1]),
            )


def render_quality_engine_diagnostics(
    evaluated_rows,
    opportunity_rows,
    metadata=None,
):
    """Render one-run diagnostics for current Opportunity Discovery results."""
    if not evaluated_rows:
        st.info("No evaluated contracts are available for the current Opportunity Discovery run.")
        return

    st.caption(
        "Diagnostics use only contracts evaluated by the current Opportunity Discovery filters."
    )
    (
        overview_tab,
        score_distribution_tab,
        rule_failures_tab,
        population_profiles_tab,
        distribution_diagnostics_tab,
    ) = st.tabs(
        [
            "Overview",
            "Score Distribution",
            "Rule Failures",
            "Population Profiles",
            "Distribution Diagnostics",
        ]
    )

    with overview_tab:
        render_quality_diagnostics_overview(
            evaluated_rows,
            opportunity_rows,
            metadata,
        )
    with score_distribution_tab:
        render_quality_score_diagnostics(evaluated_rows)
    with rule_failures_tab:
        render_rule_failure_diagnostics(evaluated_rows)
    with population_profiles_tab:
        render_population_profile_diagnostics(evaluated_rows, opportunity_rows)
    with distribution_diagnostics_tab:
        st.caption(
            "Question: Where do contracts sit relative to each rule threshold?"
        )
        render_distribution_diagnostics(evaluated_rows)


def raw_option_contracts(payload):
    """Return option contracts without changing Tradier's response fields."""
    options = payload.get("options", {})
    if not isinstance(options, dict):
        return []
    return as_list(options.get("option"))


def quote_last_price(payload):
    """Extract the selected underlying's last price from a Tradier quote response."""
    quotes = payload.get("quotes", {})
    quote = quotes.get("quote") if isinstance(quotes, dict) else None
    if isinstance(quote, list):
        quote = quote[0] if quote else None
    return quote.get("last") if isinstance(quote, dict) else None


def render_tradier_quote(ticker, get_quote, show_diagnostic_data):
    st.subheader("Tradier quote")
    if not get_quote:
        return

    if not ticker:
        st.error("Enter a ticker symbol before requesting a quote.")
        return

    try:
        raw_response = TradierClient().get_quote(ticker)
        quote = raw_response.get("quotes", {}).get("quote")
        if isinstance(quote, list):
            quote = quote[0] if quote else None
        if not isinstance(quote, dict):
            raise ValueError("Unexpected quote response format.")
    except TradierConfigurationError as error:
        st.error("Tradier configuration error: " + str(error))
    except TradierAPIError as error:
        st.error("Tradier connection error: " + str(error))
    except ValueError as error:
        st.error("Tradier response error: " + str(error))
    else:
        quote_metrics = (
            ("Symbol", quote.get("symbol", UNAVAILABLE)),
            ("Last Trade", quote.get("last", UNAVAILABLE)),
            ("Bid", quote.get("bid", UNAVAILABLE)),
            ("Ask", quote.get("ask", UNAVAILABLE)),
            ("Mid Price", mid_price(quote)),
            ("Volume", format_whole_number(quote.get("volume", UNAVAILABLE))),
        )
        for column, (label, value) in zip(st.columns(6), quote_metrics):
            column.metric(label, value)

        trade_timestamp = format_eastern_timestamp(quote.get("trade_date"))
        bid_timestamp = format_eastern_timestamp(quote.get("bid_date"))
        ask_timestamp = format_eastern_timestamp(quote.get("ask_date"))
        timestamp_columns = st.columns(2)
        timestamp_columns[0].caption("Trade timestamp: " + trade_timestamp)
        timestamp_columns[1].caption(
            "Bid/ask timestamp: Bid " + bid_timestamp + " | Ask " + ask_timestamp
        )
        st.caption("Bid/ask may update more frequently than last trade price.")
        if show_diagnostic_data:
            with st.expander("Tradier Raw Response"):
                st.json(raw_response)


def render_opportunity_discovery_workflow(
    universe_name,
    universe_path,
    universe_symbols,
    universe_error=None,
    reload_universe=False,
):
    st.subheader("Opportunity Discovery")
    st.caption(
        "Ranks the best passing contract, or highest-quality true near miss, for each watchlist ticker."
    )
    universe_source = str(Path(universe_path).expanduser())
    if (
        reload_universe
        or st.session_state.get("opportunity_universe_source") != universe_source
    ):
        st.session_state.opportunity_watchlist_input = "\n".join(universe_symbols)
        st.session_state.opportunity_universe_source = universe_source

    if universe_error:
        st.error("Opportunity Discovery unavailable: " + str(universe_error))

    watchlist_input = st.text_area(
        "Watchlist",
        height=180,
        key="opportunity_watchlist_input",
        disabled=bool(universe_error),
        help="Loaded from the currently selected Universe CSV. Use Reload Universe CSV after changing the file.",
    )
    discovery_symbols = parse_universe_symbols(watchlist_input)
    discovery_filter_columns = st.columns(3)
    selected_discovery_option_type = discovery_filter_columns[0].selectbox(
        "Option Type",
        options=list(OPTION_TYPE_FILTERS),
        index=0,
        key="opportunity_option_type",
    )
    min_discovery_dte = discovery_filter_columns[1].number_input(
        "Minimum DTE",
        min_value=0,
        value=DEFAULT_DISCOVERY_MIN_DTE,
        step=1,
        key="opportunity_min_dte",
    )
    max_discovery_dte = discovery_filter_columns[2].number_input(
        "Maximum DTE",
        min_value=0,
        value=DEFAULT_DISCOVERY_MAX_DTE,
        step=1,
        key="opportunity_max_dte",
    )
    min_discovery_dte = int(min_discovery_dte)
    max_discovery_dte = int(max_discovery_dte)
    discovery_settings = (
        selected_discovery_option_type,
        min_discovery_dte,
        max_discovery_dte,
    )
    invalid_discovery_dte = min_discovery_dte > max_discovery_dte
    if invalid_discovery_dte:
        st.error("Minimum DTE must be less than or equal to Maximum DTE.")
    run_discovery = st.button(
        "Run Opportunity Discovery",
        disabled=bool(universe_error) or not discovery_symbols or invalid_discovery_dte,
    )

    if run_discovery:
        try:
            (
                opportunity_rows,
                discovery_errors,
                discovery_evaluated_rows,
            ) = discover_universe_opportunities(
                TradierClient(),
                discovery_symbols,
                datetime.now(EASTERN_TIME).date(),
                option_type=selected_discovery_option_type,
                min_dte=min_discovery_dte,
                max_dte=max_discovery_dte,
            )
        except TradierConfigurationError as error:
            st.error("Tradier configuration error: " + str(error))
        else:
            scan_timestamp = datetime.now(EASTERN_TIME)
            scan_id = f"opportunity-scan-{scan_timestamp:%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
            formatted_scan_timestamp = scan_timestamp.strftime(
                "%Y-%m-%d %I:%M:%S %p %Z"
            )
            st.session_state.opportunity_rows = opportunity_rows
            st.session_state.opportunity_errors = discovery_errors
            st.session_state.opportunity_evaluated_rows = discovery_evaluated_rows
            st.session_state.opportunity_watchlist = discovery_symbols
            st.session_state.opportunity_settings = discovery_settings
            st.session_state.opportunity_scan_id = scan_id
            st.session_state.opportunity_scan_timestamp = formatted_scan_timestamp
            st.session_state.opportunity_universe_name = universe_name
            try:
                archive_counts = archive_current_opportunity_scan(
                    discovery_evaluated_rows,
                    scan_id,
                    formatted_scan_timestamp,
                    universe_name,
                    selected_discovery_option_type,
                    min_discovery_dte,
                    max_discovery_dte,
                    discovery_symbols,
                    DEFAULT_STUDY_PROTOCOL.metadata(run_mode=RUN_MODE_MANUAL_UI),
                )
            except Exception as error:
                st.session_state.opportunity_archive_counts = None
                st.session_state.opportunity_archive_error = str(error)
            else:
                st.session_state.opportunity_archive_counts = archive_counts
                st.session_state.opportunity_archive_error = None
                st.session_state.opportunity_archived_scan_id = scan_id

    opportunity_rows = st.session_state.get("opportunity_rows", [])
    opportunity_evaluated_rows = st.session_state.get("opportunity_evaluated_rows", [])
    opportunity_watchlist = st.session_state.get("opportunity_watchlist", [])
    opportunity_settings = st.session_state.get("opportunity_settings")
    opportunity_scan_timestamp = st.session_state.get("opportunity_scan_timestamp")
    current_opportunity_context = (
        opportunity_watchlist == discovery_symbols
        and opportunity_settings == discovery_settings
    )
    if opportunity_rows and current_opportunity_context:
        opportunity_selection = st.dataframe(
            format_opportunity_table(opportunity_rows),
            hide_index=True,
            width="stretch",
            on_select="rerun",
            selection_mode="single-row",
            key="opportunity_table",
        )
        selected_opportunity_row = selected_dataframe_row(
            opportunity_selection, opportunity_rows
        )
        if selected_opportunity_row and selected_opportunity_row.get("Status") in {
            NO_CANDIDATE,
            NO_MATCHING_CONTRACTS,
        }:
            st.info("No contract detail is available for this ticker status.")
        else:
            render_contract_detail_summary(
                selected_opportunity_row,
                "Opportunity Discovery",
            )
    elif opportunity_watchlist and current_opportunity_context:
        st.info("No passing or true near-miss contracts were found for this watchlist.")

    discovery_errors = st.session_state.get("opportunity_errors", {})
    if discovery_errors and current_opportunity_context:
        with st.expander("Watchlist Fetch Errors", expanded=False):
            for symbol, message in discovery_errors.items():
                st.caption(f"{symbol}: {message}")


def render_option_chain_explorer_workflow():
    st.subheader("Option Chain Explorer")
    st.caption("Inspect Tradier option-chain data before scanner logic is introduced.")
    explorer_ticker = st.text_input(
        "Ticker symbol", value="SPY", max_chars=10, key="option_chain_ticker"
    ).strip().upper()
    retrieve_expirations = st.button("Retrieve Expirations")

    if retrieve_expirations:
        if not explorer_ticker:
            st.error("Enter a ticker symbol before retrieving expirations.")
        else:
            try:
                raw_expirations = TradierClient().get_option_expirations(explorer_ticker)
                dates = expiration_dates(raw_expirations)
                if not dates:
                    raise ValueError("No option expirations were returned for this ticker.")
            except TradierConfigurationError as error:
                st.error("Tradier configuration error: " + str(error))
            except TradierAPIError as error:
                st.error("Tradier connection error: " + str(error))
            except ValueError as error:
                st.error("Tradier response error: " + str(error))
            else:
                st.session_state.option_chain_expirations = dates
                st.session_state.option_chain_expirations_ticker = explorer_ticker

    dates = st.session_state.get("option_chain_expirations", [])
    dates_ticker = st.session_state.get("option_chain_expirations_ticker")
    if dates and dates_ticker == explorer_ticker:
        expiration = st.selectbox("Expiration", options=dates, key="option_chain_expiration")
        retrieve_chain = st.button("Retrieve Option Chain")
        if retrieve_chain:
            try:
                raw_chain = TradierClient().get_option_chain(explorer_ticker, expiration)
                try:
                    underlying_price = quote_last_price(TradierClient().get_quote(explorer_ticker))
                except (TradierConfigurationError, TradierAPIError):
                    underlying_price = None
                rows = option_chain_rows(
                    raw_chain,
                    expiration=expiration,
                    today=datetime.now(EASTERN_TIME).date(),
                    underlying_price=underlying_price,
                    ticker=explorer_ticker,
                )
                if not rows:
                    raise ValueError("No options were returned for this expiration.")
            except TradierConfigurationError as error:
                st.error("Tradier configuration error: " + str(error))
            except TradierAPIError as error:
                st.error("Tradier connection error: " + str(error))
            except ValueError as error:
                st.error("Tradier response error: " + str(error))
            else:
                st.session_state.option_chain_response = raw_chain
                st.session_state.option_chain_rows = rows
                st.session_state.option_chain_response_ticker = explorer_ticker
                st.session_state.option_chain_response_expiration = expiration

        chain_rows = st.session_state.get("option_chain_rows")
        chain_ticker = st.session_state.get("option_chain_response_ticker")
        chain_expiration = st.session_state.get("option_chain_response_expiration")
        if chain_rows and chain_ticker == explorer_ticker and chain_expiration == expiration:
            if st.session_state.get("diagnostic_option_type") not in OPTION_TYPE_FILTERS:
                st.session_state.diagnostic_option_type = "Calls"
            selected_option_type = st.selectbox(
                "Option Type",
                options=list(OPTION_TYPE_FILTERS),
                index=0,
                key="diagnostic_option_type",
            )
            filtered_chain_rows = filter_by_option_type(
                chain_rows, selected_option_type
            )

            st.subheader("Opportunity Analysis")
            st.caption(
                "Ticker-level summary of current option-analysis outcomes and closest rule-margin shortfalls."
            )
            opportunities = opportunity_analysis(filtered_chain_rows)
            for column, label in zip(
                st.columns(3),
                ("Contracts Evaluated", "Passing Contracts Count", "True Near Miss Count"),
            ):
                column.metric(label, opportunities[label])

            if opportunities["Passing Contracts Count"] == 0:
                near_miss_count = opportunities["True Near Miss Count"]
                if near_miss_count:
                    st.info(
                        f"No contracts passed all tests. {near_miss_count} true near-miss "
                        "candidate(s) remain available for review."
                    )
                else:
                    st.info(
                        "No contracts passed all tests, and no true near-miss candidates are available."
                    )

            margin, contract = opportunity_candidate_display(
                opportunities["Closest Near Miss"]
            )
            closest_column, score_column, strength_column = st.columns(3)
            closest_column.metric("Closest Near Miss", margin)
            closest_column.caption(contract)
            score_column.metric(
                "Quality Score", quality_score_display(opportunities["Closest Near Miss"])
            )
            strength_column.metric("Primary Strength", opportunities["Primary Strength"])

            st.subheader("Passing Contracts")
            passing_rows = sort_by_quality_score_desc(
                passing_contracts(filtered_chain_rows)
            )
            if passing_rows:
                render_selectable_drilldown(
                    passing_rows,
                    drilldown_contract_columns(),
                    "Passing Contract",
                    "passing_contract_table",
                )
            else:
                st.info("No contracts in this chain passed all quality tests.")

            st.subheader("True Near Miss Contracts")
            near_miss_rows = sort_by_quality_score_desc(
                near_miss_contracts(filtered_chain_rows)
            )
            near_miss_display_rows = []
            for row in near_miss_rows:
                failed_test = failure_label(row)
                near_miss_display_rows.append(
                    {
                        **row,
                        "Failed Test": failed_test,
                        "Relevant Rule Detail": rule_detail_for_display(failed_test, row),
                    }
                )
            if near_miss_display_rows:
                render_selectable_drilldown(
                    near_miss_display_rows,
                    drilldown_contract_columns(include_failure=True),
                    "True Near Miss",
                    "true_near_miss_contract_table",
                )
            else:
                st.info("No contracts failed exactly one quality test.")

            with st.expander("Advanced Diagnostics", expanded=False):
                st.caption(
                    f"Threshold-analysis diagnostics for {chain_ticker} expiring {chain_expiration}."
                )
                # OCE diagnostics must use the same filtered population as the visible chain analysis.
                diagnostics = ticker_diagnostics(filtered_chain_rows)
                assert (
                    opportunities["Contracts Evaluated"] == diagnostics["Contracts Evaluated"]
                )
                diagnostic_counts = list(diagnostics.items())[:6]
                st.subheader("Ticker Diagnostics")
                for column, (label, value) in zip(st.columns(3), diagnostic_counts[:3]):
                    column.metric(label, value)
                for column, (label, value) in zip(st.columns(3), diagnostic_counts[3:]):
                    column.metric(label, value)
                weakness_column, strength_column = st.columns(2)
                weakness_column.metric("Primary Weakness", diagnostics["Primary Weakness"])
                strength_column.metric("Primary Strength", diagnostics["Primary Strength"])

                selected_test = st.selectbox(
                    "Near Miss Test",
                    options=[ANY_SINGLE_FAILED_TEST, *TEST_SPECIFIC_NEAR_MISS_OPTIONS],
                    key="near_miss_test",
                )

                st.subheader("Test-Specific Near Miss Contracts")
                selected_near_misses = []
                if selected_test == ANY_SINGLE_FAILED_TEST:
                    st.info("Select a specific near-miss test to view all contracts failing that test.")
                else:
                    selected_near_misses = test_specific_near_misses(
                        filtered_chain_rows, selected_test
                    )
                    selected_display_rows = [
                        {
                            **row,
                            "Failed Test": selected_test,
                            "Relevant Rule Detail": rule_detail_for_display(selected_test, row),
                            "Margin from Passing": margin_from_passing(selected_test, row),
                        }
                        for row in selected_near_misses
                    ]
                    if selected_display_rows:
                        st.caption("Contracts are ordered from the smallest shortfall to the largest.")
                        render_selectable_drilldown(
                            selected_display_rows,
                            drilldown_contract_columns(include_failure=True)
                            + ["Margin from Passing"],
                            "Test-Specific Near Miss",
                            "test_specific_near_miss_contract_table",
                        )
                    else:
                        st.info(
                            f"No {selected_option_type.lower()} contracts failed the "
                            f"{selected_test.lower()} test."
                        )

                st.subheader("Test-Specific Opportunity Analysis")
                candidate_labels = (
                    ("Closest Spread Near Miss", "Spread"),
                    ("Closest Delta Near Miss", "Delta"),
                    ("Closest Open Interest Near Miss", "Open Interest"),
                    ("Closest Volume Near Miss", "Volume"),
                )
                for start in range(0, len(candidate_labels), 2):
                    for column, (label, candidate_test) in zip(
                        st.columns(2), candidate_labels[start : start + 2]
                    ):
                        margin, contract = opportunity_candidate_display(
                            opportunities[label], candidate_test
                        )
                        column.metric(label, margin)
                        column.caption(
                            f"{contract} — Quality Score: "
                            f"{quality_score_display(opportunities[label])}"
                        )

                st.subheader("Contract Quality Summary")
                summary = contract_quality_summary(filtered_chain_rows)
                for column, (label, value) in zip(st.columns(6), summary.items()):
                    column.metric(label, value)
                chain_dataframe = pd.DataFrame(filtered_chain_rows).style.format(
                    {
                        "Strike": format_decimal,
                        "Quality Score": "{:,.0f}",
                        "Bid": format_decimal,
                        "Ask": format_decimal,
                        "Mid Price": format_decimal,
                        "Spread": format_decimal,
                        "Delta": format_decimal,
                        "Spread %": format_percent,
                        "Strike Distance %": format_percent,
                        "Implied Volatility": format_percent,
                        "IV": format_percent,
                        "Volume": "{:,.0f}",
                        "Open Interest": "{:,.0f}",
                        "Spread Margin": lambda value: format_percentage_distance(
                            value, MAX_SPREAD_PERCENT
                        ),
                        "OI Margin": "{:,.0f}",
                        "Volume Margin": "{:,.0f}",
                    }
                ).map(style_all_passed, subset=["All Passed"])
                st.dataframe(chain_dataframe, hide_index=True, width="stretch")
                if st.checkbox("Show Diagnostic Data", key="option_chain_diagnostics"):
                    st.caption("First 5 raw option contracts returned by Tradier")
                    st.dataframe(
                        pd.DataFrame(raw_option_contracts(st.session_state.option_chain_response)[:5]),
                        hide_index=True,
                        width="stretch",
                    )
                    with st.expander("Tradier Raw Option-Chain Response"):
                        st.json(st.session_state.option_chain_response)
    elif dates and dates_ticker:
        st.info("Retrieve expirations for " + explorer_ticker + " to select an expiration.")


def render_quality_engine_diagnostics_workflow():
    st.subheader("Option Analysis Explorer")
    st.caption("How did the Option Analysis Model behave during the most recent scan?")

    opportunity_scan_id = st.session_state.get("opportunity_scan_id")
    opportunity_watchlist = st.session_state.get("opportunity_watchlist", [])
    if not opportunity_scan_id:
        st.info("No Opportunity Scan is available. Run Opportunity Discovery first.")
        return

    opportunity_rows = st.session_state.get("opportunity_rows", [])
    opportunity_evaluated_rows = st.session_state.get("opportunity_evaluated_rows", [])
    opportunity_settings = st.session_state.get("opportunity_settings")
    opportunity_scan_timestamp = st.session_state.get("opportunity_scan_timestamp")
    opportunity_universe_name = st.session_state.get("opportunity_universe_name", UNAVAILABLE)
    selected_option_type, min_dte, max_dte = opportunity_settings or (
        UNAVAILABLE,
        UNAVAILABLE,
        UNAVAILABLE,
    )
    render_quality_export_section(
        opportunity_evaluated_rows,
        opportunity_rows,
        opportunity_scan_id,
        opportunity_scan_timestamp,
        opportunity_universe_name,
        opportunity_watchlist,
    )
    render_quality_engine_diagnostics(
        opportunity_evaluated_rows,
        opportunity_rows,
        dashboard_metadata(
            opportunity_evaluated_rows,
            opportunity_watchlist,
            selected_option_type,
            min_dte,
            max_dte,
            opportunity_scan_timestamp,
        ),
    )


TAM_DISPLAY_COLUMNS = [
    "ticker",
    "technical_timestamp",
    "price",
    "sma_20",
    "sma_50",
    "sma_200",
    "price_vs_sma_20",
    "price_vs_sma_20_state",
    "price_vs_sma_50",
    "price_vs_sma_50_state",
    "price_vs_sma_200",
    "price_vs_sma_200_state",
    "sma_20_vs_sma_50",
    "sma_20_50_state",
    "sma_50_vs_sma_200",
    "sma_50_200_state",
    "rsi_14",
    "rsi_regime",
    "macd_line",
    "macd_signal",
    "macd_histogram",
    "macd_state",
    "trend_state",
    "momentum_state",
    "volatility_state",
    "technical_setup_score_experimental",
    "technical_setup_grade_experimental",
    "technical_score",
    "technical_notes",
]
TAM_REQUIRED_INDICATOR_COLUMNS = [
    "price",
    "sma_20",
    "sma_50",
    "sma_200",
    "rsi_14",
    "macd_line",
    "macd_signal",
    "macd_histogram",
    "trend_state",
    "momentum_state",
    "volatility_state",
]
TAM_PRIMARY_COLUMNS = [
    "ticker", "price", "price_vs_sma_20", "price_vs_sma_50", "price_vs_sma_200",
    "rsi_14", "macd_histogram", "trend_state", "momentum_state", "volatility_state",
    "technical_setup_grade_experimental", "technical_setup_score_experimental",
]
TAM_BADGE_LABELS = {
    "above": "[Above]",
    "below": "[Below]",
    "near": "[Near]",
    "bullish": "[Bullish]",
    "bearish": "[Bearish]",
    "neutral": "[Neutral]",
    "oversold": "[Oversold]",
    "elevated": "[Elevated]",
    "overbought": "[Overbought]",
    "unavailable": "[Unavailable]",
}


def tam_state_count(rows, state_column, state_text):
    return sum(
        state_text in str(row.get(state_column) or "").strip().lower() for row in rows
    )


def tam_average_rsi(rows):
    values = [
        float(row["rsi_14"])
        for row in rows
        if row.get("rsi_14") not in (None, "")
    ]
    return sum(values) / len(values) if values else None


def tam_average_setup_score(rows):
    values = [
        float(row["technical_setup_score_experimental"])
        for row in rows
        if row.get("technical_setup_score_experimental") not in (None, "")
    ]
    return sum(values) / len(values) if values else None


def tam_error_count(rows):
    return sum("error" in str(row.get("technical_notes") or "").lower() for row in rows)


def tam_summary_metrics(rows, latest_timestamp):
    bullish_count = tam_state_count(rows, "trend_state", "bullish")
    bearish_count = tam_state_count(rows, "trend_state", "bearish")
    setup_scores = [
        float(row["technical_setup_score_experimental"])
        for row in rows
        if row.get("technical_setup_score_experimental") not in (None, "")
    ]
    return {
        "Latest Security Scan Timestamp": latest_timestamp or UNAVAILABLE,
        "Tickers Characterized": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "Average SAM Score (Experimental)": tam_average_setup_score(rows),
        "Highest SAM Score": max(setup_scores) if setup_scores else None,
        "Lowest SAM Score": min(setup_scores) if setup_scores else None,
        "Strong Count": sum(
            row.get("technical_setup_grade_experimental") == "Strong technical setup"
            for row in rows
        ),
        "Constructive Count": sum(
            row.get("technical_setup_grade_experimental") == "Constructive"
            for row in rows
        ),
        "Weak/Poor Count": sum(
            row.get("technical_setup_grade_experimental") in {"Weak", "Poor"}
            for row in rows
        ),
        "Bullish MACD Count": sum(row.get("macd_state_raw") == "bullish" for row in rows),
        "Price Above 200 SMA Count": sum(
            row.get("price_vs_sma_200_state_raw") == "above" for row in rows
        ),
        "Bullish Trend Count": bullish_count,
        "Bearish Trend Count": bearish_count,
        "Neutral/Mixed Count": max(len(rows) - bullish_count - bearish_count, 0),
        "Average RSI": tam_average_rsi(rows),
        "SAM Error Count": tam_error_count(rows),
    }


def tam_badge(value):
    key = str(value or "unavailable").strip().lower()
    return TAM_BADGE_LABELS.get(key, f"[{key.replace('_', ' ').title()}]")


def tam_signed_percent(value):
    if value in (None, ""):
        return UNAVAILABLE
    number = float(value)
    symbol = "▲" if number > 0.01 else "▼" if number < -0.01 else "●"
    return f"{symbol} {number:.2%}"


def tam_numeric_color(value):
    if value in (None, ""):
        return ""
    number = float(value)
    return "color: #137333" if number > 0.01 else "color: #b3261e" if number < -0.01 else "color: #7a5d00"


def tam_state_color(value):
    label = str(value or "").casefold()
    if any(token in label for token in ("bullish", "positive", "constructive")):
        return "color: #137333"
    if any(token in label for token in ("bearish", "negative", "deteriorating")):
        return "color: #b3261e"
    return "color: #7a5d00"


def tam_display_row(row):
    enriched = dict(row)
    derived_fields = derived_technical_display_fields(enriched)
    for key, value in derived_fields.items():
        enriched[f"{key}_raw"] = value
        enriched[key] = tam_badge(value)
    enriched["macd_state_raw"] = derived_fields["macd_state"]
    enriched["price_vs_sma_200_state_raw"] = derived_fields["price_vs_sma_200_state"]
    setup_score = technical_setup_score(enriched)
    enriched["technical_setup_score_experimental"] = setup_score
    enriched["technical_setup_grade_experimental"] = technical_setup_grade(setup_score)
    return enriched


def tam_count_rows(rows, column_name):
    counts = {}
    for row in rows:
        label = row.get(column_name) or "NULL"
        counts[label] = counts.get(label, 0) + 1
    return [
        {"State": label, "Count": count}
        for label, count in sorted(counts.items(), key=lambda item: str(item[0]))
    ]


def tam_rsi_distribution(rows):
    buckets = {
        "Below 30": 0,
        "30-45": 0,
        "45-55": 0,
        "55-70": 0,
        "Above 70": 0,
        "NULL": 0,
    }
    for row in rows:
        value = row.get("rsi_14")
        if value in (None, ""):
            buckets["NULL"] += 1
            continue
        try:
            rsi = float(value)
        except (TypeError, ValueError):
            buckets["NULL"] += 1
            continue
        if rsi < 30:
            buckets["Below 30"] += 1
        elif rsi < 45:
            buckets["30-45"] += 1
        elif rsi <= 55:
            buckets["45-55"] += 1
        elif rsi <= 70:
            buckets["55-70"] += 1
        else:
            buckets["Above 70"] += 1
    return [{"Bucket": bucket, "Count": count} for bucket, count in buckets.items()]


def tam_missing_indicator_rows(rows):
    missing_rows = []
    for row in rows:
        missing = [
            column
            for column in TAM_REQUIRED_INDICATOR_COLUMNS
            if row.get(column) in (None, "")
        ]
        if missing:
            missing_rows.append(
                {
                    "scan_id": row.get("scan_id"),
                    "ticker": row.get("ticker"),
                    "technical_timestamp": row.get("technical_timestamp"),
                    "missing_indicators": ", ".join(missing),
                }
            )
    return missing_rows


def render_tam_count_chart(rows, label_column="State"):
    if rows:
        st.bar_chart(pd.DataFrame(rows).set_index(label_column), y="Count")
    else:
        st.info("No rows are available for this view.")


def render_legacy_technical_analysis_explorer_workflow():
    handoff = st.session_state.get("active_universe_analysis_handoff")
    active_run = st.session_state.get("active_universe_analysis_run")
    st.title(handoff.universe_title if handoff else "Universe Analysis")
    if handoff:
        st.write(handoff.research_question)
        st.caption(f"Research Universe · {handoff.expected_constituent_count} companies")
    else:
        st.caption("Population-level technical comparison from stored observations.")
    try:
        repository = research_repository_from_env()
        filter_options = repository.technical_analysis_observations(
            latest_scan_only=False
        )
    except Exception as error:
        st.error("Security Analysis Explorer unavailable: " + str(error))
        return

    scan_ids = list(filter_options["available_scan_ids"])
    selected_scan = active_run.scan_id if active_run else ""
    latest_scan_only = False if active_run else True
    with st.expander("Advanced analysis controls", icon=":material/tune:"):
        browse_history = st.toggle(
            "Browse historical scans (compatibility)", value=False,
            key="tam_browse_historical_scans", disabled=not bool(scan_ids),
        )
        if browse_history:
            selected_scan = st.selectbox(
                "Scan ID", options=[""] + scan_ids,
                format_func=lambda value: "All scans" if value == "" else value,
                key="tam_scan_id",
            )
            latest_scan_only = st.toggle(
                "Latest scan only", value=True, key="tam_latest_scan_only",
                disabled=bool(selected_scan),
            )
        elif active_run:
            st.caption("Current Research Universe run: " + active_run.scan_id)

    pending_ticker = st.session_state.pop("benchmark_pending_sam_ticker", None)
    if pending_ticker and pending_ticker in filter_options["available_tickers"]:
        st.session_state.tam_ticker_search = ""
        st.session_state.tam_tickers = [pending_ticker]
    elif pending_ticker:
        st.session_state.benchmark_sam_handoff_error = (
            f"{pending_ticker} has no stored SAM observation and cannot be selected in this experience."
        )
    ticker_search = st.text_input("Ticker search", key="tam_ticker_search").strip().upper()
    ticker_options = [
        ticker
        for ticker in filter_options["available_tickers"]
        if not ticker_search or ticker.startswith(ticker_search)
    ]
    handoff_error = st.session_state.pop("benchmark_sam_handoff_error", None)
    if handoff_error:
        st.warning(handoff_error)
    default_tickers = []
    if active_run:
        default_tickers = list(active_run.analyzed_tickers)
    elif handoff:
        allowed = set(filter_options["available_tickers"])
        default_tickers = [ticker for ticker in handoff.approved_constituents if ticker in allowed]
    selected_tickers = st.multiselect(
        "Tickers",
        options=ticker_options,
        default=default_tickers,
        key="tam_tickers",
    )
    trend_states = st.multiselect(
        "Trend State",
        options=list(filter_options["available_trend_states"]),
        key="tam_trend_states",
    )
    momentum_states = st.multiselect(
        "Momentum State",
        options=list(filter_options["available_momentum_states"]),
        key="tam_momentum_states",
    )
    volatility_states = st.multiselect(
        "Volatility State",
        options=list(filter_options["available_volatility_states"]),
        key="tam_volatility_states",
    )

    try:
        observations = repository.technical_analysis_observations(
            tickers=selected_tickers,
            trend_states=trend_states,
            momentum_states=momentum_states,
            volatility_states=volatility_states,
            latest_scan_only=latest_scan_only,
            scan_id=selected_scan or None,
        )
    except Exception as error:
        st.error("Unable to load SAM observations: " + str(error))
        return

    rows = [tam_display_row(row) for row in observations["rows"]]
    expected_count = active_run.requested_constituent_count if active_run else handoff.total_member_count if handoff else len(rows)
    st.caption(f"Showing {len(rows)} of {expected_count} universe members")
    if active_run:
        st.caption(
            f"Requested {active_run.requested_constituent_count} · "
            f"analyzed {len(active_run.analyzed_tickers)} · "
            f"unavailable {active_run.requested_constituent_count - len(active_run.analyzed_tickers)}"
        )
        with st.expander("Research Universe result ledger"):
            st.dataframe(pd.DataFrame([{
                "Company": entry.company_name,
                "Ticker or identifier": entry.ticker_or_identifier or "Unresolved",
                "Result": entry.status.value,
                "Reason": entry.reason,
            } for entry in active_run.ledger]), hide_index=True)
    summary = tam_summary_metrics(rows, observations["latest_technical_timestamp"])
    render_metric_grid({
        "Companies analyzed": summary["Tickers Characterized"],
        "Strong setups": summary["Strong Count"],
        "Constructive setups": summary["Constructive Count"],
        "Weak/poor setups": summary["Weak/Poor Count"],
        "Bullish trends": summary["Bullish Trend Count"],
        "Average technical score": summary["Average SAM Score (Experimental)"],
    }, columns_per_row=3)
    with st.expander("Population details"):
        render_metric_grid({
            key: value for key, value in summary.items()
            if key not in {
                "Tickers Characterized", "Strong Count", "Constructive Count",
                "Weak/Poor Count", "Bullish Trend Count", "Average SAM Score (Experimental)",
            }
        }, columns_per_row=4)
    if observations.get("selected_scan_id"):
        st.caption("Selected technical scan_id: " + observations["selected_scan_id"])

    if not rows:
        st.info("No technical characterization rows match the selected filters.")
        return

    st.subheader("Company comparison")
    st.caption(
        "Security Setup Score is Experimental / Observational. It summarizes SAM "
        "observations only and does not define Research Universe gates or influence "
        "Opportunity Discovery, OAM scoring, OAE, rankings, filters, thresholds, or "
        "Evaluation Profile logic."
    )
    st.caption("Legend: ▲ positive/above · ▼ negative/below · ● neutral/near; text labels remain visible.")
    st.dataframe(
        pd.DataFrame(rows)
        .reindex(columns=TAM_PRIMARY_COLUMNS)
        .rename(
            columns={
                "technical_setup_score_experimental": "Technical score (descriptive)",
                "technical_setup_grade_experimental": "Setup",
                "price_vs_sma_20": "Price vs 20-day SMA",
                "price_vs_sma_50": "Price vs 50-day SMA",
                "price_vs_sma_200": "Price vs 200-day SMA",
                "rsi_14": "RSI",
                "macd_histogram": "MACD",
                "trend_state": "Trend",
                "momentum_state": "Momentum",
                "volatility_state": "Volatility",
            }
        )
        .style.format(
            {
                "price": format_decimal,
                "Price vs 20-day SMA": tam_signed_percent,
                "Price vs 50-day SMA": tam_signed_percent,
                "Price vs 200-day SMA": tam_signed_percent,
                "RSI": format_decimal,
                "MACD": format_decimal,
                "Technical score (descriptive)": format_decimal,
            }
        ).map(
            tam_numeric_color,
            subset=["Price vs 20-day SMA", "Price vs 50-day SMA", "Price vs 200-day SMA", "MACD"],
        ).map(tam_state_color, subset=["Trend", "Momentum"]),
        hide_index=True,
        width="stretch",
    )
    with st.expander("Technical data and diagnostics", icon=":material/database:"):
        st.dataframe(pd.DataFrame(rows).reindex(columns=TAM_DISPLAY_COLUMNS), hide_index=True)

    selected_company = st.selectbox(
        "Explore a company", [row["ticker"] for row in rows], key="universe_detail_ticker"
    )
    selected_row = next(row for row in rows if row["ticker"] == selected_company)
    with st.expander(f"Why does {selected_company} have this setup?", expanded=False):
        st.write(
            f"Trend: {selected_row.get('trend_state', 'unavailable')}. "
            f"Momentum: {selected_row.get('momentum_state', 'unavailable')}. "
            f"Volatility: {selected_row.get('volatility_state', 'unavailable')}."
        )
        st.caption(f"Observation timestamp: {selected_row.get('technical_timestamp', UNAVAILABLE)}")
        if st.button("View Company Analysis", key="view_company_analysis"):
            st.session_state["company_analysis_context"] = {
                "ticker": selected_company, "row": selected_row, "parent_handoff": handoff,
                "return_destination": "Universe Analysis",
            }
            request_navigation("Company Analysis")

    rsi_tab, trend_tab, momentum_tab, volatility_tab, missing_tab = st.tabs(
        [
            "RSI Distribution",
            "Trend Counts",
            "Momentum Counts",
            "Volatility Counts",
            "Missing Indicators",
        ]
    )
    with rsi_tab:
        render_tam_count_chart(tam_rsi_distribution(rows), label_column="Bucket")
    with trend_tab:
        render_tam_count_chart(tam_count_rows(rows, "trend_state"))
    with momentum_tab:
        render_tam_count_chart(tam_count_rows(rows, "momentum_state"))
    with volatility_tab:
        render_tam_count_chart(tam_count_rows(rows, "volatility_state"))
    with missing_tab:
        missing_rows = tam_missing_indicator_rows(rows)
        if missing_rows:
            st.dataframe(pd.DataFrame(missing_rows), hide_index=True, width="stretch")
        else:
            st.info("No missing required SAM indicators in the current result set.")


def load_local_environment():
    env_path = ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def render_technical_analysis_explorer_workflow():
    """Render the user-facing exact-universe analysis experience."""
    render_universe_analysis()


def launch_benchmark_company_analysis(ticker: str) -> None:
    """Use the existing Security Research/SAM ticker-selection contract."""
    canonical = str(ticker or "").strip().upper()
    if not canonical:
        st.session_state.benchmark_sam_handoff_error = "SAM requires a public ticker."
        return
    st.session_state.benchmark_pending_sam_ticker = canonical
    st.session_state["company_analysis_context"] = {
        "ticker": canonical,
        "row": {"ticker": canonical, "technical_timestamp": UNAVAILABLE},
        "parent_handoff": None,
        "return_destination": "Research Universe",
    }
    request_navigation("Company Analysis")


def render_company_analysis_shell():
    context = st.session_state.get("company_analysis_context")
    if not context:
        st.info("Select a company from Universe Analysis to open its company-level context.")
        return
    ticker = context["ticker"]
    company_name = context.get("company_name") or ticker
    row = context["row"]
    parent = context.get("parent_handoff")
    st.subheader(company_name)
    if company_name != ticker:
        st.caption(ticker)
    if parent:
        st.caption(f"From {parent.universe_title} · Version {parent.universe_version}")
    st.write(
        f"Trend: {row.get('trend_state', 'unavailable')}. "
        f"Momentum: {row.get('momentum_state', 'unavailable')}. "
        f"Volatility: {row.get('volatility_state', 'unavailable')}."
    )
    st.caption(f"Observation timestamp: {row.get('technical_timestamp', UNAVAILABLE)}")
    st.info("The deeper single-company experience is the next redesign target.")
    destination = context.get("return_destination") or "Universe Analysis"
    if st.button(f"Return to {destination}", icon=":material/arrow_back:"):
        request_navigation(destination)


def enforce_app_password():
    expected_password = os.getenv(APP_PASSWORD_ENV, "")
    if not expected_password:
        return
    if st.session_state.get("app_password_authenticated"):
        return

    st.title("Kip Options Scanner")
    password = st.text_input("Password", type="password")
    if st.button("Unlock"):
        if compare_digest(password, expected_password):
            st.session_state.app_password_authenticated = True
            st.rerun()
        st.error("Invalid password.")
    st.stop()


def main():
    load_local_environment()
    st.set_page_config(page_title="Kip Options Scanner", layout="wide")
    enforce_app_password()
    apply_pending_navigation()
    default_universe_path = str(ROOT / "data" / "technology_growth_ai_v1.csv")
    if "research_universe_path" not in st.session_state:
        st.session_state.research_universe_path = default_universe_path
    reload_universe = False
    compatibility_routes = {
        "Research Workspace": "Home",
        "Research Universe Builder": "Research Launchpad",
        "Benchmark Explorer": "Research Universe",
        "Research Universes": "Research Universe",
        "Benchmark Curator Workbench": "Administration",
        "Security Analysis Explorer": "Company Analysis",
        "Security Research": "Company Analysis",
        "Opportunity Research": "Opportunities",
        "Research Repository": "History",
        "Tradier Connection": "Administration",
        "Startup Check": "Administration",
    }
    current_route = st.session_state.get("selected_page", "Home")
    if current_route in compatibility_routes:
        st.session_state.selected_page = compatibility_routes[current_route]
    app_pages = [
        "Home",
        "Research Launchpad",
        "Research Universe",
        "Universe Analysis",
        "Company Analysis",
        "Opportunities",
        "History",
        "Administration",
    ]
    with st.sidebar:
        st.markdown("## Kip Research")
        selected_page = st.radio("Navigation", app_pages, key="selected_page")
        if selected_page == "Opportunities":
            st.text_input(
                "Research Universe CSV",
                key="research_universe_path",
            )
            reload_universe = st.button("Reload Research Universe CSV")

    path = st.session_state.research_universe_path
    universe_error = None
    try:
        universe = load_universe(path)
    except UniverseError as error:
        universe_error = error
        with st.sidebar:
            if selected_page == "Opportunities":
                st.error("Unable to load Research Universe: " + str(error))
        universe = []
    universe_symbols = [item.symbol for item in universe]
    with st.sidebar:
        render_research_sidebar_metadata(
            {
                "Company Analysis": "Security Research",
                "Opportunities": "Opportunity Research",
            }.get(selected_page),
            path,
            len(universe_symbols),
        )

    if selected_page == "Home":
        render_home(path, universe_symbols)
    elif selected_page == "Company Analysis":
        st.title("Company Analysis")
        render_company_analysis_shell()
    elif selected_page == "Universe Analysis":
        render_technical_analysis_explorer_workflow()
    elif selected_page == "Opportunities":
        st.title("Opportunities")
        (
            opportunity_discovery_tab,
            option_chain_explorer_tab,
            option_analysis_explorer_tab,
        ) = st.tabs(
            [
                "Opportunity Discovery",
                "Option Chain Explorer",
                "Option Analysis Explorer",
            ]
        )
        with opportunity_discovery_tab:
            render_opportunity_discovery_workflow(
                Path(path).stem,
                path,
                universe_symbols,
                universe_error,
                reload_universe,
            )
        with option_chain_explorer_tab:
            render_option_chain_explorer_workflow()
        with option_analysis_explorer_tab:
            render_quality_engine_diagnostics_workflow()
    elif selected_page == "History":
        render_research_repository_page()
    elif selected_page == "Research Launchpad":
        render_research_universe_builder(root=ROOT, analyze_company=launch_benchmark_company_analysis)
    elif selected_page == "Research Universe":
        render_current_research_universe_page(analyze_company=launch_benchmark_company_analysis)
    elif selected_page == "Administration":
        st.title("Administration")
        admin_page = st.selectbox(
            "Administration area",
            [
                "Tradier Connection",
                "Developer diagnostics",
                "Benchmark certification",
                "Startup Check",
            ],
        )
        st.space("small")
        if admin_page == "Tradier Connection":
            ticker = st.text_input("Ticker symbol", value="SPY", max_chars=10).strip().upper()
            get_quote = st.button("Get Quote", type="primary")
            show_diagnostic_data = st.checkbox("Show Diagnostic Data")
            render_tradier_quote(ticker, get_quote, show_diagnostic_data)
        elif admin_page in ("Developer diagnostics", "Startup Check"):
            render_startup_check()
        else:
            render_benchmark_explorer(ROOT, analyze_company=launch_benchmark_company_analysis)


if __name__ == "__main__":
    main()
