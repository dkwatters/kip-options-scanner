# Kip Options Research Platform

Kip Options is a Streamlit-based, question-driven quantitative research platform. It begins with investor curiosity, translates plain-language research questions into Research Missions and Research Universes, characterizes securities, evaluates option opportunities, and preserves research evidence over time.

Conversation starts the process. Evidence completes it. The platform remembers research rather than conversations through durable Research Sessions that can preserve the original question, mission, universe, findings, refinements, decisions, and saved notes.

It has no trading, brokerage account access, Robinhood integration, order placement, recommendations, affordability scoring, autonomous investment advice, or portfolio awareness. Its option-analysis score is an explainable evaluation of existing Option Analysis Model rules, not a recommendation.

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
backend, database connectivity, and latest scan timestamp. The Research sidebar
section initially shows only Security Research and Opportunity Research choices.
Security Research and Opportunity Research sidebar views show metadata only;
analytical explorers are organized in the main workspace. If
`APP_PASSWORD` is unset, the app runs without a password prompt.

## Architecture

- `app.py`: quote view, metadata-only Research sidebar, Security Analysis Explorer, Opportunity Discovery, Option Chain Explorer, and Option Analysis Explorer. Opportunity Discovery evaluates a Research Universe by Calls/Puts and configurable DTE range before selecting the highest-quality passing contract or highest-quality true near miss, then renders a selectable ranking table that reuses the Contract Detail Summary. The opportunity workspace retrieves expirations, presents Opportunity Analysis, passing contracts, true near misses, and diagnostic option analytics for the selected Calls/Puts type.
- `src/contract_scoring.py`: reusable, configuration-driven quality-score helper. Its default Delta Fit, Spread, Open Interest, and Volume weights total 100 and can later be exposed as user-editable settings.
- `src/tradier_client.py`: read-only market-data GET client.
- `src/universe.py`: validated CSV-backed Research Universe loading.
- `src/opportunity_ranking.py`: presentation-neutral Research Universe opportunity selection and ranking.
- `src/indicators.py`, `src/scoring.py`, and `src/scanner.py`: future-facing typed data contracts.

The CSV requires `symbol`; `name`, `sector`, and `enabled` are optional. `run_scan()` deliberately raises `ScannerNotImplementedError` in this phase.
