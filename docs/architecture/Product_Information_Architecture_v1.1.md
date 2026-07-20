# Product Information Architecture v1.1

**Status:** Proposed architecture amendment and implementation foundation for independent review
**Supersedes:** Product Information Architecture v1.0 as the current north-star reference
**Scope:** Canonical Research Universe product model and shared review workflow

## Executive summary

Product Information Architecture v1.1 preserves the two primary intents from v1.0 and corrects the universe-construction architecture. There is one durable central product object: the **Research Universe**. User-entered, curator-authored, imported, saved, and company-derived starting lists are equivalent inputs to that object. Their sources remain provenance and may govern ownership, visibility, publication, or certification, but do not select different matching, review, disposition, or downstream-analysis behavior.

The formal principle is:

> User-entered, curator-authored, imported, saved, and company-derived starting lists are equivalent Research Universe inputs for review and analysis. Their source is retained as provenance, but their computational treatment and user-facing review workflow are identical.

Research Universe Builder is therefore a compatibility route and lifecycle operation, not a permanent top-level product module. Benchmark curators are privileged users of the same Research Universe model and review capabilities, not owners of a separate universe type or CRUD application.

## 1. Product model correction

### 1.1 Canonical workflow

The market/theme workflow is:

`Research question and/or Starting Companies + RCE Suggestions -> Research Universe Review -> Approved Research Universe -> Analyze every constituent -> Opportunities`

The company workflow is:

`Company -> Company Analysis -> Research this company's market and competition? -> Company and optional peers become Starting Companies -> RCE Suggestions -> the same Research Universe Review`

### 1.2 Lifecycle, not modules

“Building,” “reviewing,” “updating,” and “curating” are lifecycle operations on a Research Universe:

- **Build:** establish a question and/or Starting Companies and obtain optional RCE Suggestions.
- **Review:** compare normalized identities and record included, rejected, pending, deferred, or identity-review states.
- **Approve:** establish the exact membership contract without requiring every suggestion to be resolved.
- **Analyze:** hand the approved membership to downstream capabilities unchanged.
- **Update/refine:** create an explicit revision that preserves prior records and decisions.
- **Curate:** perform the same operations with additional governance permissions and diagnostic context.

Curator is a role/permission context. A curator-authored official universe and a private user universe share the same object and candidate model. They may differ in owner, visibility, sharing, publication, certification, and version-governance privileges.

## 2. Canonical Research Universe

A Research Universe contains or references:

- stable universe identity and explicit version/revision identity;
- owner or owner reference when identity exists;
- title and research topic/question;
- lifecycle state;
- Starting Companies corpus;
- RCE Suggestions corpus;
- normalized company identities;
- source records and provenance;
- user/curator dispositions and comments;
- approved membership;
- visibility/scope and governance metadata where applicable;
- timestamps;
- downstream analysis references when available.

Persisted Research Universes are user-owned or shared research sandboxes. They evolve through explicit revisions. Updating a universe must never rewrite the historical candidate set, dispositions, or approved membership of an earlier version.

### 2.1 Starting Companies

**Starting Companies** is the user-facing term for corpora previously described as Authored Benchmark, Authored Source Corpus, ABM, anchor companies, known companies, curator seed, or user seed list. ABM is not a normal-user concept.

A Starting Company can originate from:

- one of the existing 17 curator-authored corpora;
- manual general-user entry;
- entry alongside a free-form market/theme question;
- Company Analysis;
- a company used as a market-and-competition anchor;
- a saved Research Universe revision;
- a future imported list or watchlist.

The source changes provenance, permissions, and possibly publication status. It does not change normalization, ticker-first matching, comparison, inclusion, rejection, pending/deferred handling, audit retention, or downstream handoff.

### 2.2 RCE Suggestions

**RCE Suggestions** is the user-facing term for the RCE-generated candidate corpus. Suggestions are provisional. General users and curators may include or reject them. A suggestion may remain pending indefinitely.

RCE does not approve membership. Approval of a Research Universe does not require every RCE Suggestion to be dispositioned.

### 2.3 Research Universe Review

**Research Universe Review** is the shared user-facing company-list review surface. General-user and curator modes use the same normalized candidate rows, disposition rules, progress calculation, provenance model, and approved-membership export.

General-user mode shows the topic, Starting Companies, RCE Suggestions, dispositions, include/reject actions, optional comments, Analyze Company, and approved summary. It hides certification, fixtures, scoring/regression evidence, developer diagnostics, and official-publication controls.

Curator mode adds richer authored provenance, official corpus source, evaluation detail, certification/regression evidence, publication controls, and privileged version governance. Those additions do not fork the core review computation or table model.

## 3. Identity, membership, and disposition rules

All input origins receive identical rules:

1. Normalize deterministic company names and ticker/identifier values.
2. Match ticker/identifier first; use exact normalized company name only as a fallback when no ticker is available.
3. Surface ambiguous or conflicting deterministic identities as `identity_review`; do not use fuzzy or model-based identity resolution implicitly.
4. A company in both Starting Companies and RCE Suggestions is included automatically.
5. A Starting-only company is included immediately because the user explicitly selected or entered it.
6. An RCE-only suggestion is pending until explicitly included.
7. A general user or curator may reject a one-sided candidate.
8. Rejection does not delete any source record.
9. Pending and deferred candidates may remain unresolved indefinitely.
10. Approval includes automatic agreements plus explicit inclusions only.
11. Approval does not require all suggestions to be dispositioned.
12. Pending and rejected candidates remain outside approved membership but remain auditable in that version.
13. The approved membership is the exact downstream contract.
14. Display filtering, sorting, ranking, highlighting, and recommendation do not change membership.

The existing Curator Workbench automatic-agreement behavior is preserved by the canonical rule rather than treated as curator-specific logic.

## 4. Source and provenance model

Canonical source values initially include:

- `curator_authored`
- `user_entered`
- `company_analysis_anchor`
- `saved_universe_revision`
- `imported`
- `rce_generated`

Each source record retains its supplied company name, ticker/identifier when present, source reference, and source-specific metadata. A canonical candidate can contain multiple source records. Source metadata can affect who may publish or certify a universe, but cannot select an alternate matcher, review engine, or downstream handoff.

Inclusion origin is recorded independently from source. Examples are automatic Starting Companies/RCE agreement and explicit review decision. Rejection reason and optional user/curator comments are decision metadata, not destructive edits to provenance.

## 5. Lifecycle states

The future-compatible state vocabulary is:

- `draft`
- `under_review`
- `approved`
- `analysis_running`
- `analyzed`
- `revision_draft`
- `archived`

The Sprint 1 implementation needs only `under_review` and `approved` for the adapted general-user flow, while retaining the broader vocabulary in the domain model. Approval may occur with pending records. Analysis state must be changed only by explicit downstream orchestration; universe approval does not automatically launch SAM or Opportunity Discovery.

## 6. Downstream contract and non-filtering requirement

The future-compatible handoff contains:

- `universe_id`;
- `universe_version`;
- exact ordered approved constituent list;
- `expected_constituent_count`;
- provenance/source references.

SAM and Opportunity Discovery must receive every approved member. For each constituent they must return analysis or an explicit unavailable/error/no-result status. They must not silently remove a company. Approved count must equal the exported constituent count before a run is accepted.

The handoff does not launch analysis. It does not change SAM scoring, SAM reasoning, Opportunity Discovery selection/scoring, production analytical behavior, or repository archiving.

## 7. Entry-point readiness

The future Home still asks **“What would you like to analyze today?”** with Industry, Market, or Theme and Company. This sprint does not redesign Home.

The market/theme workflow context must accept:

- question only;
- Starting Companies only;
- question and Starting Companies;
- selected saved/seeded universe;
- valid combinations of those inputs.

Research Universe Review must not require an authored benchmark. Company-derived context provides the source company as a `company_analysis_anchor`, optional user-entered peers, an editable starter question, and an originating Company Analysis reference. The transition UI remains future work.

## 8. Curator governance

Curator Tools layer permissions and diagnostics onto the canonical object. They may expose:

- complete authored provenance and original source pages;
- official/shared publication actions;
- stored evaluation comparison;
- certification and regression evidence;
- privileged version approval or governance metadata.

They must not require a second computational universe-review implementation. Existing Benchmark Curator Workbench and Benchmark Explorer routes remain compatibility paths until a later adapter sprint proves their certification, audit, and two-click approval behavior on the shared renderer.

## 9. RCE refinement and revision

RCE refinement/update is a future explicit workflow. Its request should be capable of referencing:

- prior Research Universe/version;
- prior RCE Suggestions;
- accepted companies;
- rejected companies;
- deferred or pending companies;
- optional comments.

It must create a proposed revision rather than mutating history. No accepted/rejected feedback is sent to RCE in this sprint, and no Refine or Update Universe provider call is implemented.

## 10. Current implementation overlap audit

### 10.1 Research Workspace

**Current responsibility:** free-form question input, RCE interpretation preview, Candidate Companies, research starter cards, recent observations, saved CSV universe display, and shortcuts to internal modules.

**Overlap:** duplicates question/candidate presentation from Research Universe Builder; includes a company starter path; its Build Research Universe action is disabled. RCE response state is session-only and is not handed to Builder.

**Reusable:** existing Research Conversation service/provider boundary, structured response, question state, and session reset/modify behavior.

**Protected:** production RCE prompt, parsing, validation, confidence, provider selection, and live-call boundaries.

### 10.2 Research Universe Builder

**Current responsibility:** free-form question plus anchor entry, provider request, anchor reconciliation, session draft, candidate selection, manual inclusion, draft Benchmark of Record, and SAM ticker handoff.

**Overlap:** duplicates candidate table, approval state, provenance expander, and approved summary from the Curator Workbench. Uses `ResearchUniverseDraft`, `approved_candidate_keys`, and `inclusion_origins`, which differ from curator persistence and identifiers.

**Persistence:** `st.session_state.research_universe_draft`; lost on tab/session termination or server restart.

**Sprint 1 adapter:** its result view now creates the canonical Research Universe and calls the shared renderer. Its compatibility route and provider request remain.

### 10.3 Benchmark Curator Workbench / Benchmark Explorer

**Current responsibility:** select one of 17 domains; compare authored source corpus to stored certified RCE candidate corpus; investigate provenance; preserve automatic agreements; add one-sided candidates through two-click confirmation; inspect Benchmark of Record; expose certification/evaluation detail.

**Overlap:** maintains another comparison row, progress model, inclusion flow, approved summary, provenance display, and Analyze Company action.

**Persistence:** `CuratorApprovalRepository` writes idempotent inclusions to `data/research/rce_benchmark_curator_approvals_v0.1.json` using benchmark ID plus normalized matching key. Agreements are derived, not stored. The JSON does not retain curator identity, rejection, pending, or decision rationale.

**Reusable:** `corpus_comparison`, deterministic ticker-first matching, authored/RCE loaders, approval repository, investigation/evaluation services, and existing approval behavior. A canonical adapter now reads comparison rows and existing approvals without changing the JSON.

**Protected:** certified baseline, fixtures, scoring configuration, authored corpus, evaluation language, two-click approval, Benchmark-of-Record behavior, and regression tests.

### 10.4 Current Benchmark of Record

**Current responsibility:** a derived read model consisting of automatic corpus agreements plus matching keys present in curator approval JSON.

**Identifier:** benchmark ID + `ticker:<symbol>` or fallback `name:<normalized-name>`. Some one-sided stored comparison keys use name fallback even when the row has a ticker, so the canonical curator adapter translates legacy keys to the canonical ticker-first key.

**Limitation:** it is membership output, not yet a durable full Research Universe with rejected/pending history, ownership, revisions, or analysis references.

### 10.5 Free-form RCE request flow

**Current responsibility:** builds `ResearchConversationRequest` with original question, optional anchor strings, `general_user` origin, and workflow context; then uses the existing provider/parser/validation pipeline.

**Persistence:** response and draft are session-only. Candidate keys are generated separately by Builder and use ticker-first/fallback-name logic, but not the complete curator ambiguity model.

**Protected:** anchor payload compatibility, benchmark-style request behavior, system prompt, reasoning, candidate generation, and provider invocation timing.

### 10.6 SAM ticker/universe handoff

**Current responsibility:** Builder and Curator actions call `launch_benchmark_company_analysis`, set `benchmark_pending_sam_ticker`, switch `selected_page` to Security Research, and select the ticker only when a stored SAM observation exists.

**Limitation:** this is a single-ticker UI handoff, not a Research Universe population contract. Opportunity Research separately consumes a CSV path. Neither currently accepts universe ID/version plus exact approved membership.

**Protected:** SAM calculations, scoring, stored observations, filters, and Opportunity Discovery behavior.

### 10.7 Research Repository observations

**Current responsibility:** SQLite or Postgres repository abstraction for opportunity scans, evaluated contracts, rule evaluations, security characterization, technical characterization, status, and recent observation metadata.

**Persistence:** SQLite defaults to `data/research/opportunity_scans.sqlite`; cloud may use Postgres. It persists completed observations and Study Protocol metadata, not Research Universe drafts or review decisions.

**Decision:** do not extend this schema in Sprint 1. A Research Universe repository needs an independently reviewed ownership/version/history migration design. Free-form universes remain clearly session-only.

## 11. Duplicate models and incompatibilities

| Concern | Builder | Curator Workbench | Canonical direction |
|---|---|---|---|
| Company input | `AnchorCompany` | `AuthoredSourceCandidate` | `UniverseSourceRecord` with source provenance |
| Candidate input | RCE mapping | `RCECorpusCandidate` | `UniverseSourceRecord(source=rce_generated)` |
| Comparison row | `AnchorReview` plus candidate mapping | `CorpusComparisonRow` / `CuratorCorpusRow` | `UniverseCandidate` |
| Decision state | approved key set only | persisted approved key set; agreements derived | included/rejected/pending/deferred/identity-review |
| Approved output | draft approved candidates | `BenchmarkOfRecordMember` | `ResearchUniverse.approved_membership` |
| Identifier | ticker then normalized name | ticker/identifier then name, with legacy one-sided name keys | canonical ticker-first key plus legacy adapter |
| Persistence | Streamlit session | JSON inclusion approvals | reuse JSON through adapter; no new store |
| Renderer | one dataframe and detail block | two side-specific tables and detail blocks | one shared review renderer with mode additions |

No third review implementation should be introduced. The next curator adapter should replace duplicated table rendering only after equivalence tests cover existing two-click confirmation and governance detail.

## 12. Sprint 1 implementation decision

The general-user Builder result view is the first adapter because:

- it has the smaller behavior and persistence surface;
- it is explicitly session-only;
- it lacks certification, scoring, fixture, or publication controls;
- its current approval model can be preserved through compatibility fields;
- adapting it proves question-plus-Starting-Companies input without risking curator audit artifacts.

The Benchmark Curator Workbench remains unchanged as a compatibility route. The shared service includes a curator comparison/approval adapter, allowing parity tests before its renderer is migrated.

## 13. Persistence decision and future schema

Sprint 1 uses no new persistence store:

- existing curator inclusions remain in the current approval JSON and are readable through the canonical adapter;
- automatic agreements remain derived;
- free-form Research Universes, rejections, pending states, and approval state remain in Streamlit session state;
- Research Repository observations remain unchanged.

A future durable repository should model universe, version, source record, candidate identity, disposition event, approved membership snapshot, and analysis reference separately. It should support owner, visibility, sharing, publication, certification, optimistic versioning, and immutable historical versions. This is defined, not implemented.

## 14. Navigation implications

Research Universe Builder is not a permanent top-level product module. During compatibility review, Research Workspace, Research Universe Builder, Benchmark Curator Workbench/Explorer, and existing research pages remain reachable. The next consolidation sprint can:

1. connect Research Workspace structured output to the canonical context/service;
2. make Research Universe the contextual destination;
3. adapt Curator Workbench core comparison to the shared renderer while preserving its privileged controls;
4. remove the Builder top-level entry only after both entry paths are verified;
5. introduce progressive navigation after context handoffs are stable.

## 15. Explicit non-goals and protected behavior

This amendment and foundation do not modify production RCE prompts or reasoning, candidate-generation logic, benchmark questions/scoring, fixtures, certified artifacts, authored-source files, Benchmark-of-Record computation, SAM reasoning/scoring, Opportunity Discovery selection/scoring, Study Protocols, cloud jobs, or production analysis. It does not feed decisions back into RCE, implement Refine/Update, persist general-user universes durably, launch a population run, delete compatibility pages, commit, or push.

Future durable Research Universe architecture must preserve the exact AI request prompt and exact provider response as versioned provenance alongside the universe revision. That persistence is intentionally deferred and is not implemented by this sprint.

See `Product_Information_Architecture_v1.1_diagram.md` for the converged input, review, role, and downstream-contract diagrams.

## 16. Research Universe UX Sprint 1 migration path

Normal navigation now treats **Research Universes** as the session current-universe surface: Current Companies precede RCE-only Suggested Additions, every starting member is included by default, and manual additions are included without an RCE refresh. The existing Benchmark Curator Workbench remains available under **Administration → Benchmark certification** as the compatibility and diagnostic route; its certification, evaluation, provenance, regression, and approval repository behavior are unchanged.

`universe_type` is a governance classification with initial values `private_user`, `shared`, `curated_official`, `system_seeded`, and `imported`. Along with future ownership, visibility, publication status, and user role, it may govern sharing, publication, certification, and official-version controls. It must never select alternate matching, disposition, membership, review, or downstream-analysis rules. Normal users will be able to govern universes they own; authorized curators will additionally govern shared or official universes. Authentication and enforcement remain future work.

The exact population handoff is available as universe ID, version, expected count, ordered constituent list, and provenance references. **Analyze Companies** remains disabled until SAM has a reviewed population entry point that consumes this contract without CSV-path coupling or silent constituent filtering. A later migration may place official-universe controls in Curator Tools or a secondary expander after role and universe-type authorization exists; it must not introduce a separate Research Universe model or editing application.
