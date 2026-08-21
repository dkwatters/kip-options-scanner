# Research Universe Discovery Context Foundation v0.1

## Scope

This Sprint A artifact records current Research Launchpad behavior and introduces a deterministic context boundary for a later, benchmarked enrichment sprint. It does not change RCE prompts, reasoning, provider behavior, candidate generation, scoring, analysis, or any downstream research system.

The implementation boundary is `ResearchUniverseDiscoveryContextV01` in `src/research_universe_discovery_context.py`. Launchpad persists its serialized form under `ResearchUniverse.provenance["discovery_context"]` when the initial under-review universe is saved.

## Current execution audit

The active Launchpad is `render_research_universe_builder()` in `src/research_universe_builder_page.py`. The four requested combinations follow these paths:

| Path | Deterministic starting membership | Manual included | Topic included | Duplicate handling | Discovery execution | Request received by live RCE | Suggestions and distinction |
|---|---|---:|---:|---|---|---|---|
| A. Question only | Empty | n/a | n/a | n/a | `_provider_suggestions()` constructs the configured provider and calls `ResearchConversationService.interpret_request()` | Trimmed question; empty `anchor_companies`; `request_origin=general_user`; context only `{workflow: research_universe_builder}`; current prompt version/timestamp defaults | Provider candidate securities become `RCE_GENERATED`, pending suggestions (`in_rce_suggestions=True`, `in_starting_companies=False`) |
| B. Question + manual tickers | Resolved/manual records are included immediately | Yes | No | Input parser suppresses repeated ticker tokens; review assembly merges ticker/name matches and retains source records | Same provider-backed path as A | Trimmed question plus manual tickers in `anchor_companies`; same origin/workflow context | Provider candidates are suggestions; an overlap is one candidate with both starting and suggestion flags and all matching source records |
| C. Question + predefined topic | Authored source-corpus members for the selected established topic are included immediately | No | Yes | Review assembly deterministically merges ticker/name matches | **No live RCE/provider call.** `_stored_suggestions()` reads the stored RCE candidate corpus for that benchmark topic | None | Stored corpus candidates are projected as `RCE_GENERATED` suggestions; overlaps retain both flags/source records |
| D. Question + manual tickers + predefined topic | Union of authored topic records and resolved manual records | Yes | Yes | Manual parsing suppresses repeated input; assembly merges duplicate ticker/name matches and preserves matching source records | **No live RCE/provider call.** Same stored-corpus shortcut as C | None; neither the question nor manual anchors are sent to RCE in this branch | Same stored suggestions as C; manual/topic members remain included and stored suggestions remain pending unless they overlap |

### Detailed construction behavior

Topic members come from `RCEBenchmarkExplorerService.authored_source_candidates()` and are marked `UniverseSource.CURATOR_AUTHORED`. Manual inputs pass through the ticker-only parser and resolver and are marked `UniverseSource.USER_ENTERED`. Before a live provider request, manual entries are resolved against topic/saved metadata without market data and all starting record ticker-or-name values are projected into the existing RCE `anchor_companies` tuple. After discovery, manual records are resolved again against deterministic known metadata, provider suggestions, and—when configured—the existing market-data identity lookup. That lookup is existing identity behavior, not candidate discovery.

`ResearchUniverseReviewService.assemble()` groups matches using normalized ticker keys when available and conservative exact/legal-suffix name aliases otherwise. It emits one candidate per match group and retains every matching `UniverseSourceRecord`. Starting records default to `INCLUDED`; suggestion-only records default to `PENDING`; ambiguous identity conflicts require identity review. `in_starting_companies` and `in_rce_suggestions` distinguish membership roles.

Current membership provenance is represented indirectly by `UniverseSourceRecord.source`, `source_reference`, and retained `source_records`, plus candidate role flags and a free-form universe-level provenance mapping. It did not previously provide the product vocabulary `predefined_universe` / `manual_entry` or a versioned discovery-context contract.

The initial universe becomes durable immediately after assembly, before navigation to review, through `research_universe_repository_from_env().save(universe)`. It is saved in `UNDER_REVIEW` state. Review changes rebuild and save the same `universe_id`; current revision code also preserves the existing version value (normally 1). Analysis handoff and persisted snapshots carry that universe ID and version, so identity remains stable through review and analysis. The lack of version increments for membership revisions is an architectural concern for Sprint B.

### Latency finding

The observed 8–12 second question-only latency is consistent with the configured live provider path: A (and B) calls provider-backed RCE synchronously. Selecting an established topic selects a deterministic shortcut: C and D do not construct or call the configured RCE provider and instead read already-stored benchmark RCE candidates. Therefore the nearly instantaneous mixed topic/manual execution is a real live-provider/RCE bypass, not merely a rendering difference. It still supplies stored historical RCE suggestions, which can make the result look RCE-backed despite no request occurring for the current question.

## Discovery Context v0.1

`ResearchUniverseDiscoveryContextV01` contains:

- fixed schema identity `research-universe-discovery-context-v0.1`;
- deterministic UUIDv5 `context_identity`, derived from normalized supplied context rather than creation time;
- trimmed research question;
- optional predefined-universe identity, name, and source references;
- normalized manual input tokens;
- combined deterministic seed universe;
- the full ordered Discovery Lens vocabulary and its version;
- timezone-aware creation timestamp and trace metadata.

Seed construction is pure and performs no I/O or AI/provider call. Predefined records are processed first, followed by manual records. Members are deduplicated by the canonical existing normalized matching key. First occurrence fixes order; later duplicate sources add provenance. Member identity is a stable UUIDv5 of schema version and matching key. Where an existing resolved ticker/identifier exists, it remains the member identifier.

Question-only context is valid and has an empty seed universe. No provenance is invented for an absent or unknowable source.

## Membership provenance

`MembershipProvenanceV01` contains a typed source, optional stable source identity, and optional source reference. A seed member owns an ordered tuple of provenance records and may therefore have multiple sources. For example, NVDA occurring in both a topic and manual input is represented once with both `predefined_universe` and `manual_entry` provenance.

The versioned vocabulary supports:

- `predefined_universe`
- `manual_entry`
- `rce_discovered`
- `promoted_candidate`
- `recovered_snapshot`
- `compatibility_import`

Only the first two are assigned by this Sprint A seed builder. The others reserve explicit future boundaries; historical records are not migrated and unknown history is not guessed.

## Discovery Lens vocabulary v0.1

The fixed ordered vocabulary version is `discovery-lens-v0.1`:

1. `direct_competitors` — companies directly competing with important seeds.
2. `industry_landscape_peers` — companies co-occurring in credible classifications, market-share work, analyst landscapes, competitive evaluations, and comparable public research.
3. `value_chain_relationships` — critical suppliers, customers, enabling technologies, infrastructure dependencies, distributors, and other material value-chain participants.
4. `adjacent_beneficiaries` — companies materially exposed to the thesis without necessarily sharing its conventional industry classification.
5. `substitution_disruption_threats` — companies or technologies capable of replacement, displacement, commoditization, or material ecosystem change.
6. `cross_seed_dependencies` — companies, technologies, suppliers, customers, or ecosystem participants recurring across independent seed research paths.

This sprint defines names and semantics only. No lens research logic or RCE prompt consumption is implemented.

## Future candidate boundary

`FutureRCECandidateV01` names the non-instantiated Sprint B boundary: deterministic candidate identity; company and ticker/identifier; one or more Discovery Lenses; related stable seed-member identities; reason discovered; evidence references; typed candidate provenance; optional support/confidence metadata; and schema version `research-universe-discovery-candidate-v0.1`.

Sprint A creates no instances, makes no evidence claims, and does not promote anything into approved membership. Sprint B must define deterministic candidate identity inputs and evidence/support validation before production candidate creation.

## Product semantic and intended consumer behavior

The seed universe is known user context, **not** a request for RCE to regenerate already-known companies. A future enrichment consumer should ask: “What might this existing Research Universe be materially missing?”

Both predefined members and manual tickers must be available as omission-discovery context. Manual entry has additional semantic importance because it is deliberate user context and should seed future competitor, ecosystem, value-chain, adjacency, disruption, and cross-seed investigation. This is a Sprint B consumer requirement, not current RCE behavior.

## Architectural flow

```text
User Inputs
    ↓
Deterministic Seed Universe
    - predefined members
    - manual members
    - deduplicated
    - provenance preserved
    ↓
Research Universe Discovery Context
    - research question
    - seed universe
    - Discovery Lenses
    - provenance
    ↓
[Sprint A stops here]
    ↓
Future RCE Enrichment
    - omission-oriented discovery
    - seed-aware research
    - evidence-backed candidate generation
    ↓
Suggested Candidates
    ↓
Human Review / Add / Reject
    ↓
Approved Research Universe
    ↓
Universe Analysis
```

## Sprint B concerns and recommended scope

Before implementation, resolve these concerns explicitly:

1. Established-topic launches currently bypass current-question RCE and reuse stored benchmark output. Sprint B must decide whether to replace that shortcut, augment it, or retain it as an offline mode, then benchmark the chosen behavior.
2. Current live RCE receives only question, flat anchor strings, and a workflow marker. It does not receive source identities, seed provenance, topic identity, lens vocabulary, or the structured combined seed universe.
3. A selected topic causes the typed question and deliberate manual entries to have no influence on suggestion generation.
4. Universe revision currently keeps version 1 while membership changes. Sprint B should define whether discovery-context/candidate review revisions require version increments or a separate immutable proposal/run identity.
5. Manual identity resolution may perform a market-data quote lookup after suggestions are obtained. Sprint B should keep identity resolution distinct from discovery and specify failure/latency behavior.
6. The broader UI also supports compatibility CSV continuation. Its source should eventually map to `compatibility_import`, rather than being conflated with a predefined product universe.

Recommended exact Sprint B scope: consume `ResearchUniverseDiscoveryContextV01` at a new provider-neutral enrichment boundary; add an explicitly versioned omission-oriented RCE request/prompt and response contract; research across the six lenses using seed identities/provenance; require evidence-backed `FutureRCECandidateV01` output; deterministically deduplicate candidates against seeds and each other; preserve current seeds as approved and all discovered records as pending; add human Add/Reject transitions with `rce_discovered` and `promoted_candidate` provenance; benchmark A/B/C/D and topic/manual sensitivity before changing the Launchpad branch; and make rollout/fallback behavior explicit. Do not change downstream analysis, scoring, SAM, Opportunity systems, technical analysis, snapshots, jobs, or Morning Coffee.
