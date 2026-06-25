# Kip Options Scanner

Phase 4A is a Streamlit research tool for inspecting Tradier option-chain market data. It has no trading, brokerage account access, Robinhood integration, order placement, ranking, or recommendations. Its contract-quality score is an explainable evaluation of existing quality rules, not a recommendation.

## Setup

1. Create a Python 3.11+ environment.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and configure a Tradier token if needed later.
4. Start: `streamlit run app.py`.

## Architecture

- `app.py`: quote view and Option Chain Explorer. The explorer retrieves expirations, then presents Opportunity Analysis, passing contracts, and true near misses for the selected Calls/Puts type. An Advanced Diagnostics expander contains test-specific near misses, threshold-analysis tables, and the raw chain response used for validation. It displays an explainable contract-quality score, but does not rank contracts or tickers, provide recommendations, or add a discovery mode.
- `src/contract_scoring.py`: reusable, configuration-driven quality-score helper. Its default Delta Fit, Spread, Open Interest, and Volume weights total 100 and can later be exposed as user-editable settings.
- `src/tradier_client.py`: read-only market-data GET client.
- `src/universe.py`: validated CSV universe.
- `src/indicators.py`, `src/scoring.py`, and `src/scanner.py`: future-facing typed data contracts.

The CSV requires `symbol`; `name`, `sector`, and `enabled` are optional. `run_scan()` deliberately raises `ScannerNotImplementedError` in this phase.
