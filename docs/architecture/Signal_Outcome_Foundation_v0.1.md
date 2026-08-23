# Signal and Outcome Foundation v0.1

## Decision

The foundation extends the existing append-oriented Research Repository pattern with a presentation-neutral `Signal`, a separate `SignalOutcome`, and a descriptive model-performance service.

The first producer is the existing deterministic Technical Analysis Model setup score (`technical-setup-score-v0.1`). Its 0–100 score is translated linearly to normalized conviction with `(score - 50) / 50`; its scoring inputs and behavior are unchanged. A missing score produces `abstain`, not `neutral`, and confidence remains absent because the source model does not estimate it.

## Integrity boundaries

- A signal contains only information available at its `as_of` timestamp.
- Outcomes are stored in a separate table and deliberately use later dated closes.
- Signal IDs are deterministic for model, version, security, timestamp, and source observation.
- Repeating an identical insert is idempotent. Different content under an existing signal ID raises `HistoricalSignalConflict`; model revisions therefore require a new version and cannot silently rewrite history.
- Directional correctness is undefined for neutral and abstained signals.
- Scorecards always expose sample and missing counts and are descriptive research evidence, not investment advice.

## Schema management

This repository manages schemas at repository startup rather than through standalone migration files. `SignalRepository.initialize()` follows that convention for both SQLite and Postgres and adds:

- `research_signals`, keyed by `signal_id`, indexed by security/as-of and model/version/as-of.
- `signal_outcomes`, keyed by `signal_id + horizon_trading_days`, with a foreign key to the signal and a status/horizon index.

Horizons are rows, not columns, so additional trading-day horizons require no redesign. JSON text preserves components, metadata, and evidence references across both supported databases.

## Extension points

Any deterministic or future AI analyst can emit the same `Signal` contract. Ensembles can identify their own model/version and preserve component signal references as evidence. Future simulation should consume persisted Signals through a policy boundary rather than call producers directly. The outcome engine accepts a `HistoricalPriceProvider`, keeping market-data acquisition outside signal generation and enabling network-free tests.

## Deferred

- Benchmark-relative return: there is no reliable benchmark history abstraction in the current application.
- Scheduled outcome collection: v0.1 provides the persisted-signal evaluation service but does not introduce a cron or worker.
- Simulated portfolios, options outcomes, model optimization, AI decisions, brokerage connectivity, and trading remain out of scope.
