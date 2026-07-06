# Kip Options Scanner

Phase 4B is a Streamlit research tool for inspecting Tradier option-chain market data and ranking the best current watchlist opportunity per ticker. It has no trading, brokerage account access, Robinhood integration, order placement, recommendations, historical tracking, technical indicators, affordability scoring, AI reasoning, or portfolio awareness. Its contract-quality score is an explainable evaluation of existing quality rules, not a recommendation.

## Setup

1. Create a Python 3.11+ environment.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and configure a Tradier token if needed later.
4. Start: `streamlit run app.py`.

Local runs default to the SQLite research repository at
`data/research/opportunity_scans.sqlite`. A local `.env` file is optional; cloud
deployments should use platform environment variables instead.

## Render Web Service Deployment

Deploy the dashboard as a Render Web Service backed by the cloud Postgres
Research Repository.

Use this web command:

```bash
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

Set these Render environment variables:

| Variable | Required | Purpose |
| --- | --- | --- |
| `RESEARCH_REPOSITORY_BACKEND` | Yes | Set to `postgres` for the cloud Research Repository. |
| `DATABASE_URL` | Yes | Render Postgres connection URL. Must use a `postgres` or `postgresql` scheme. |
| `TRADIER_API_TOKEN` | Yes for market-data actions | Tradier market-data API token. |
| `TRADIER_ENVIRONMENT` | Yes for market-data actions | Tradier environment, usually `sandbox` or `production`. |
| `APP_PASSWORD` | No | Optional shared password gate for demo protection. |

On startup, the app sidebar shows a Startup Check with the resolved repository
backend, database connectivity, and latest scan timestamp. If
`APP_PASSWORD` is unset, the app runs without a password prompt.

## Architecture

- `app.py`: quote view, Opportunity Discovery, and Option Chain Explorer. Opportunity Discovery filters watchlist contracts by Calls/Puts and a configurable DTE range before selecting the highest-quality passing contract or highest-quality true near miss, then renders a selectable ranking table that reuses the Contract Detail Summary. The explorer retrieves expirations, then presents Opportunity Analysis, passing contracts, and true near misses for the selected Calls/Puts type. An Advanced Diagnostics expander contains test-specific near misses, threshold-analysis tables, and the raw chain response used for validation.
- `src/contract_scoring.py`: reusable, configuration-driven quality-score helper. Its default Delta Fit, Spread, Open Interest, and Volume weights total 100 and can later be exposed as user-editable settings.
- `src/tradier_client.py`: read-only market-data GET client.
- `src/universe.py`: validated CSV universe and editable default watchlist.
- `src/opportunity_ranking.py`: presentation-neutral watchlist opportunity selection and ranking.
- `src/indicators.py`, `src/scoring.py`, and `src/scanner.py`: future-facing typed data contracts.

The CSV requires `symbol`; `name`, `sector`, and `enabled` are optional. `run_scan()` deliberately raises `ScannerNotImplementedError` in this phase.
