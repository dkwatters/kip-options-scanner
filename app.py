from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
from dotenv import load_dotenv

from src.scanner import ScannerNotImplementedError, run_scan
from src.tradier_client import TradierAPIError, TradierClient, TradierConfigurationError
from src.universe import UniverseError, load_universe

ROOT = Path(__file__).resolve().parent
EASTERN_TIME = ZoneInfo("America/New_York")
UNAVAILABLE = "-"


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
    try:
        bid = float(quote["bid"])
        ask = float(quote["ask"])
    except (KeyError, TypeError, ValueError):
        return UNAVAILABLE
    return (bid + ask) / 2


def main():
    load_dotenv(ROOT / ".env")
    st.set_page_config(page_title="Kip Options Scanner", layout="wide")
    st.title("Kip Options Scanner")
    st.caption("Phase 1B - Research tool only - No trading or order placement")
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
