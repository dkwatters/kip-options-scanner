# Typed Signal & Outcome Families v0.2

## Purpose

The v0.1 Signal contract described directional analytical conclusions. v0.2 adds an explicit analytical dimension so the same immutable evidence framework can also represent models that do not answer a directional question. The initial families are intentionally limited to `directional` and `volatility`.

This is an architectural release. It does not add a volatility forecast, regime model, GARCH variant, AI analyst, ensemble, simulation, options backtest, scheduler, or trading behavior.

## Signal family and direction semantics

Every Signal has a `signal_family`:

- `directional` retains the v0.1 `bullish`, `neutral`, `bearish`, and `abstain` directions and conviction rules.
- `volatility` requires `direction = not_applicable` and zero conviction.

The states are deliberately distinct:

- `neutral` means a directional model evaluated direction and found no directional preference.
- `abstain` means a directional model could not or chose not to provide a conclusion.
- `not_applicable` means direction is outside the model's analytical domain.

Volatility is orthogonal to direction: high or low volatility does not imply bullish, bearish, neutral, or abstain.

An explicit `not_applicable` state was selected instead of nullable direction. The v0.1 SQLite schema has a `NOT NULL` direction column; nullability would require reconstructing existing tables. The explicit state permits a safe additive bootstrap while preventing non-directional observations from masquerading as neutral or abstain.

## Outcome family and compatibility

Every persisted outcome has an `outcome_family` and a generic JSON `components` payload:

- `return` is the unchanged v0.1 5/20/60 verified U.S. equity trading-session outcome.
- `volatility` reserves a typed contract for later realized-volatility, forecast-error, regime-persistence, regime-transition, or absolute-movement evidence. Those values can be carried in `components` without pretending they are returns or adding premature top-level columns.

Compatibility is explicit:

| Signal family | Compatible outcome family | v0.2 evaluation behavior |
| --- | --- | --- |
| `directional` | `return` | Existing return evaluation and directional correctness |
| `volatility` | `volatility` | Contract and persistence only; no invented metric |

Return evaluation rejects volatility Signals. Volatility outcomes cannot carry directional correctness. Repository persistence rejects a known Signal/outcome family mismatch.

## Backward compatibility

Bootstrap adds `research_signals.signal_family` with deterministic default `directional`, `signal_outcomes.outcome_family` with deterministic default `return`, and outcome `components` with deterministic default `{}`. Existing rows therefore retain their v0.1 meanings without reinterpretation or destructive data migration. SQLite adds missing columns and indexes during repository initialization. Postgres uses `ADD COLUMN IF NOT EXISTS` with the same defaults.

The Technical Setup producer remains `technical-setup-score · technical-setup-signal-v0.1.1`. Its identity inputs, trend-state mapping, conviction, point-in-time behavior, and return outcomes are unchanged.

## Architecture-validation producer

`volatility-family-smoke · 0.1` is an experimental deterministic producer. It copies only the already-dated TAM `volatility_state` into Signal components, performs no provider call or new calculation, and makes no forecast or predictive claim. It is not wired into production scans in v0.2; tests use it to prove non-directional validation, identity, persistence, and presentation without changing v0.1 user workflows.

## Model Lab

Model Lab groups Signals by family before model/version selection. Directional models retain the v0.1 distribution and return scorecard. Volatility Signals show family, `N/A` direction, count, and an explicit notice that volatility outcome metrics are not implemented. They never enter directional tiles, coverage, or directional hit-rate denominators.

## Extension path

Future families can extend the enums and compatibility map while retaining the immutable Signal envelope and JSON components/metadata. Family-specific analytical values remain in those existing structures until repeated production use justifies a dedicated top-level field. Future outcome services may add typed payload structures without changing the meaning of historical return outcomes.

## Deferred scope

GARCH, EGARCH, GJR-GARCH, volatility regimes, implied-volatility comparison, options volatility edge, AI/filings/earnings/catalyst analysts, ensembles, simulation, portfolio construction, position sizing, brokerage, trading, options backtesting, scheduled observation changes, and model optimization or promotion remain out of scope.
