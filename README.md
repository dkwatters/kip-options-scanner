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

## Research Universe API v0.1

The optional FastAPI service exposes a deliberately narrow interoperability boundary over the same Research Universe repository used by the Streamlit application. It does not expose trading, brokerage, RCE generation, analysis execution, or arbitrary database operations.

Run locally with:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

For a separate Render Web Service use:

```bash
uvicorn api:app --host 0.0.0.0 --port $PORT
```

Configure `RESEARCH_REPOSITORY_BACKEND=postgres`, the same `DATABASE_URL` used by the application, and a long random `RESEARCH_API_KEY`. Protected requests must send `Authorization: Bearer <RESEARCH_API_KEY>`. `GET /health` is intentionally unauthenticated for service health checks.

The v0.1 surface is limited to `GET /health`, `GET /api/v1/universes`, `GET /api/v1/universes/{universe_id}`, and `POST /api/v1/universes`. Creation requires an explicit approval envelope with `mechanism=explicit_conversation_confirmation`. The approval contains a SHA-256 membership digest computed over the exact ordered list of normalized `{company_name, ticker_or_identifier}` members. The server recomputes that digest before persistence and refuses creation when membership changed after approval. It also refuses creation if canonicalization changes approved membership cardinality.

## Architecture

- `app.py`: quote view, metadata-only Research sidebar, Security Analysis Explorer, Opportunity Discovery, Option Chain Explorer, and Option Analysis Explorer. Opportunity Discovery evaluates a Research Universe by Calls/Puts and configurable DTE range before selecting the highest-quality passing contract or highest-quality true near miss, then renders a selectable ranking table that reuses the Contract Detail Summary. The opportunity workspace retrieves expirations, presents Opportunity Analysis, passing contracts, true near misses, and diagnostic option analytics for the selected Calls/Puts type.
- `api.py`: authenticated Research Universe API v0.1 transport boundary.
- `src/research_universe_api_service.py`: approval binding, canonical creation orchestration, repository reads, and API projection without direct SQL access.
- `src/contract_scoring.py`: reusable, configuration-driven quality-score helper. Its default Delta Fit, Spread, Open Interest, and Volume weights total 100 and can later be exposed as user-editable settings.
- `src/tradier_client.py`: read-only market-data GET client.
- `src/universe.py`: validated CSV-backed Research Universe loading.
- `src/opportunity_ranking.py`: presentation-neutral Research Universe opportunity selection and ranking.
- `src/indicators.py`, `src/scoring.py`, and `src/scanner.py`: future-facing typed data contracts.

The CSV requires `symbol`; `name`, `sector`, and `enabled` are optional. `run_scan()` deliberately raises `ScannerNotImplementedError` in this phase.
