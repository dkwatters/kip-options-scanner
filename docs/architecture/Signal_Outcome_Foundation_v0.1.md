# Signal and Outcome Foundation v0.1

## Decision

The foundation extends the existing append-oriented Research Repository pattern with a presentation-neutral `Signal`, a separate `SignalOutcome`, and a descriptive model-performance service.

The first producer reuses the existing deterministic Technical Analysis Model setup score (`technical-setup-score-v0.1`) without changing its calculation. Direction comes only from the TAM's existing directional `trend_state`: `bullish_alignment` / `constructive` map to positive conviction, `mixed` maps to neutral, and `deteriorating` / `bearish_alignment` map to negative conviction. Missing or unsupported trend evidence produces `abstain`. The adapter is versioned separately as `technical-setup-signal-v0.1.1`, preserving the original v0.1 adapter history rather than reinterpreting persisted Signals. Confidence remains absent because the source model does not estimate it.

Signal production is attached to the shared technical-observation application boundary rather than to an option-contract or page-specific workflow. Universe Analysis, Opportunity Discovery, and script-driven TAM/research scans archive successfully generated observations before deriving and atomically persisting the corresponding Signal batch from the same repository target.

## Integrity boundaries

- A signal contains only information available at its `as_of` timestamp.
- Outcomes are stored in a separate table and deliberately use later dated closes.
- Historical TAM generation retains dated closes, rejects history after `end_date`, conservatively uses only completed bars before the historical `end_date`, and never requests a live quote unless `end_date` is the current date. This prevents an intraday historical timestamp from seeing that session's later official close.
- Outcome start is the official close for the first U.S. equity trading session on or after the Signal's calendar date. Intraday Signals therefore use that later same-day close as the outcome baseline, not as Signal input.
- Every session through a horizon must have an observation; weekends and market holidays are excluded and missing sessions produce `missing_data` rather than substitution.
- Signal IDs are deterministic for model, version, security, timestamp, and source observation.
- Repeating an identical insert is idempotent. Different content under an existing signal ID raises `HistoricalSignalConflict`; model revisions therefore require a new version and cannot silently rewrite history.
- Directional correctness is undefined for neutral and abstained signals.
- Scorecards always expose sample and missing counts and are descriptive research evidence, not investment advice.

## Schema management

This repository manages schemas at repository startup rather than through standalone migration files. `SignalRepository.initialize()` follows that convention for both SQLite and Postgres and adds:

- `research_signals`, keyed by `signal_id`, indexed by security/as-of and model/version/as-of.
- `signal_outcomes`, keyed by `signal_id + horizon_trading_days`, with a foreign key to the signal and a status/horizon index.

SQLite enables foreign-key enforcement on every Signal Repository connection, matching Postgres orphan-rejection behavior.

Horizons are rows, not columns, so additional trading-day horizons require no redesign. JSON text preserves components, metadata, and evidence references across both supported databases.

## Persistence failure semantics

Research scan persistence and Signal persistence use separate existing repository transactions. Once a scan commits it is not rolled back by a later Signal error. Signals for that scan are written as one atomic batch: either every new Signal commits, or none of that batch does. The application reports this state explicitly as “scan archived, Signals not persisted” and retains the successful scan counts. After the Signal batch commits, later UI/session-state failures do not roll it back; both the scan and Signals remain durable.

## Extension points

Any deterministic or future AI analyst can emit the same `Signal` contract. Ensembles can identify their own model/version and preserve component signal references as evidence. Future simulation should consume persisted Signals through a policy boundary rather than call producers directly. The outcome engine accepts a `HistoricalPriceProvider`, keeping market-data acquisition outside signal generation and enabling network-free tests.

## Deferred

- Benchmark-relative return: there is no reliable benchmark history abstraction in the current application.
- Scheduled outcome collection: v0.1 provides the persisted-signal evaluation service but does not introduce a cron or worker.
- Simulated portfolios, options outcomes, model optimization, AI decisions, brokerage connectivity, and trading remain out of scope.
