# Kip Options Scanner

Phase 2A is a Streamlit research tool for inspecting Tradier option-chain market data. It has no trading, brokerage account access, Robinhood integration, or order placement.

## Setup

1. Create a Python 3.11+ environment.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and configure a Tradier token if needed later.
4. Start: `streamlit run app.py`.

## Architecture

- `app.py`: quote view and Option Chain Explorer. The explorer retrieves expirations, then displays the selected chain's strike, type, bid, ask, calculated mid price, delta, implied volatility, volume, and open interest. Its diagnostic control exposes the raw chain response for validation.
- `src/tradier_client.py`: read-only market-data GET client.
- `src/universe.py`: validated CSV universe.
- `src/indicators.py`, `src/scoring.py`, and `src/scanner.py`: future-facing typed data contracts.

The CSV requires `symbol`; `name`, `sector`, and `enabled` are optional. `run_scan()` deliberately raises `ScannerNotImplementedError` in this phase.
