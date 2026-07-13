# RCE Benchmark Library

## Purpose and Boundary

The RCE Benchmark Library is a versioned QA and reference subsystem for evaluating Research Conversation Engine research maps and candidate-universe proposals. It records what a human reviewer expects an RCE response to cover for a specific research question.

A benchmark is not ground truth. It may be incomplete, become stale, contain judgment calls, or reflect the limits of its source material. A benchmark security is not a recommendation, approved Research Universe member, production score input, or statement of security quality. Benchmark data never becomes a production Research Universe merely because it was imported.

The library is separate from RCE prompts and reasoning, SAM, OD, OAM, Study Protocols, Research Universe persistence, production scoring, and cloud research jobs. The importer writes only the four `rce_benchmark*` tables in the dedicated benchmark database.

## Data Model

- `rce_benchmark` holds the versioned question, domain, status, review metadata, and top-level source reference. `(benchmark_id, version)` is unique.
- `rce_benchmark_category` holds expected research-map areas and their roles.
- `rce_benchmark_security` holds reference entities, expectation levels, listing classification, rationale, and evidence summary.
- `rce_benchmark_source` holds document-level and page/section-level provenance plus the reviewed source SHA-256.

Child rows also carry `benchmark_version` so two versions can coexist without mixing category, security, or source records.

## Review and Approval Lifecycle

1. A reference document is received and deduplicated using document identity and SHA-256.
2. An editor converts it into one canonical JSON fixture. Production code does not parse PDFs.
3. A reviewer checks the exact question, category boundary, entity classifications, evidence summaries, listing status, caveats, page/section citations, source date, and source hash.
4. The benchmark remains `draft_pending_source_review` until those checks are complete. Approval records the reviewer and review notes and changes status according to the team's controlled vocabulary.
5. Any substantive correction creates a new version. Existing versions remain available for reproducible QA.
6. The reviewed fixture is dry-run, then transactionally applied.

The twelve v0.1 fixtures were structurally prepared from the sprint domain list. The source PDFs were not present in the workspace, so they deliberately retain draft status, placeholder source filenames, null page/date values, and explicit review caveats. They must not be represented as source-approved until the actual documents are attached and reviewed.

## Versioning and Provenance

`benchmark_id` is stable across revisions; `version` identifies a reviewable snapshot. The importer rejects an already-imported `(benchmark_id, version)` rather than overwriting it. `created_at` and `updated_at` record import time in UTC.

Every fixture includes at least one source row. `source_document`, `source_page`, `source_section`, `source_date`, `source_notes`, and `source_hash` preserve provenance. Identical source documents may provide multiple page references inside one benchmark. A directory that uses the same top-level source document to define multiple benchmark identities is rejected as a duplicate source definition and must be consolidated before import.

## Expected Inclusion Levels

Category `expected_status` values are:

- `core`: required research-map coverage.
- `adjacent`: related context that can improve boundary clarity.
- `optional`: useful but nonessential coverage.
- `excluded`: an explicit out-of-scope or negative-control area.

Security `expectation` values are:

- `must_include`: a central positive reference.
- `should_include`: a strong expected reference.
- `acceptable`: a defensible but nonessential reference.
- `must_exclude`: a negative, distressed, or off-scope reference that should not appear as a normal inclusion.
- `private_reference`: a private company retained for ecosystem context.
- `international_reference`: a non-domestic or international-listing reference retained explicitly.
- `fund_reference`: an ETF, trust, or other fund reference retained explicitly.

Private, international, and fund references are reported by the importer rather than silently removed. Missing tickers are expected for some private entities, but the importer reports every missing ticker or company name for review. Duplicate tickers are also reported across the import batch.

## Canonical Fixture Format

Fixtures live in `tests/fixtures/rce_benchmarks/`, one JSON object per benchmark. Each uses `schema_version: "1.0"` and contains:

- `benchmark`: metadata and the exact research question.
- `categories`: included, adjacent, optional, and excluded research-map categories.
- `securities`: entities, listing/public status, expectation, role, evidence, and notes.
- `benchmark_caveats`: limitations and review warnings.
- `sources`: page/section provenance and SHA-256.

The schema validator requires declared categories, controlled enum values, importance values from 1 through 5, nonempty rationale/evidence, and valid 64-character SHA-256 strings.

## Import Workflow

Validate all fixtures, report classifications, and perform no benchmark row writes:

```powershell
python scripts/import_rce_benchmarks.py --path tests/fixtures/rce_benchmarks --dry-run
```

Apply the entire directory in one transaction:

```powershell
python scripts/import_rce_benchmarks.py --path tests/fixtures/rce_benchmarks --apply
```

Use `--database PATH` to select a QA database. The default is `data/research/rce_benchmarks.sqlite`, which is intentionally different from the production research repository. Schema validation and duplicate-source checks happen before inserts. Duplicate versions and any database failure roll back the batch.

## Why Separation Matters

Benchmarks answer, “What did reviewers expect this RCE artifact to cover?” Production research data answers, “What population and observations were actually approved and run?” Combining them would allow editorial expectations to masquerade as user-approved universes, model evidence, or immutable truth. Separate files, tables, database defaults, and import commands preserve that boundary.
