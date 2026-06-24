from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

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
    passing_contracts,
    test_specific_near_misses,
    ticker_diagnostics,
)
from src.scanner import ScannerNotImplementedError, run_scan
from src.tradier_client import TradierAPIError, TradierClient, TradierConfigurationError
from src.universe import UniverseError, load_universe

ROOT = Path(__file__).resolve().parent
EASTERN_TIME = ZoneInfo("America/New_York")
UNAVAILABLE = "-"


def style_all_passed(value):
    """Highlight the aggregate quality result without changing contract logic."""
    if value == "Yes":
        return "background-color: #d1fae5; color: #065f46"
    return "background-color: #fee2e2; color: #991b1b"


def format_eastern_timestamp(value):
    """Format Tradier epoch timestamps in the user's Eastern time zone."""
    if value in (None, ""):
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
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return value if value not in (None, "") else UNAVAILABLE


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


def implied_volatility(greeks):
    """Return Tradier's preferred available implied-volatility value."""
    for field in ("mid_iv", "smv_vol", "ask_iv", "bid_iv"):
        value = greeks.get(field)
        if value not in (None, ""):
            return value
    return UNAVAILABLE


def option_chain_rows(payload, expiration=None, today=None, underlying_price=None):
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
        rows.append(
            {
                "Symbol": option.get("symbol", UNAVAILABLE),
                "Strike": option.get("strike", UNAVAILABLE),
                "Expiration": expiration or option.get("expiration_date", UNAVAILABLE),
                "Option Type": option.get("option_type", UNAVAILABLE),
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
        "Symbol",
        "Strike",
        "Expiration",
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
            "Bid": format_decimal,
            "Ask": format_decimal,
            "Mid Price": format_decimal,
            "Spread": format_decimal,
            "Delta": format_decimal,
            "IV": "{:.2%}",
            "Spread %": "{:.2%}",
            "Strike Distance %": "{:.2%}",
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
    st.caption("Phase 2A - Research tool only - No trading or order placement")
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
            st.subheader("Ticker Diagnostics")
            st.caption(
                f"Contract-quality aggregation for {chain_ticker} expiring {chain_expiration}."
            )
            diagnostics = ticker_diagnostics(chain_rows)
            diagnostic_counts = list(diagnostics.items())[:6]
            for column, (label, value) in zip(st.columns(3), diagnostic_counts[:3]):
                column.metric(label, value)
            for column, (label, value) in zip(st.columns(3), diagnostic_counts[3:]):
                column.metric(label, value)
            weakness_column, strength_column = st.columns(2)
            weakness_column.metric("Primary Weakness", diagnostics["Primary Weakness"])
            strength_column.metric("Primary Strength", diagnostics["Primary Strength"])

            controls_column, test_column = st.columns(2)
            selected_option_type = controls_column.selectbox(
                "Option Type",
                options=list(OPTION_TYPE_FILTERS),
                key="diagnostic_option_type",
            )
            selected_test = test_column.selectbox(
                "Near Miss Test",
                options=[ANY_SINGLE_FAILED_TEST, *TEST_SPECIFIC_NEAR_MISS_OPTIONS],
                key="near_miss_test",
            )

            st.subheader("Passing Contracts")
            passing_rows = filter_by_option_type(
                passing_contracts(chain_rows), selected_option_type
            )
            if passing_rows:
                st.dataframe(
                    format_drilldown_dataframe(
                        passing_rows, drilldown_contract_columns()
                    ),
                    hide_index=True,
                    width="stretch",
                )
            else:
                st.info("No contracts in this chain passed all quality tests.")

            st.subheader("Pure Near Miss Contracts")
            near_miss_rows = filter_by_option_type(
                near_miss_contracts(chain_rows), selected_option_type
            )
            if selected_test != ANY_SINGLE_FAILED_TEST:
                near_miss_rows = test_specific_near_misses(near_miss_rows, selected_test)
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
                if selected_test != ANY_SINGLE_FAILED_TEST:
                    st.caption("Contracts are ordered from the smallest shortfall to the largest.")
                st.dataframe(
                    format_drilldown_dataframe(
                        near_miss_display_rows, drilldown_contract_columns(include_failure=True)
                    ),
                    hide_index=True,
                    width="stretch",
                )
            else:
                if selected_test == ANY_SINGLE_FAILED_TEST:
                    st.info("No contracts failed exactly one quality test.")
                else:
                    st.info(
                        f"No {selected_option_type.lower()} contracts failed only the "
                        f"{selected_test.lower()} test."
                    )

            st.subheader("Test-Specific Near Miss Contracts")
            if selected_test == ANY_SINGLE_FAILED_TEST:
                st.info("Select a specific near-miss test to view all contracts failing that test.")
            else:
                selected_near_misses = test_specific_near_misses(
                    filter_by_option_type(chain_rows, selected_option_type), selected_test
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
                    st.dataframe(
                        format_drilldown_dataframe(
                            selected_display_rows,
                            drilldown_contract_columns(include_failure=True)
                            + ["Margin from Passing"],
                        ),
                        hide_index=True,
                        width="stretch",
                    )
                else:
                    st.info(
                        f"No {selected_option_type.lower()} contracts failed the "
                        f"{selected_test.lower()} test."
                    )

            st.subheader("Contract Quality Summary")
            summary = contract_quality_summary(chain_rows)
            for column, (label, value) in zip(st.columns(6), summary.items()):
                column.metric(label, value)
            chain_dataframe = pd.DataFrame(chain_rows).style.format(
                {
                    "Strike": format_decimal,
                    "Bid": format_decimal,
                    "Ask": format_decimal,
                    "Mid Price": format_decimal,
                    "Spread": format_decimal,
                    "Delta": format_decimal,
                    "Spread %": "{:.2%}",
                    "Strike Distance %": "{:.2%}",
                    "Implied Volatility": "{:.2%}",
                    "IV": "{:.2%}",
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
