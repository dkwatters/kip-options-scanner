# Universe Analysis Snapshot Persistence v1

## Purpose

This layer durably stores the already validated `UniverseAnalysisSnapshotV1` artifact. It records trustworthy point-in-time history; it does not compare, reinterpret, or generate prose from snapshots.

## Immutable envelope

The `universe_analysis_snapshots` table stores indexed identity and ordering metadata plus the complete canonical JSON snapshot. The JSON payload remains authoritative for round-trip reconstruction. A saved `snapshot_id` cannot be overwritten:

- the same ID and identical canonical payload is an idempotent success;
- the same ID and different payload is an explicit conflict.

The envelope contains `snapshot_id`, schema and universe identity/version, membership digest, analysis run ID, status, observation/completion/persistence timestamps, analysis/scoring/presentation versions, and `snapshot_json`.

Indexes support universe/version history and unique analysis-run identity. Snapshot internals are intentionally not normalized in v1.

## Repository API and ordering

The backend-neutral repository supports save, get by ID, list by universe and optional version, latest completed snapshot, the next older retrieval candidate, and a compact history summary for diagnostics.

History order is deterministic:

1. `observation_as_of DESC`;
2. `completed_at DESC`;
3. `snapshot_id DESC`.

The previous-candidate method only retrieves the next older record. It does not claim comparability; future comparison policy must evaluate membership and behavior versions.

## Lifecycle and failure policy

After exact-universe technical execution and ledger reconciliation, the lifecycle loads only the new run's technical rows, builds and validates `UniverseAnalysisSnapshotV1`, and saves it. A snapshot ID is exposed to session diagnostics only after persistence succeeds.

Persistence failure does not invalidate or hide a successfully reconciled current analysis. The current run remains the page's authoritative display input, while the application explicitly warns that durable history was not saved. Invalid or unreconciled analysis never produces a completed snapshot.

## Legacy limitation

Existing technical scans are not backfilled or reinterpreted. They lack the exact membership ledger, universe/version envelope, behavior manifest, and raw/derived snapshot boundary. Historical snapshot availability begins with valid v1 artifacts written through this repository.

## Future seam

The repository can retrieve the latest snapshot, ordered history, and a prior candidate with exact universe, membership, provenance, and behavior-version context. Snapshot Comparison and Change Detection remain separate future layers.
