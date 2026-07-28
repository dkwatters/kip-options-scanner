# Research Universe Canonical Candidate Group Contract v0.1

Status: Proposed implementation contract  
Scope: Research Universe review assembly, persistence, and downstream handoff  
Non-goals: RCE generation or reasoning changes, fuzzy matching, scoring changes, snapshot repair, and historical-data mutation

## Purpose

A Research Universe is durable only if each included member has one stable identity. Source evidence may arrive through manual input, validated market identifiers, RCE suggestions, saved universes, or historical names and tickers. Those records can describe the same security, but they are not interchangeable merely because their names resemble one another.

This contract defines when source records may form one canonical candidate, when they must remain separate, and when canonicalization becomes final. It is designed to preserve supported canonical-name promotion such as a manual “Zscaler” entry joining a uniquely validated `ZS` suggestion, while preventing an unresolved historical ticker such as `CSG` from becoming `COHR` based only on name similarity.

The central rule is:

> Canonicalization produces an exclusive, validated partition of source evidence before candidate disposition or `ResearchUniverse` construction. Downstream components consume that partition and never repair or reinterpret it.

## 1. Canonical candidate group

A canonical candidate group is the complete, non-overlapping set of source records that the available deterministic evidence establishes as referring to one logical company or security.

Every group has:

- One canonical identity key.
- Zero or one canonical security identity.
- One canonical display name.
- Zero or one current ticker or supported identifier.
- One identity status: resolved, unresolved, or ambiguous.
- An ordered, deduplicated collection of source records and provenance.
- A disposition assigned only after the group is final.

For a resolved public security, the preferred identity is a stable security identifier when the domain supports one. Until such an identifier exists, a validated normalized ticker is the canonical key. A name key is used only for an unresolved entity that has not been mapped to a security.

Canonical identity follows this deterministic precedence:

1. A stable validated security identifier, when the domain and provider support one.
2. A validated normalized current ticker when no stable security identifier is available.
3. A normalized unresolved name key only when no validated security identity or ticker exists.
4. Raw display names and raw tickers remain provenance and must never independently serve as canonical identity after normalization.

A lower-priority identity may be refined to a higher-priority identity when new deterministic evidence becomes available. A raw or historical ticker does not outrank a validated current ticker, and a name key cannot coexist as a second canonical candidate after it has been authoritatively mapped to a resolved security. This precedence establishes how identity is represented; it does not authorize any merge unsupported by Section 2.

Legal-name aliases and historical names are evidence attached to a canonical group; they are not independent canonical identities once an authoritative mapping has been established. Conversely, name similarity is not itself an authoritative mapping.

## 2. Evidence allowed in one group

Evidence may belong to one group when at least one of these deterministic conditions holds:

1. **Exact validated security identity.** Records resolve to the same stable security identifier.
2. **Exact validated current ticker.** Records independently validate to the same current ticker and no security-level conflict exists.
3. **Explicit validated correction.** An identity validator records that a raw name or ticker was corrected to the group’s canonical security, with correction status and supporting provenance.
4. **Authoritative historical relationship.** Evidence explicitly establishes a former ticker, renamed issuer, acquisition, merger, or delisting relationship to the canonical security.
5. **Unique canonical-name promotion.** A tickerless manual entry matches exactly, or through the existing conservative legal-suffix alias rule, one and only one resolved candidate. The manual entry expresses membership intent; the resolved candidate supplies security identity.
6. **Equivalent unresolved name evidence.** Multiple tickerless, unresolved records have the same normalized name or conservative legal-suffix alias and no record supplies a conflicting security claim.

Source type does not change identity truth. Manual entry may express membership intent, but it does not make an unsupported ticker mapping valid. RCE evidence may contribute discovery rationale and provenance, but it does not become resolved without deterministic validation.

Every source record must be assigned to exactly one group. A record cannot lend resolution, starting-company status, or disposition to two candidates.

## 3. Finalization point and ownership

Canonicalization becomes final during review-domain assembly, before dispositions are computed and before a `ResearchUniverse` object is constructed.

The required sequence is:

1. Normalize source evidence without discarding raw values.
2. Establish authoritative security mappings and explicit corrections.
3. Partition all source records into exclusive canonical groups.
4. Validate group uniqueness and source ownership.
5. Construct one candidate per group.
6. Apply default and explicit dispositions to the finalized candidates.
7. Validate the complete candidate collection.
8. Construct the `ResearchUniverse`.
9. Persist the already-canonical model.

Persistence is a validation boundary, not the canonicalization owner. Repository save must reject a universe that violates this contract. Repository load must restore the persisted canonical candidates without rerunning a changing identity algorithm over flattened evidence. If compatibility reconstruction is unavoidable for legacy payloads, it must use a versioned migration that produces a new validated representation; ordinary reads must not silently rewrite identity.

After `ResearchUniverse` construction, downstream components must never re-canonicalize:

- Review presentation displays candidate identity and evidence.
- Downstream handoff copies finalized included candidates.
- Analysis preflight assigns availability status.
- The execution ledger preserves one row per member.
- Snapshot construction records the same member population.
- Comparison matches snapshots using the persisted canonical identity.

These layers retain duplicate validation as defense in depth, but they fail on corruption rather than merge, discard, rename, or choose between members.

## 4. Permitted merges

### Manual ticker input

A manually supplied ticker may merge into an existing group only when the ticker is an exact normalized match or deterministic validation resolves both records to the same security. Manual entry provides explicit inclusion intent but cannot override a conflicting validated security.

### Manual tickerless name

A tickerless manual name may merge with a resolved candidate when:

- The normalized exact name or conservative legal-suffix alias matches.
- Exactly one resolved candidate is eligible.
- No supplied ticker or security claim conflicts with that candidate.
- No competing resolved candidate shares the same alias.
- The raw manual value remains in provenance.

Thus `Zscaler` may merge with uniquely validated `Zscaler, Inc. / ZS`. The resulting candidate is `ticker:ZS`, contains both source records, and may be included because of the manual membership intent.

If two resolved candidates are plausible, the manual record remains separate or the affected records form an ambiguous review case. No first-row-wins rule is permitted.

### RCE suggestions and aliases

A resolved RCE suggestion may merge through exact validated security or ticker identity. A tickerless RCE suggestion may merge by unique canonical name only when it makes no conflicting security claim and repository identity policy explicitly permits name-only evidence attachment.

An RCE suggestion carrying a raw ticker that failed validation is not equivalent to a genuinely tickerless name. That raw ticker is material conflicting evidence and must be preserved.

### Historical names and tickers

Historical evidence may merge only when an authoritative or explicitly validated relationship connects it to the current canonical security. Acceptable evidence includes a recorded ticker change, issuer rename, acquisition, merger, or other supported corporate-action mapping.

A legal-suffix alias is insufficient to infer a historical-security relationship.

## 5. Evidence that must remain separate

Evidence remains separate pending review when:

- A supplied ticker is unresolved, rejected, unsupported, or conflicts with a validated ticker.
- Two validated securities share the same or similar company name.
- A name alias matches more than one resolved candidate.
- A historical ticker lacks an authoritative mapping to the current issuer.
- Identity validation produced no normalized security identity.
- Merging would cause one source record to appear in multiple groups.
- Merging would transfer starting-company status or an included disposition from one identity to another.
- The evidence indicates materially different securities, share classes, issuers, or corporate histories.

For the COHR case, `Coherent, Inc. / CSG` must not merge into `Coherent Corp / COHR` based only on the conservative name alias. The RCE record supplied `CSG`, validation did not correct it, and no authoritative relationship mapped it to COHR. It must remain a separate unresolved or ambiguous review candidate until deterministic validation establishes the relationship.

If later evidence explicitly corrects `CSG` to `COHR`, canonicalization may merge the groups during an intentional review revision. The revision must preserve the raw `CSG` value, correction result, source provenance, and universe-version transition.

## 6. Idempotence guarantees

Canonical assembly is a deterministic, idempotent operation over the same ordered evidence and decisions.

For an unchanged universe:

```text
assemble → save → load
```

must preserve:

- Candidate count and ordering.
- Canonical identity keys.
- Canonical names, tickers, and identity statuses.
- Source-record ownership.
- Source-record count and provenance.
- Dispositions and comments.
- Approved membership.
- Universe version.

Reconstruction must never multiply source evidence. Flattening overlapping candidate evidence and reassembling it is prohibited because it loses ownership boundaries and can amplify records on every load.

If an explicit revision adds evidence, canonical groups may change only as a deterministic consequence of that new evidence. A membership-changing merge or split must produce the repository’s normal universe-version transition. Merely saving or loading cannot change version or identity.

### Identity-confidence monotonicity

Canonicalization may refine identity confidence only when new deterministic evidence is introduced. Save, load, serialization, deserialization, display, handoff, or ordinary reassembly must not reduce or otherwise alter identity confidence. In particular:

- Resolved must not become unresolved merely because of persistence or reload.
- Resolved must not become ambiguous merely because evidence was flattened or reordered.
- Unresolved may become resolved only through new validated evidence, explicit correction, or authoritative historical mapping.
- Ambiguous may become resolved only through new deterministic evidence.
- Identity-status changes that affect membership require the repository’s normal universe-version transition.
- Ordinary persistence round trips must preserve identity status exactly.

## 7. Preconditions for `ResearchUniverse`

A `ResearchUniverse` may exist only when all these invariants hold:

1. Every input source record belongs to exactly one canonical candidate group.
2. No source record appears more than once within a group.
3. No two candidates share the same canonical identity key.
4. Resolved candidates have a validated canonical security identity or normalized ticker.
5. Unresolved candidates do not borrow a ticker, resolution, or membership intent from another group.
6. Ambiguous evidence remains explicit and inspectable.
7. Raw names and tickers are preserved alongside normalized or corrected identity.
8. Materially conflicting securities are not silently collapsed.
9. Candidate groups are final before any disposition is assigned.
10. An included disposition applies to exactly one finalized candidate.
11. Approved membership contains unique canonical identities.
12. Serialization and deserialization preserve the canonical partition exactly.

The following downstream invariants then follow:

- Handoff contains exactly one row per included canonical candidate.
- Preflight and execution ledger contain exactly one row per handoff member.
- An analyzed and unavailable row can never represent the same canonical identity.
- Snapshot membership reconciles exactly with the universe ID and version.
- Snapshot and repository duplicate checks remain active and reject corruption.
- Comparison can treat canonical matching keys as stable historical identity.

### Deterministic regression coverage

Every mandatory invariant in this contract must be covered by at least one deterministic regression test. Tests must cover valid and invalid cases and must not depend on OpenAI, Tradier, external network calls, fuzzy matching, or nondeterministic ordering. At minimum, regression coverage must include exclusive source-record ownership, unique canonical candidate identities, Zscaler-compatible tickerless manual-name promotion, COHR/CSG separation without authoritative correction, exact save/load idempotence, no evidence multiplication, downstream duplicate rejection, preservation of raw provenance, and identity-confidence monotonicity.

## Implementation decision summary

The implementation should introduce or formalize one review-domain canonical partition operation and make it the sole owner of candidate grouping. It must be validation-aware and directional: unique tickerless manual-name promotion is allowed, while unresolved ticker-bearing historical evidence requires an explicit correction or authoritative relationship.

Candidate dispositions must be applied after partitioning. Persistence must store and reload the finalized candidates without ordinary read-time re-canonicalization. Handoff, ledger, snapshot, and comparison remain strict consumers with duplicate guards; none may repair identity defects.

This contract deliberately favors explicit ambiguity over silent historical corruption.
