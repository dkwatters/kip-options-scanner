# Cloud Infrastructure Cheat Sheet

## GitHub

GitHub is the source-control home for the project. Render can connect to the
repository and redeploy the Streamlit app or cron job code when changes are
pushed.

## Render Web Service

The Render Web Service hosts the Streamlit dashboard so demos do not depend on a
laptop being online.

Web command:

```bash
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

The web service reads the Research Repository configured by environment
variables and shows startup status in the sidebar.

## Render Cron Jobs

Render Cron Jobs run scheduled research scans without using the Streamlit UI.
They should execute the scheduled runner with the same repository and Tradier
environment variables used by the cloud deployment.

Cron jobs create laptop-independent SP-001 observations because they run on
Render's infrastructure rather than Windows Task Scheduler.

## Render Postgres

Render Postgres is the cloud Research Repository. It stores archived
`opportunity_scans`, `evaluated_contracts`, `rule_evaluations`, and
`security_characterization` rows for both scheduled scans and manual demo scans.

## Environment Variables

Render environment variables replace local `.env` files in cloud deployments.
Set secrets in Render, not in GitHub.

Common variables:

| Variable | Purpose |
| --- | --- |
| `RESEARCH_REPOSITORY_BACKEND` | Set to `postgres` in cloud. |
| `DATABASE_URL` | Postgres connection URL supplied by Render. |
| `TRADIER_API_TOKEN` | Tradier market-data token. |
| `TRADIER_ENVIRONMENT` | Tradier environment, such as `sandbox` or `production`. |
| `APP_PASSWORD` | Optional password gate for demo protection. |
| `RESEARCH_RUN_MODE` | Set to `scheduled` for cloud cron scans. |
| `SCHEDULED_TIME_LABEL` | Scheduled observation label, such as `10:00 ET`. |

## DATABASE_URL

`DATABASE_URL` tells the app and scheduled runners which Postgres database to
use. When `RESEARCH_REPOSITORY_BACKEND=postgres`, it is required and must start
with `postgres://` or `postgresql://`.

Do not paste `DATABASE_URL` into documentation, commits, or screenshots.

## APP_PASSWORD

`APP_PASSWORD` is optional. If set, the Streamlit app shows a password prompt
before loading the dashboard. If unset, the app opens normally.

This is a lightweight demo-protection gate, not a full user-account system.

## Laptop-Independent Demo Architecture

The full cloud architecture separates source code, hosting, scheduling, and
storage:

- GitHub stores the app and runner code.
- Render Web Service hosts the Streamlit dashboard.
- Render Cron Jobs run scheduled research scans.
- Render Postgres stores all archived research observations.
- Render environment variables provide secrets and deployment configuration.

With this setup, a demo can show current repository status, recent scheduled
observations, and manual scan results from the cloud database even when the
local laptop is offline.
