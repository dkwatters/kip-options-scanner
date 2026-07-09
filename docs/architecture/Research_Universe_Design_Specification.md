# Research Universe Design Specification v0.1

## Purpose

This specification defines the Research Universe architecture before implementation.

It is a design document only. It does not change executable behavior, scoring, OD/OAM/SAM calculations, database schema, cloud jobs, or UI behavior.

---

## First-Class Concepts

### Research Conversation Engine

The Research Conversation Engine (RCE) is the guided workflow that translates a user's research question into a reviewable Research Universe Definition.

RCE interprets the user's Research Mission, proposes candidate universe membership, explains why each Candidate Security may be relevant, and requires user review before the universe is saved and snapshotted.

RCE does not:

- Score securities.
- Evaluate option contracts.
- Recommend trades.
- Modify Opportunity Discovery.
- Modify OAM scoring.
- Modify SAM calculations.
- Modify SAE or OAE behavior.
- Modify Evaluation Profiles or Study Protocols.
- Modify cloud jobs or database schema in v0.1 design.

### Research Mission

A Research Mission is the user's top-level research question, thesis, theme, or exploratory intent.

Examples:

- "I think AI infrastructure spending will keep growing."
- "Find companies exposed to power demand from data centers."
- "Help me research strong growth stocks in my watchlist."

The mission anchors RCE interpretation, but it does not define final universe membership until the user approves a Research Universe Definition.

### AI-Assisted Research Universe Definition

An AI-Assisted Research Universe Definition is a proposed Research Universe Definition produced by RCE from a Research Mission.

It should include:

- Structured mission interpretation.
- Proposed name and purpose.
- Candidate Securities.
- Inclusion Rationale for each candidate.
- Suggested boundaries and exclusions.
- Source notes or uncertainty notes when available.

It remains provisional until the user reviews, edits, names, and saves it.

### Candidate Security

A Candidate Security is a security proposed for possible inclusion in an AI-Assisted Research Universe Definition.

Candidate status means "possibly relevant to this mission." It does not mean the security is attractive, high quality, technically strong, optionable, liquid, or recommended.

### Inclusion Rationale

Inclusion Rationale is the short explanation attached to a Candidate Security that describes why it may belong in the proposed Research Universe.

The rationale is a review aid. It is not a score, ranking, forecast, suitability claim, or trading recommendation.

### User-Approved Research Universe

A User-Approved Research Universe is a Research Universe Definition after the user has reviewed, edited, named, and saved it.

Only user-approved definitions should proceed to snapshot creation and downstream research workflows.

### Market Universe

A Market Universe is the broad available population of securities that could be considered for research.

Examples:

- All optionable equities.
- S&P 500 constituents.
- Nasdaq 100 constituents.
- A manually curated market list.

The Market Universe is not the scan input by itself. It is the candidate boundary from which a Research Universe Definition may select securities.

### Research Universe Definition

A Research Universe Definition is a saved recipe for creating a Research Universe.

It records:

- Name and purpose.
- Static or dynamic definition type.
- Source Market Universe or candidate list.
- Static source reference, such as CSV or manual watchlist, when applicable.
- Dynamic generator rules and gates, when applicable.
- Refresh cadence or manual refresh expectation.
- Ownership notes and rationale.

Static examples:

- CSV-backed universe.
- Manual watchlist.
- Predefined index constituent file.

Dynamic examples:

- A generated universe built by Research Universe Generator rules.
- A bounded candidate list filtered by SAM-derived technical states.

### Research Universe Snapshot

A Research Universe Snapshot is the exact materialized list of securities used for a scan, Study Protocol observation, or research run at a specific time.

The snapshot must be persisted for reproducibility. Downstream workflows consume the snapshot, not the Research Universe Definition directly.

A snapshot should identify:

- `universe_snapshot_id`.
- `universe_definition_id`.
- Snapshot timestamp.
- Materialized ticker list.
- Source definition version or digest.
- Gate results or inclusion rationale when generated dynamically.
- Data freshness metadata when available.

### Research Universe Generator

A Research Universe Generator applies rules and gates to a Market Universe or bounded candidate list to produce a Research Universe Snapshot.

The generator may use SAM-derived values where applicable, such as RSI, MACD state, moving-average relationships, realized volatility, or trend state.

The generator does not:

- Evaluate option contracts.
- Fetch or score option chains.
- Modify OD behavior.
- Modify OAM scoring.
- Modify SAM calculations.
- Rewrite Study Protocol rules.

Its responsibility is population construction only.

### Research Universe Gate

A Research Universe Gate is a single inclusion or exclusion rule used by a Research Universe Generator.

Examples:

- RSI between 55 and 70.
- MACD state bullish.
- Price above SMA50.
- Average volume above threshold.
- Sector included or excluded.

Gates should be independently named, inspectable, and explainable. A generated snapshot should be able to record which gates were applied and, where practical, why each included security passed.

---

## Architecture Decisions

### RCE Produces Reviewable Artifacts, Not Model Output

RCE is upstream of research execution. It may propose an AI-Assisted Research Universe Definition, but the user must approve the definition before snapshot creation.

RCE output should be treated as structured product metadata:

- Mission interpretation.
- Candidate list.
- Inclusion rationale.
- User edits.
- Approval state.
- Saved universe name and purpose.

It should not be treated as SAM output, OAM output, OD output, Study Protocol evidence, or Research Repository conclusions.

### Static and Dynamic Universes Look Identical Downstream

Static and dynamic universes differ only before snapshot creation.

Once a Research Universe Snapshot exists, downstream workflows receive:

- Snapshot identity.
- Definition identity.
- Materialized ticker list.
- Observation timestamp and metadata.

Opportunity Discovery, SAM, OAM, OAE, SAE, Study Protocols, and the Research Repository should not branch on whether the snapshot came from a CSV file, manual watchlist, index list, or dynamic generator.

### OD Receives a Research Universe Snapshot

Opportunity Discovery should be invoked with a Research Universe Snapshot as its population boundary.

In RU-1, the existing CSV universe can be materialized into a snapshot before OD runs. OD can continue to iterate over tickers as it does today, but the archived scan should reference both:

- `universe_definition_id`
- `universe_snapshot_id`

This preserves current behavior while making the observed population explicit and reproducible.

### SAM Supports Generation Without Becoming the Generator

SAM remains the independent security-level characterization model. It may supply observable fields to a Research Universe Generator, but it does not own generation policy.

Allowed relationship:

- SAM computes or persists security technical observations.
- A generator reads eligible SAM fields as gate inputs.
- The generator decides membership according to a Research Universe Definition.

Disallowed relationship:

- SAM admitting or excluding securities directly.
- SAM changing OD filters or OAM scoring.
- SAE display scores becoming implicit gates without an explicit Research Universe Definition.

### Snapshots Preserve Reproducibility

Snapshots preserve reproducibility by fixing the exact ticker list observed at a point in time.

For static universes, the snapshot protects against later CSV edits or manual list changes.

For dynamic universes, the snapshot protects against changing market conditions, changing SAM observations, provider revisions, and future generator rule changes.

The minimum reproducibility requirement is the materialized ticker list plus definition identity. Stronger reproducibility adds rule versions, source data timestamps, candidate universe identity, and gate-level pass/fail evidence.

For RCE-created universes, stronger reproducibility also includes the user-approved name, mission summary, Candidate Securities, Inclusion Rationale, user edits, approval timestamp, and definition version or digest when available.

### RCE Workflow

The RCE workflow is:

User question -> RCE structured interpretation -> candidate universe proposal -> user review/edit/name -> Research Universe Definition -> Research Universe Snapshot -> SAM/SAE -> OD/OAM/OAE -> Research Repository

Workflow notes:

- The user question becomes a Research Mission.
- RCE produces a structured interpretation and a candidate universe proposal.
- Candidate Securities are displayed with Inclusion Rationale.
- The user may add, remove, rename, and edit before saving.
- Saving creates a Research Universe Definition.
- Snapshot creation fixes point-in-time membership before downstream analysis.
- SAM/SAE and OD/OAM/OAE consume the snapshot and remain independent of how the universe was proposed.

### Future UI for Universe Rules

A future Research Universe management UI should support:

- Starting from the Research Workspace mission input prompt.
- Displaying RCE structured interpretation.
- Previewing AI-assisted candidate universe proposals.
- Showing Candidate Securities with Inclusion Rationale.
- Editing, naming, approving, and saving the proposed universe.
- Viewing Research Universe Definitions.
- Viewing Research Universe Snapshots.
- Creating static definitions from CSV or manual ticker lists.
- Selecting a definition for Opportunity Discovery.
- Previewing dynamic generator results before snapshot creation.
- Defining gates through controlled fields, operators, and values.
- Showing gate explanations and expected data dependencies.

The UI should save definitions and create snapshots. It should not silently mutate active Study Protocols, OAM thresholds, SAM calculations, or prior snapshots.

### Avoiding Expensive Full-Market Scans Initially

Initial dynamic generation should not attempt to scan the entire market.

RU-3 should start with bounded candidate lists, such as:

- Existing Technology Growth AI universe.
- S&P 500 constituents.
- Nasdaq 100 constituents.
- Manually curated optionable equities.
- A small provider-supported watchlist.

This avoids excessive quote/history requests, provider throttling, slow UI behavior, and unreliable scheduled runs.

### Candidate Market Universe Data Sources

Candidate Market Universes may need:

- Static CSV files for curated lists.
- Index constituent sources for S&P 500 or Nasdaq 100.
- Tradier or another provider for optionable status, quotes, history, and liquidity context.
- Sector and industry reference data.
- Average volume and price history.
- Corporate action and symbol-change awareness for long-lived snapshots.

The first implementation should prefer static curated candidate lists and already available price-history inputs before adding broad provider enumeration.

### Provider and Rate-Limit Risks

Tradier and other providers introduce risks:

- Rate limits when retrieving quotes, history, expirations, or option chains for large candidate lists.
- Latency and timeout risk for UI-triggered generation.
- Incomplete or delayed index constituent and optionable universe coverage.
- Provider-specific symbol formats and stale delisting or corporate-action data.
- Cost or quota increases when moving from bounded lists to broad market universes.

Mitigations:

- Keep RU-3 bounded.
- Cache candidate lists and SAM inputs.
- Separate universe generation from option-chain evaluation.
- Avoid fetching option chains during universe generation.
- Record provider and data freshness metadata in snapshots when available.
- Prefer scheduled or background generation for larger universes.

---

## Phased Implementation Plan

### Phase RCE-1 - Research Conversation Workflow Design

Document RCE as the upstream workflow for translating a user question into a user-reviewed Research Universe Definition.

Expected behavior impact: documentation only. No executable implementation, scoring change, OD change, OAM change, SAM change, Evaluation Profile change, Study Protocol change, cloud job change, or database schema change.

### Phase RU-1 - Static Definitions and Snapshots

Formalize static Research Universe Definitions.

Persist Research Universe Snapshots for existing CSV universes.

Associate scans with:

- `universe_definition_id`
- `universe_snapshot_id`

Expected behavior impact: no change to OD, OAM, SAM, scoring, ranking, or UI behavior beyond explicit metadata persistence.

### Phase RU-2 - Research Universe Management UI

Add Research Universe management UI.

The UI should:

- Show definitions.
- Show snapshots.
- Allow selecting a universe for OD.
- Display definition metadata and latest snapshot metadata.

Expected behavior impact: selection and inspection only. It should not alter model scoring or generator behavior.

### Phase RU-3 - Dynamic Generator With Existing SAM Fields

Add Research Universe Generator using existing SAM fields.

Start with a bounded candidate list, not the entire market.

Initial gates should use existing persisted or computable SAM fields, such as RSI, MACD state, price versus SMA50, trend state, and realized volatility. The generator should produce snapshots that OD consumes like any static snapshot.

Expected behavior impact: new population-construction capability. No option-contract evaluation inside the generator and no OAM scoring changes.

### Phase RU-4 - User-Defined Gates

Add UI support for user-defined gates.

Gate controls should use explicit fields, operators, values, inclusion/exclusion behavior, and validation. Saved definitions should remain inspectable and versionable.

Expected behavior impact: user-controlled universe definition, still snapshot-mediated before downstream workflows run.

---

## Non-Goals for v0.1

- No executable implementation.
- No database schema change.
- No OD/OAM/SAM calculation change.
- No option-contract evaluation inside universe generation.
- No security scoring inside RCE.
- No trade recommendations.
- No full-market scan.
- No automatic mutation of Study Protocols.
- No recommendation, suitability, trading, or order-routing behavior.
