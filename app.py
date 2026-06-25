from datetime import date, datetime, timezone
from math import isfinite
from numbers import Number
from pathlib import Path
from zoneinfo import ZoneInfo

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
from src.opportunity_ranking import (
    NO_CANDIDATE,
    NO_MATCHING_CONTRACTS,
    no_matching_contracts_row,
    opportunity_table_rows,
)
from src.quality_diagnostics import (
    average_rule_contribution,
    discovery_diagnostic_summary,
    quality_score_distribution,
    rule_failure_distribution,
    status_distribution,
    top_opportunity_summary,
)
from src.scanner import ScannerNotImplementedError, run_scan
from src.tradier_client import TradierAPIError, TradierClient, TradierConfigurationError
from src.universe import DEFAULT_WATCHLIST, UniverseError, load_universe

ROOT = Path(__file__).resolve().parent
EASTERN_TIME = ZoneInfo("America/New_York")
UNAVAILABLE = "-"
DEFAULT_DISCOVERY_MIN_DTE = 7
DEFAULT_DISCOVERY_MAX_DTE = 28


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
                    ticker or option.get("root_symbol"),
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


def parse_watchlist(value):
    """Return uppercase symbols from a newline/comma separated watchlist."""
    symbols = []
    seen = set()
    for raw_symbol in value.replace(",", "\n").splitlines():
        symbol = raw_symbol.strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return symbols


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


def discover_watchlist_opportunities(
    client,
    watchlist,
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
    for symbol in watchlist:
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
        "Passing Contracts Count",
        "True Near Miss Count",
        "Rejected Count",
        "Highest Quality Score",
        "Lowest Quality Score",
        "Average DTE",
        "Average Open Interest",
        "Average Volume",
    }:
        return format_whole_number(value)
    if label in {"Average Strike Distance %", "Average Spread %"}:
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


def render_quality_engine_diagnostics(evaluated_rows, opportunity_rows):
    """Render one-run diagnostics for current Opportunity Discovery results."""
    with st.expander("Quality Engine Diagnostics", expanded=False):
        if not evaluated_rows:
            st.info("No evaluated contracts are available for the current Opportunity Discovery run.")
            return

        st.caption(
            "Diagnostics use only contracts evaluated by the current Opportunity Discovery filters."
        )
        render_metric_grid(discovery_diagnostic_summary(evaluated_rows))

        st.markdown("Top 10 Opportunity Summary")
        render_metric_grid(top_opportunity_summary(opportunity_rows), columns_per_row=4)

        score_column, status_column = st.columns(2)
        with score_column:
            st.markdown("Quality Score Distribution")
            render_bar_chart(
                quality_score_distribution(evaluated_rows),
                "Score Bucket",
                "Contracts",
            )
        with status_column:
            st.markdown("Status Distribution")
            render_bar_chart(status_distribution(evaluated_rows), "Status", "Contracts")

        failure_column, contribution_column = st.columns(2)
        with failure_column:
            st.markdown("Rule Failure Distribution")
            render_bar_chart(
                rule_failure_distribution(evaluated_rows),
                "Rule",
                "Failures",
            )
        with contribution_column:
            st.markdown("Average Rule Contribution")
            render_bar_chart(
                average_rule_contribution(evaluated_rows),
                "Rule",
                "Average Points",
            )


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


def main():
    load_dotenv(ROOT / ".env")
    st.set_page_config(page_title="Kip Options Scanner", layout="wide")
    st.title("Kip Options Scanner")
    st.caption("Phase 4B - Research tool only - No trading or order placement")
    with st.sidebar:
        path = st.text_input("Universe CSV", value=str(ROOT / "data" / "universe_default.csv"))
        st.header("Tradier Connection")
        ticker = st.text_input("Ticker symbol", value="SPY", max_chars=10).strip().upper()
        get_quote = st.button("Get Quote")
        show_diagnostic_data = st.checkbox("Show Diagnostic Data")
    try:
        universe = load_universe(path)
    except UniverseError as error:
        st.error("Unable to load universe: " + str(error))
        universe = []

    st.subheader("Tradier quote")
    if get_quote:
        if not ticker:
            st.error("Enter a ticker symbol before requesting a quote.")
        else:
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

    st.divider()
    st.subheader("Opportunity Discovery")
    st.caption(
        "Ranks the best passing contract, or highest-quality true near miss, for each watchlist ticker."
    )
    watchlist_input = st.text_area(
        "Watchlist",
        value="\n".join(DEFAULT_WATCHLIST),
        height=180,
        help="Edit this list here for the current run, or update DEFAULT_WATCHLIST in src/universe.py.",
    )
    watchlist = parse_watchlist(watchlist_input)
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
        disabled=not watchlist or invalid_discovery_dte,
    )

    if run_discovery:
        try:
            (
                opportunity_rows,
                discovery_errors,
                discovery_evaluated_rows,
            ) = discover_watchlist_opportunities(
                TradierClient(),
                watchlist,
                datetime.now(EASTERN_TIME).date(),
                option_type=selected_discovery_option_type,
                min_dte=min_discovery_dte,
                max_dte=max_discovery_dte,
            )
        except TradierConfigurationError as error:
            st.error("Tradier configuration error: " + str(error))
        else:
            st.session_state.opportunity_rows = opportunity_rows
            st.session_state.opportunity_errors = discovery_errors
            st.session_state.opportunity_evaluated_rows = discovery_evaluated_rows
            st.session_state.opportunity_watchlist = watchlist
            st.session_state.opportunity_settings = discovery_settings

    opportunity_rows = st.session_state.get("opportunity_rows", [])
    opportunity_evaluated_rows = st.session_state.get("opportunity_evaluated_rows", [])
    opportunity_watchlist = st.session_state.get("opportunity_watchlist", [])
    opportunity_settings = st.session_state.get("opportunity_settings")
    current_opportunity_context = (
        opportunity_watchlist == watchlist
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
        render_quality_engine_diagnostics(opportunity_evaluated_rows, opportunity_rows)
    elif opportunity_watchlist and current_opportunity_context:
        st.info("No passing or true near-miss contracts were found for this watchlist.")
        render_quality_engine_diagnostics(opportunity_evaluated_rows, opportunity_rows)

    discovery_errors = st.session_state.get("opportunity_errors", {})
    if discovery_errors and current_opportunity_context:
        with st.expander("Watchlist Fetch Errors", expanded=False):
            for symbol, message in discovery_errors.items():
                st.caption(f"{symbol}: {message}")

    st.divider()
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
                "Ticker-level summary of current contract-quality outcomes and closest rule-margin shortfalls."
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
                diagnostics = ticker_diagnostics(chain_rows)
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
                summary = contract_quality_summary(chain_rows)
                for column, (label, value) in zip(st.columns(6), summary.items()):
                    column.metric(label, value)
                chain_dataframe = pd.DataFrame(chain_rows).style.format(
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

    st.subheader("Universe")
    if universe:
        st.dataframe([item.to_display_dict() for item in universe], hide_index=True, width="stretch")
    else:
        st.warning("No enabled symbols are available.")
    if st.button("Run scan", disabled=not universe):
        try:
            run_scan(universe)
        except ScannerNotImplementedError as error:
            st.info(str(error))
    st.subheader("Results")
    st.caption("Results will appear here when scanning is implemented in a later phase.")


if __name__ == "__main__":
    main()
