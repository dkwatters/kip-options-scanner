from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.contract_quality import (
    calculate_mid_price,
    contract_quality,
    contract_quality_summary,
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
                "Strike": option.get("strike", UNAVAILABLE),
                "Option Type": option.get("option_type", UNAVAILABLE),
                "Bid": option.get("bid", UNAVAILABLE),
                "Ask": option.get("ask", UNAVAILABLE),
                "Delta": greeks.get("delta", UNAVAILABLE),
                "Implied Volatility": implied_volatility(greeks),
                "Volume": option.get("volume", UNAVAILABLE),
                "Open Interest": option.get("open_interest", UNAVAILABLE),
                **quality,
            }
        )
    return rows


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
                    ("Volume", quote.get("volume", UNAVAILABLE)),
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

            st.subheader("Contract Quality Summary")
            summary = contract_quality_summary(chain_rows)
            for column, (label, value) in zip(st.columns(6), summary.items()):
                column.metric(label, value)
            chain_dataframe = pd.DataFrame(chain_rows).style.format(
                {
                    "Mid Price": "{:.2f}",
                    "Spread": "{:.2f}",
                    "Spread %": "{:.2%}",
                    "Strike Distance %": "{:.2%}",
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
