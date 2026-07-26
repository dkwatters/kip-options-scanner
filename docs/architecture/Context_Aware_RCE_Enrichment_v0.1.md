# Context-Aware RCE Enrichment v0.1

## Product intent

Context-Aware RCE Enrichment treats the existing deterministic seed universe as authoritative known context and asks what material public-company coverage is missing. Seeds are never regenerated as recommendations. Enriched companies are pending suggestions until a human adds or rejects them.

This is the bounded flow:

```text
User inputs → Discovery Context → Context-Aware RCE Enrichment
→ pending suggestions → human Add / Reject → approved membership → analysis
```

## Versioned boundaries

- Request: `research-universe-enrichment-request-v0.1`
- Provider behavior/prompt: `rce-context-aware-universe-enrichment-v0.1`
- Response: `research-universe-enrichment-response-v0.1`
- Discovery Context: `research-universe-discovery-context-v0.1`
- Discovery Lenses: `discovery-lens-v0.1`
- Deterministic contract benchmark: `rce-enrichment-benchmark-v0.1`

`ResearchUniverseEnrichmentRequestV01` carries the complete Discovery Context, research question, ordered seed members and provenance, optional predefined-universe identity, all active lenses, known-member exclusion keys, workflow marker, evidence requirements, and candidate constraints. It projects to the existing provider-neutral `ResearchConversationRequest`; flat anchors remain only a compatibility projection and are not the authoritative context.

`ResearchUniverseEnrichmentResponseV01` contains normalized `RCEEnrichmentCandidateV01` suggestions, the provider response, deterministically suppressed seed duplicates, and warnings. Candidate UUIDv5 identity is derived from response version, Discovery Context identity, and normalized company identity.

## Omission-oriented provider behavior

The new OpenAI behavior is isolated from the prior prompt version. It directs the provider to:

- treat seeds as known and exclude them;
- investigate material omissions rather than reconstructing the universe;
- use public disclosures, filings, and reputable public industry sources without assuming paywalled access;
- apply Discovery Lenses as research directions rather than quotas;
- avoid weak thematic adjacency;
- return material coverage rationale, related seed keys, lenses, and actual evidence references;
- describe every result as pending, never approved.

The six lenses are direct competitors, industry landscape peers, value-chain relationships, adjacent beneficiaries, substitution/disruption threats, and recurring cross-seed dependencies. Multiple lenses are retained in source order after deterministic deduplication.

Normalization rejects candidates lacking a supported lens, evidence reference, or reason. It suppresses seed matches and repeated provider candidates. This boundary validates evidence presence and provenance; it does not independently prove source truth.

## A/B/C/D behavior

All four Launchpad combinations construct `ResearchUniverseDiscoveryContextV01` and enter `ResearchUniverseEnrichmentService`:

| Path | Enrichment context |
|---|---|
| Question only | Question, empty known-member set, six lenses |
| Question + manual | Question, deliberate manual seeds/provenance, exclusions, six lenses |
| Question + topic | Question, topic identity and authored seed membership/provenance, exclusions, six lenses |
| Question + manual + topic | Question, deduplicated topic/manual union with multi-source provenance, exclusions, six lenses |

The topic branch no longer short-circuits before provider invocation. Manual and topic context are both serialized into the current request.

## Stored-topic fallback

Stored benchmark/topic candidates are an explicit offline/availability fallback, not the primary enrichment path and not extra seed membership. They are used only when a selected topic's enrichment returns no eligible normalized suggestion. `stored_topic_fallback_used` records the decision. When enrichment returns candidates, stored candidates are ignored. Benchmark corpus remains unchanged.

## Evidence and provenance

Every normalized candidate receives `rce_discovered` provenance, stable candidate/source identity, lenses, related seed identities, reason, evidence references, duplicate status, and `pending` state. The provider-free mock uses clearly labeled `mock-fixture://` references; these validate contract plumbing and are not claims of real-world evidence.

Promotion retains the original RCE source record and adds a membership source record containing both `rce_discovered` and `promoted_candidate` provenance plus the original candidate identity, lenses, and evidence. Rejection changes review disposition only and does not alter approved membership.

## Universe version semantics

Universe identity remains stable. A revision increments `ResearchUniverse.version` exactly when the approved matching-key set changes:

- manual member added: increment;
- approved member removed: increment;
- pending RCE candidate promoted: increment;
- pending candidate rejected: no increment;
- reopening/rebuilding without membership change: no increment;
- idempotent duplicate add: no increment.

Existing snapshot comparison rules are unchanged. Future snapshots naturally carry the membership version present at analysis time. No historical migration is performed.

## Benchmark methodology and results boundary

The legacy RCE fixture corpus and deterministic scoring configuration are unchanged. Context-aware contract diagnostics are separate because existing scoring does not measure provenance, lenses, evidence presence, seed duplicates, or sensitivity. `tests/fixtures/rce_enrichment_scenarios_v01.json` provides A/B/C/D cases plus declared checks for seed deduplication, anchor/topic sensitivity, omission behavior, lens attribution, evidence support, drift resistance, multi-lens support, pending state, and stable provenance.

`scripts/run_rce_enrichment_benchmarks.py` runs the four cases through the provider-free mock and reports candidate count, suppressed seed duplicates, returned duplicate rate, evidence/lens/provenance/pending completeness, multi-lens count, and explicit limitations. It does not calculate or alter the legacy overall score.

Mock runs establish deterministic contract behavior, not qualitative improvement. Relevant recall, unsupported-candidate truth, thematic drift quality, real evidence quality, live latency, token use, and API cost require a reviewed live benchmark. No live run is authorized by this sprint request.

## Rollout and safety boundaries

The Launchpad/review UI adds only compact lenses, related-seed count, and evidence/support details. Seeds remain included and suggestions remain pending. No RCE result is silently promoted.

This change does not modify SAM, production scoring, Opportunity systems, Study Protocols, technical analysis, snapshot comparison, deterministic change detection, Morning Coffee, scheduled scans, or cloud jobs.
