# Cloud Migration Plan

## Purpose

This plan prepares SP-001 scheduled Study Protocol observations for cloud execution while preserving the current local SQLite research workflow.

No deployment is included in v0.1.

---

## Recommended Architecture

The recommended cloud architecture is:

- Cloud scheduler triggers the research runner at the SP-001 observation times.
- Cloud research runner executes `research_scan.py` or `cloud_research_runner.py` in scheduled mode.
- Market-calendar guard skips non-trading days before market-data calls.
- Research Repository abstraction selects local SQLite or cloud Postgres.
- Research Dashboard either runs cloud-hosted or reads from the cloud repository.

The local laptop Task Scheduler setup remains useful for development and fallback validation, but it is not the target continuous-observation infrastructure.

---

## Required External Services

- Cloud scheduler or cron service.
- Python runtime with project dependencies installed.
- Tradier market-data credentials.
- Managed Postgres database for cloud repository storage.
- Secret manager or equivalent environment-variable injection.
- Optional cloud-hosted dashboard runtime.

---

## Environment Variables

### Required for Cloud Runner

| Variable | Purpose |
| --- | --- |
| `CLOUD_RUNNER` | Set to `true` when using `research_scan.py --from-env` in a cloud cron context. |
| `RESEARCH_RUN_MODE` | Must be `scheduled` for cloud scheduled observations. |
| `SCHEDULED_TIME_LABEL` | Schedule slot archived with the observation, such as `10:00 ET`. |
| `TRADIER_API_TOKEN` | Tradier market-data API token. |
| `TRADIER_ENVIRONMENT` | Tradier environment, `sandbox` or `production`. |
| `RESEARCH_REPOSITORY_BACKEND` | Repository backend selector. Use `sqlite` locally; cloud value is `postgres`. |
| `DATABASE_URL` | Postgres connection URL for cloud repository storage. Required when backend is `postgres`. |

`RESEARCH_SCHEDULED_TIME_LABEL` is also accepted as an alternate scheduled time label.

### Optional for Research Conversation Engine

| Variable | Purpose |
| --- | --- |
| `RCE_PROVIDER` | RCE provider selector. Use `mock` for deterministic local behavior or `openai` for live structured interpretation. Defaults to `mock` when unset. |
| `OPENAI_API_KEY` | OpenAI API key required when `RCE_PROVIDER=openai`. |
| `RCE_OPENAI_MODEL` | Optional OpenAI model override for RCE interpretation. |
| `RCE_DEBUG_ARTIFACTS` | Set to `true` to show provider, timing, fallback, parser, verification-marker, and candidate-count diagnostics in Research Workspace. |

RCE provider settings affect only Research Workspace interpretation. They do not change scheduled scans, cloud jobs, repository schema, scoring, SAM, OD, OAM, or Study Protocol behavior.

### Optional for Local SQLite

| Variable | Purpose |
| --- | --- |
| `RESEARCH_SQLITE_PATH` | Overrides the local SQLite path. Defaults to `data/research/opportunity_scans.sqlite`. |

---

## Local vs Cloud Repository Behavior

Local behavior remains SQLite-first:

- If no repository environment variables are set, scans archive to `data/research/opportunity_scans.sqlite`.
- If `RESEARCH_REPOSITORY_BACKEND=sqlite`, `RESEARCH_SQLITE_PATH` may override the local path.
- Existing app and local `research_scan.py` usage continue to work with SQLite.

Cloud repository behavior:

- If `DATABASE_URL` is present, the repository target resolves to Postgres unless explicitly configured otherwise.
- If `RESEARCH_REPOSITORY_BACKEND=postgres`, `DATABASE_URL` is required and must use a `postgres` or `postgresql` URL scheme.
- The Postgres backend initializes the research schema and persists `opportunity_scans`, `evaluated_contracts`, `rule_evaluations`, and `security_characterization`.
- A psycopg-compatible runtime dependency is required for Postgres connections.

---

## Market Calendar Behavior

Scheduled runs use U.S. equity market calendar awareness:

- Weekends are skipped.
- Regular U.S. market holidays are skipped.
- Observed holidays are skipped.
- Early-close days are identified for future scheduling policy, but v0.1 does not yet adjust scan times.

The scheduled runner skips closed market days before making market-data calls or archiving an observation. Manual research-script mode remains available for ad hoc local research.

---

## Migration Phases

### Phase 0 - Local Readiness

- Keep local SQLite as the default repository.
- Add repository backend configuration.
- Add market-calendar skip logic for scheduled observations.
- Add cloud-runner environment validation.
- Document required cloud services and variables.

### Phase 1 - Cloud Dry Run

- Provision cloud runtime and secrets.
- Configure cloud cron entries for SP-001 labels.
- Run with `RESEARCH_REPOSITORY_BACKEND=postgres` and a managed database `DATABASE_URL`.
- Confirm schema initialization, repository writes, closed-market skips, and required-variable failures.

### Phase 2 - Cloud Repository Implementation

- Add integration tests against an isolated Postgres instance.
- Verify parity with SQLite row counts and protocol progress.

### Phase 3 - Dashboard Cloud Readiness

- Point the Research Dashboard at the configured repository backend.
- Support cloud-hosted dashboard deployment or local dashboard reads from cloud data.
- Confirm manual scans remain excluded from scheduled protocol progress.

### Phase 4 - Continuous Observation

- Enable cloud scheduler for SP-001.
- Monitor run results, skip reasons, and repository writes.
- Add early-close schedule policy after observed behavior is validated.
