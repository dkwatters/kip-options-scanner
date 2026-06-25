# Kip Options Scanner

Phase 4B is a Streamlit research tool for inspecting Tradier option-chain market data and ranking the best current watchlist opportunity per ticker. It has no trading, brokerage account access, Robinhood integration, order placement, recommendations, historical tracking, technical indicators, affordability scoring, AI reasoning, or portfolio awareness. Its contract-quality score is an explainable evaluation of existing quality rules, not a recommendation.

## Setup

1. Create a Python 3.11+ environment.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and configure a Tradier token if needed later.
4. Start: `streamlit run app.py`.

## Architecture

- `app.py`: quote view, Opportunity Discovery, and Option Chain Explorer. Opportunity Discovery evaluates the nearest listed option expiration for each watchlist ticker, selects the highest-quality passing contract or highest-quality true near miss, and renders a selectable ranking table that reuses the Contract Detail Summary. The explorer retrieves expirations, then presents Opportunity Analysis, passing contracts, and true near misses for the selected Calls/Puts type. An Advanced Diagnostics expander contains test-specific near misses, threshold-analysis tables, and the raw chain response used for validation.
- `src/contract_scoring.py`: reusable, configuration-driven quality-score helper. Its default Delta Fit, Spread, Open Interest, and Volume weights total 100 and can later be exposed as user-editable settings.
- `src/tradier_client.py`: read-only market-data GET client.
- `src/universe.py`: validated CSV universe and editable default watchlist.
- `src/opportunity_ranking.py`: presentation-neutral watchlist opportunity selection and ranking.
- `src/indicators.py`, `src/scoring.py`, and `src/scanner.py`: future-facing typed data contracts.

The CSV requires `symbol`; `name`, `sector`, and `enabled` are optional. `run_scan()` deliberately raises `ScannerNotImplementedError` in this phase.
