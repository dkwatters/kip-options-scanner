# Product Information Architecture v1.0

**Status:** North-star product architecture for independent review
**Sprint:** Product Information Architecture Sprint 1
**Scope:** Documentation only; no executable, model, provider, benchmark, scoring, repository, or cloud behavior change

## Executive summary

Kip should begin with the user's intent, not with its internal modules. The home experience asks **“What would you like to analyze today?”** and offers two primary choices: **Industry, Market, or Theme** and **Company**. Every normal-user page is then revealed in the context of the selected journey.

The market/theme journey turns a question, optional anchor companies, and an optional saved or seeded starting universe into suggested companies, a user-approved **Research Universe**, company analysis for every member, and a complete ranked opportunity view. The company journey launches a coherent **Company Analysis** and can branch into market-and-competition research by entering the same market/theme journey with the company as an anchor. It does not create a second analysis engine.

The approved Research Universe is a downstream contract. Company Analysis (internally SAM) and Opportunities (internally Opportunity Discovery) must preserve every approved constituent. Sorting, ranking, highlighting, and temporary display filters do not change membership.

The current application contains useful foundations but exposes them as eight peer navigation entries. The lowest-risk migration is presentation-first: establish Home and intent context, consolidate the existing question and universe-building surfaces, progressively disclose analysis pages, then refactor population and single-company presentation without changing reasoning or scoring.

## 1. Product principles

1. **Begin with user intent.** Users choose what they want to understand before they encounter tools or system concepts.
2. **Use plain product language.** Normal users see Research Topic, Suggested Companies, Research Universe, Company Analysis, Opportunities, and Research History.
3. **One workflow, several capabilities.** Existing internal systems serve steps in a continuous experience; they are not the primary navigation model.
4. **User approval establishes membership.** Machine-generated candidates remain suggestions until a user approves the Research Universe.
5. **The Research Universe is a contract.** Downstream systems may characterize and order its constituents but may not silently change membership.
6. **Population and single-company analysis are different presentations over the same company-analysis capability.** They should not become separate analytical engines.
7. **Progressively disclose complexity.** Advanced, curator, administrative, and diagnostic controls appear only to the appropriate role or context.
8. **Preserve provenance and reproducibility.** A user should be able to understand where a constituent came from and which approved population was analyzed.
9. **Preserve context across transitions.** Topic, anchors, universe identity/version, selected company, analysis status, and return location travel with the workflow.
10. **Avoid premature routing replacement.** Conditional navigation and explicit handoff state can establish the IA before a broader routing decision.

## 2. Primary user journeys

### 2.1 Journey 1 — Industry, Market, or Theme

| Step | User experience | Proposed user-facing name | Current internal system(s) | Product contract |
|---|---|---|---|---|
| 1 | Enter a plain-language question | Research Topic | Authored benchmark inputs when a seeded case is selected; RCE question input | The original wording is retained as workflow context. |
| 2 | Optionally name known companies | Companies you already know | Anchor inputs; authored benchmark/source corpus where applicable | Anchors are explicit inputs, not guaranteed final members. Omissions or reconciliation must be visible. |
| 3 | Optionally choose a saved or seeded starting point | Start from existing research | Seeded authored inputs, saved universe definitions, candidate corpus | Starting source and version remain attributable. |
| 4 | Generate or retrieve candidates | Find companies | RCE and candidate corpus | Output is structured suggestions, never final membership. |
| 5 | Inspect the proposed set and rationale | Suggested Companies | RCE structured candidates; candidate corpus | Each suggestion shows rationale, provenance, and uncertainty where available. |
| 6 | Add, exclude, and restore companies | Review Companies | Research Universe Builder; Curator Workbench capabilities where authorized | Changes are low-friction, reversible, and visibly user-authored. |
| 7 | Approve the population | Research Universe | Benchmark of Record semantics; Research Universe definition/snapshot | Approval creates the authoritative downstream membership set and provenance record. |
| 8 | Analyze all members | Analyze Companies | SAM / Security Research | Every supplied constituent receives a result or an explicit per-company error/unavailable status. |
| 9 | Compare and rank without losing members | Opportunities | Opportunity Discovery; population SAM views | Ranking and recommendation preserve the full constituent ledger. |
| 10 | Continue research | Company detail, Watchlist, Save research | Security Research, Research Repository, future watchlist/portfolio workflows | Drill-down preserves the parent topic/universe and provides a return path. |

The journey is conceptually:

`Research Topic -> Suggested Companies -> Review Companies -> Research Universe -> Analyze Companies -> Opportunities`

The user should not need to know that authored inputs, RCE, candidate corpora, a curator workbench, Benchmark of Record, SAM, and Opportunity Discovery implement those steps.

### 2.2 Journey 2 — Company

1. From Home, the user selects **Company** and enters a ticker or company name.
2. Identity resolution confirms the intended security when a name is ambiguous.
3. **Company Analysis** opens in single-company mode, using the existing SAM/Security Research capability and any other supported technical, fundamental, catalyst, and risk evidence. Unsupported dimensions must be labeled unavailable or planned rather than implied complete.
4. The page explains the company coherently and prioritizes narrative, key evidence, risks, catalysts, and future time-series views rather than one-row population charts.
5. The page offers **“Research this company’s market and competition?”**
6. On acceptance, the system creates market/theme journey context with:
   - the resolved company as an anchor;
   - its name and ticker;
   - a safely supported starter question or market context, clearly editable by the user;
   - a reference to the originating Company Analysis and a return path.
7. The user lands at **Research Topic** or **Suggested Companies**, depending on whether adequate, reviewable context can be safely pre-populated. RCE/candidate discovery proposes peers; the user still reviews and approves membership.
8. Population analysis reuses SAM and Opportunities. The anchor's existing observation may be reused only when its data/version/freshness contract matches; otherwise it is analyzed with the population.

**Transition point:** the branch occurs after the Company Analysis identity and context are established but before candidate generation. This is an input handoff into the single market/theme workflow, not a direct write to the Research Universe and not a parallel peer-analysis engine.

## 3. Home experience

### 3.1 Concept

The initial page contains:

- Product identity and a short research-only disclaimer.
- The primary question: **“What would you like to analyze today?”**
- Two equally clear intent choices:
  - **Industry, Market, or Theme** — “Build and analyze a group of relevant companies.”
  - **Company** — “Understand one company in depth.”
- A **Recent Research** section beneath the choices.
- A restrained link to advanced or administrative tools only for authorized users.

Selecting an intent reveals its minimal first input on the same page or navigates to its first step. Industry/market/theme asks for a question, optional known companies, and optional existing research. Company asks for a ticker or company name. The home page does not show benchmark selectors, provider controls, universe CSV paths, model acronyms, diagnostics, or scoring controls.

### 3.2 Recent Research

Example cards may include AI Data Center Networking, Defense Drones, Nuclear Utilities, Credo Technology, and Affirm. A card represents a resumable research object, not merely a raw scan row.

Conceptually, Recent Research includes:

- recently opened or changed market/theme work;
- recent Company Analyses;
- saved and in-progress research;
- status such as “reviewing companies,” “analysis complete,” or “in progress”;
- last activity time and the relevant topic, company, or universe label.

**Session-only behavior:** until durable persistence exists, the app may show work held in the current Streamlit session. It disappears when the tab/session ends and must be labeled **This session**. Existing repository observations may be shown as historical observations, but they are not automatically equivalent to resumable research projects.

**Durable behavior:** future Research History requires a stable research/project ID, user/owner identity, intent type, display title, original question, anchor companies, universe definition and snapshot IDs, analysis run references/status, selected company, saved/in-progress state, timestamps, and schema/version metadata. Persistence is explicitly out of scope for this sprint.

## 4. Terminology map

| Internal term | Current UI term | Proposed user-facing term | Where the internal term remains visible | Notes |
|---|---|---|---|---|
| Authored Benchmark | Authored Source Corpus / benchmark inputs | Seeded research set | Curator Tools, benchmark documentation, evaluator diagnostics | A source of known examples, not a normal-user destination. |
| Candidate Benchmark | RCE Candidate Corpus / Candidate Universe | Suggested Companies | Curator Tools, evaluator diagnostics | “Candidate” describes provisional membership. |
| Benchmark of Record | Benchmark of Record / Draft Benchmark of Record | Approved Research Universe | Curator Tools, audit metadata, developer docs | Product copy may simply use Research Universe once approved. |
| RCE | RCE / Research Workspace interpretation | Research Topic assistance / Find companies | Research Diagnostics, configuration, developer docs | Do not brand the workflow around the engine acronym. |
| SAM | Security Research / Security Analysis Explorer | Company Analysis | Research Diagnostics, model documentation, advanced methodology | Same capability supports population and single-company modes. |
| Opportunity Discovery | Opportunity Discovery | Opportunities | Advanced methodology, diagnostics, developer docs | User view ranks and characterizes all constituents. |
| Benchmark Curator Workbench | Benchmark curator workbench | Curator Tools | Role-restricted curator navigation | Retain as a specialized workflow, not normal navigation. |
| Research Universe Builder | Research Universe Builder | Review Companies | Page metadata during migration; advanced documentation | Merge into the market/theme workflow. |
| Research Workspace | Research Workspace | Home / active research workspace | Internal route or developer docs | “Workspace” may describe the shell, not the first decision. |
| Security Research | Security Research | Company Analysis / Analyze Companies | Advanced methodology and diagnostics | Name varies by single versus population presentation. |
| Evaluation Fixture | Fixture / benchmark scenario | Test scenario | Developer Diagnostics and test documentation only | Never normal-user navigation. |
| Certified Benchmark | Certified Benchmark | No normal-user label | Curator Tools, release evidence, developer diagnostics | Certification is an evaluation/governance concept. |
| Research Repository | Research Repository | Research History | Administration and repository diagnostics | Separate resumable research from raw observation storage. |
| Research Universe | Research Universe | Research Universe | User workflow and internal architecture | This term is useful and should remain visible. |

Copy should use sentence casing and verbs for actions: **Find companies**, **Review companies**, **Analyze companies**, **View opportunities**.

## 5. Progressive navigation model

### 5.1 Initial launch

Visible navigation:

- Home
- Recent research (or Research history once durable)
- Administration only when role-authorized

The primary intent choices live in Home content, not as a long permanent module list.

### 5.2 After selecting Industry, Market, or Theme

Reveal a contextual workflow group:

- Research Topic
- Suggested Companies (after candidates exist)
- Review Companies (after candidates exist)

A compact progress indicator can show the full journey while only valid steps are interactive. Home and Recent Research remain available.

### 5.3 After a Research Universe exists

Reveal:

- Research Universe
- Analyze Companies
- Opportunities when results are available or running

The universe name and constituent count remain visible in the workflow header. Editing membership creates an explicit revised/unapproved state; it does not retroactively mutate completed analysis.

### 5.4 After a Company Analysis exists

Reveal:

- Company Analysis
- Related market research, only after the user accepts the transition
- Parent Research Universe and Opportunities when the company was opened from a population

### 5.5 Restricted navigation

- **Administration:** Startup Check, connection/configuration status, repository operational status.
- **Curator Tools:** Benchmark Explorer/Curator Workbench, authored-vs-candidate comparison, approvals, certification evidence.
- **Developer Diagnostics:** RCE metadata, prompts/version identifiers, evaluation fixtures, certified artifacts, raw model/repository diagnostics, option-analysis diagnostics.
- **Advanced research:** Option Chain Explorer, detailed SAM/OAM diagnostic explorers, Study Protocol inspection where authorized.

Tradier Connection should not be a normal-user top-level page or persistent home sidebar control. It belongs to administration/diagnostics or appears as an operational status when relevant.

### 5.6 Return and context preservation

Home is always reachable. Recent Research resumes at the last meaningful workflow state. Breadcrumbs or a contextual back action return from Company Analysis to its parent population without losing view filters.

The workflow context should carry at least: research ID (when durable), intent, original question, editable interpreted topic, anchors, selected seed, candidate set plus provenance, user dispositions, approved universe ID/version/snapshot, analysis run IDs/statuses, selected company, display filters, and return location. In the current Streamlit application, session state can support an initial session-only contract; durable resume requires repository work later. Widget state alone must not be the cross-page contract.

This model can initially be implemented with the existing `selected_page` and explicit session-state handoffs. A move to conditional `st.navigation`/`st.Page` may improve structure later, but a broad routing rewrite is not a prerequisite.

## 6. Module contracts

### 6.1 Benchmark / Universe Construction

**Owns:** research-question and anchor inputs; candidate discovery request; candidate collation; review and curation; explicit add/exclude/restore disposition; approved membership; definition/snapshot identity; source and user-action provenance.

**Must not:** perform SAM or Opportunity Discovery analysis; present suggestions as final authority; silently remove approved members downstream; overwrite a previously approved/snapshotted population without an explicit revision.

### 6.2 SAM / Company Analysis

**Owns:** analysis of every supplied company; supported technical, fundamental, catalyst, risk, and future dimensions; single-security explanation; population comparison inputs; explicit unavailable/error states; model/version/freshness metadata.

**Must not:** add, remove, or replace Research Universe members; silently filter companies; embed universe-construction policy; create a separate analytical engine for single-company mode.

### 6.3 Opportunity Discovery

**Owns:** ranking and characterizing opportunity across the supplied population; relative strengths, risks, timing, and attention signals; visibility of every analyzed constituent; explicit “no opportunity,” “no matching contract,” unavailable, and error outcomes where applicable.

**Must not:** rewrite the approved Research Universe; confuse rank eligibility with membership; suppress low-ranked or no-result constituents from the population ledger; imply that a temporary UI filter changes scope.

### 6.4 RCE

**Owns:** interpreting the research question; candidate discovery and expansion; structured candidate output; assumptions, boundaries, rationales, uncertainty, and future refinement support.

**Must not:** become final authority on membership; analyze companies or options; change scoring; silently elevate authored, candidate, or model output into an approved Research Universe.

### 6.5 Research Repository

**Owns:** durable evidence and observation references, reproducibility metadata, and later support for saved/resumable research artifacts.

**Must not:** define user intent, universe membership, or analytical conclusions merely because it stores related records.

## 7. Population versus single-company analysis

### Population Analysis

Population Analysis is used when a Research Universe contains multiple companies. It answers: **“How do these companies compare, and where should I look more closely?”**

It should:

- analyze and show every constituent;
- compare, rank, summarize, and identify patterns;
- use tables, distributions, population charts, cohorts, and completeness/status indicators;
- permit temporary sorting and filtering without changing membership;
- open any row into the same Company Analysis capability with parent context.

### Single-Company Analysis

Single-Company Analysis is used when the user enters a company directly or drills into a population row. It answers: **“What should I understand about this company?”**

It should:

- explain one company coherently in narrative form;
- organize supported technical, fundamental, catalyst, and risk evidence;
- avoid one-row distributions, rankings, and population tables;
- support future technical trend lines and time-series visualizations;
- show evidence freshness and gaps;
- offer **“Research this company’s market and competition?”**

The difference is presentation and task context, not analytical authority. Future SAM/Security Research refactoring should establish a shared company-result contract with two view composers: population and single-company.

## 8. Formal non-filtering requirement

> **PIA-NF-001:** The approved Research Universe is the contract handed downstream. SAM and Opportunity Discovery must analyze, score, rank, and report on every supplied constituent. They must not silently reduce the universe to a smaller subset. Only an explicit user change to the Research Universe changes membership.

For every approved constituent, downstream output must provide either analysis or an explicit status such as unavailable, insufficient data, provider error, unsupported security, or no qualifying opportunity. Absence is not an acceptable status.

| Concept | Meaning | Changes membership? |
|---|---|---|
| Membership | The authoritative set approved by the user for the universe version/snapshot | Yes, but only through an explicit universe edit and approval action |
| Ranking | An ordering or score over members/results | No |
| Display filtering | A temporary view predicate, such as sector, status, or score range | No; provide “show all” and the full count |
| Recommendation | A signal that some members deserve attention | No |
| User disposition | An explicit action such as include, exclude, watch, dismiss, or archive | Include/exclude changes a draft; membership changes only when the revised universe is approved |

Acceptance evidence should reconcile `approved constituent count = analyzed/result-status constituent count` and make the universe version visible. Opportunity-specific rows may be fewer than constituents only if a complete constituent ledger explains every omission from the ranked opportunity subset.

## 9. User types

| User type | Likely entry point | Information depth | Visible controls | Hidden details | Likely next action |
|---|---|---|---|---|---|
| Level 1 user | Home, either intent | Guided summary and plain-language explanations | Question/company input, accept suggestions, simple include/exclude, analyze | RCE/SAM/OD acronyms, versions, fixtures, protocols, raw diagnostics | Review a company or shortlist; learn why it matters |
| Level 2 user | Home or Recent Research | More evidence, comparisons, filters, provenance | Anchors, seed selection, universe edits, population filters, drill-down | Evaluation fixtures, certification mechanics, provider internals | Refine a universe, compare companies, monitor research |
| Advanced research user | Home, Recent Research, optional Advanced tools | Methodology, freshness, distributions, run metadata | Advanced filters, evidence views, protocols where authorized | Curator approval and developer-only raw artifacts unless separately authorized | Inspect evidence, repeat or extend a study |
| Benchmark curator | Curator Tools | Corpus reconciliation, provenance, approval and certification evidence | Authored/candidate comparison, investigate, approve, audit | Normal user simplification is not required inside the tool | Maintain the authoritative evaluation corpus |
| RCE evaluator/developer | Developer Diagnostics | Prompt/provider metadata, fixtures, benchmark results and failure analysis | Diagnostic comparisons and evaluation tooling | Production user workflow controls when irrelevant | Evaluate candidate quality or diagnose behavior |

Level 1 and Level 2 workflows determine the primary IA. Advanced roles receive additional surfaces; they do not redefine Home.

## 10. Proposed page inventory

| Proposed user-facing name | Purpose / primary user question | Required entry context | Outputs | Next actions | Internal systems | Exists today | Disposition |
|---|---|---|---|---|---|---|---|
| Home | Choose intent: “What would you like to analyze today?” | Authenticated app session | Intent and initial input | Start topic or company; resume recent | Current Research Workspace shell | Partially: Research Workspace | **Rename/reframe**; replace four starter paths and module shortcuts with two intents |
| Research Topic | Define “What market, industry, or theme am I researching?” | Market/theme intent | Question, anchors, optional seed | Find companies | RCE; authored inputs; saved/seeded universes | Partially in Research Workspace and Builder | **Merge** into one workflow step |
| Suggested Companies | Understand “Which companies may be relevant, and why?” | Interpreted topic or seed | Candidate list, rationale, provenance, warnings | Review companies; refine topic | RCE; candidate corpus | Partially in Research Workspace preview and Builder | **Merge/rename** |
| Review Companies | Decide “Which companies belong in my research?” | Candidate list | User dispositions and draft membership | Approve Research Universe | Research Universe Builder; selected curator capabilities | Yes, emerging/untracked builder page | **Retain capability, merge page** into workflow |
| Research Universe | Confirm “What exact population will be analyzed?” | Approved draft | Named/versioned membership and provenance | Analyze companies; edit as new revision | Benchmark-of-Record semantics; universe definition/snapshot | Partial draft/CSV concepts | **Rename/consolidate** |
| Analyze Companies | Ask “What does the analysis show across every member?” | Approved Research Universe | Population analysis, completeness ledger, distributions | Open company; view opportunities | SAM/Security Research | Yes as Security Analysis Explorer | **Refactor/rename** population mode |
| Company Analysis | Ask “What should I understand about this company?” | Resolved company or population row | Coherent single-company evidence and narrative | Research market/competition; return to population | SAM/Security Research | Partial ticker filtering and benchmark handoff | **Refactor/rename** single-company mode |
| Opportunities | Ask “Which constituents deserve attention, and why?” | Approved universe plus analysis/run context | Complete ledger, ranking, strengths/risks/timing | Drill down; watch; save | Opportunity Discovery; existing option-analysis components | Yes under Opportunity Research | **Rename/integrate**; retain advanced option tools separately |
| Research History | Ask “What work can I resume or inspect?” | Repository/session context | Saved/in-progress research and historical observations | Resume; open result | Research Repository plus future research-object persistence | Partial recent observations only | **Rename and evolve**; do not equate raw observations with resumable work |
| Curator Tools | Maintain evaluation corpora and approvals | Curator role | Corpus comparisons, approvals, audit data | Investigate; certify | Benchmark Explorer/Curator Workbench | Yes, emerging/untracked page | **Hide** from normal users; retain |
| Administration | Ask “Is the application and its data access healthy?” | Admin role | Startup, repository, provider/connection status | Diagnose configuration | Startup Check; Tradier Connection; repository status | Yes as separate pages/sidebar | **Merge and hide** behind role |
| Developer Diagnostics | Diagnose “Why did an engine or evaluation behave this way?” | Developer/evaluator role and relevant artifact | Raw metadata, fixtures, model diagnostics | Compare, trace, export | RCE diagnostics, SAE/OAE detail, fixtures, certified benchmarks | Distributed across pages and flags | **Consolidate/hide** |

### Current named-page decisions

- **Current home/landing / Research Workspace:** retain its question and session foundations; rename/reframe as Home and split by two intents.
- **Benchmark Explorer / Benchmark Curator Workbench:** retain as Curator Tools; remove from normal navigation.
- **Research Universe Builder:** merge into Research Topic -> Suggested Companies -> Review Companies; no separate top-level destination.
- **Research Workspace:** treat as the application shell/active research context, not a user choice alongside modules.
- **Security Research / SAM views:** retain capability; split presentation into Analyze Companies and Company Analysis.
- **Opportunity Discovery:** retain capability; expose as Opportunities only when a universe exists; keep Option Chain Explorer and Option Analysis Explorer advanced/diagnostic.
- **Research Repository:** rename the user surface Research History; keep repository operations in Administration/Diagnostics.
- **Startup Check and Tradier Connection:** merge under Administration and remove their always-visible/sidebar entry points.
- **Broad standalone module launcher:** retire as the primary navigation pattern.

## 11. User-visible state model

| State | Visible page | Available actions | Required data | Allowed transitions |
|---|---|---|---|---|
| No active research | Home | Choose intent; resume recent | Session/user context | Question entered; Single-company active; Research resumed |
| Research question entered | Research Topic | Edit question/anchors/seed; find companies | Intent, question, optional anchors/seed | Candidate generated; Home |
| Candidate universe generated | Suggested Companies | Inspect rationale/provenance; refine; continue | Structured candidate set | Universe under review; Question entered |
| Universe under review | Review Companies | Add, exclude, restore, edit rationale; approve | Candidate set plus dispositions | Research Universe established; Candidate generated |
| Research Universe established | Research Universe | Inspect membership/provenance; analyze; revise explicitly | Approved definition/version and materialized membership/snapshot | Population running; Universe under review as a new revision; saved/recent |
| Population analysis running | Analyze Companies | View progress/status; inspect completed results | Approved universe and analysis run ID/status | Population complete; Company active; saved/recent |
| Population analysis complete | Analyze Companies | Compare/filter; inspect every member; open company; view opportunities | Result/status for every constituent | Company active; Opportunities available; saved/recent |
| Single-company analysis active | Company Analysis | Review evidence; research market/competition; return | Resolved company; result/status; optional parent context | Research question entered with anchor; parent population; saved/recent |
| Opportunities available | Opportunities | Rank, filter display, inspect all statuses, open company | Approved universe, opportunity result/status ledger | Company active; population complete; saved/recent |
| Research saved or recent | Home / Research History | Resume; open; optionally archive later | Session object or durable research metadata | Research resumed; Home |
| Research resumed | Last valid workflow page | Continue valid actions; navigate within revealed steps | Rehydrated context and version references | Any state allowed by stored workflow data |

Invalid transitions should be unavailable rather than leading to empty module pages. A state may contain errors, but error statuses must preserve the expected constituent ledger and recovery actions.

## 12. Current-application migration assessment

### Evidence inspected

The current app is a single Streamlit entry point in `app.py` using a sidebar radio and `st.session_state.selected_page`. It exposes eight peers: Research Workspace, Research Universe Builder, Security Research, Opportunity Research, Research Repository, Benchmark Explorer, Startup Check, and Tradier Connection. Opportunity Research then adds three tabs: Opportunity Discovery, Option Chain Explorer, and Option Analysis Explorer.

Existing useful handoffs and state include:

- Research Workspace question, RCE response preview, starter cards, saved universe display, recent observations, and direct module shortcuts.
- A session-only Research Universe Builder with anchor reconciliation and draft Benchmark of Record language.
- A Benchmark Curator Workbench with authored-vs-candidate corpus and Benchmark of Record controls.
- A ticker handoff from benchmark/builder pages to Security Research via session state, limited to tickers with stored SAM observations.
- Repository-backed recent observations, which are scan history rather than durable research projects.

### Findings

**Duplicate entry points:** company research appears in the Research Workspace starter card, persistent Tradier ticker input, benchmark/builder Analyze Company actions, and Security Research ticker filters. Market/theme work begins in Research Workspace, Research Universe Builder, Benchmark Explorer, or by manually selecting a CSV in Opportunity Research.

**Overlapping pages:** Research Workspace candidate preview, Research Universe Builder, and Benchmark Curator Workbench each cover parts of question/candidate/review/approval. Security Research combines population-oriented distributions with ticker selection. Research Workspace and Research Repository both surface recent observations.

**Terminology conflicts:** Candidate Universe, Proposed Research Universe, Research Universe, Draft Benchmark of Record, Benchmark of Record, Authored Source Corpus, RCE Candidate Corpus, Security Research, Security Analysis Explorer, SAM, Opportunity Research, and Opportunity Discovery are visible at adjacent layers.

**Implementation leakage:** normal navigation exposes Benchmark Explorer, Startup Check, Tradier Connection, repository identity, CSV paths, study protocol metadata, provider/model/prompt metadata, and model acronyms. Some leakage is behind debug flags, but the page model itself remains module-first.

**Context-sharing gaps:** the RCE preview's Build Research Universe action is disabled; builder state and workspace RCE output are separate; approved universe persistence/snapshots are not established; Opportunity Research reads a CSV path rather than an approved workflow artifact; company handoff only selects an existing stored SAM observation; Recent Observations cannot resume the intent/candidate/review state; Company-to-market context does not exist.

**Navigation to delay:** Suggested Companies and Review Companies before candidate generation; Analyze Companies and Opportunities before approval; Company Analysis before identity resolution; repository/admin/diagnostic pages for unauthorized roles.

**Likely merges:** Research Workspace + Research Universe Builder for the market/theme journey; Startup Check + Tradier Connection + repository operational status into Administration; recent universe/observation surfaces into future Research History.

**Likely retained restricted tools:** Benchmark Curator Workbench, authored/candidate comparison, Benchmark of Record audit controls, RCE evaluator metadata, fixtures/certified benchmarks, SAE/OAE deep diagnostics, Study Protocol and cloud operational views.

**Likely retired patterns:** eight-item flat sidebar; persistent provider ticker/quote controls on unrelated pages; standalone builder as a peer destination; generic “Already know where you want to go?” module launcher for normal users.

### Lowest-risk refactoring strategy

Keep business logic and existing page renderers stable while first introducing intent and workflow context around them. Establish an explicit, testable context object/session-state contract before moving pages or changing routing. Reconcile full-universe result completeness before redesigning charts, because a visually improved population page must not conceal current omissions. Defer persistence and broad multipage routing until the user-visible state and artifact contracts are settled.

## 13. Phased implementation recommendation

| Sprint | User outcome | Likely files/areas affected | Major risks | Acceptance criteria | Production reasoning touched? |
|---|---|---|---|---|---|
| 1. Home and intent entry | User sees exactly two primary ways to begin and Recent Research | `app.py` presentation/navigation; possible future page-shell module; UI tests/docs | Breaking existing advanced access; confusing observations with resumable work | Home asks required question; two choices work; advanced tools remain reachable by authorized path; no provider call on render | No |
| 2. Workflow context contract | Transitions preserve intent, question, anchors, selection, and return path | Session-state initialization/handoff helpers; tests | Widget keys becoming de facto domain state; stale cross-workflow data | Explicit session-only context schema; start/reset/resume tests; no business-model changes | No |
| 3. Consolidate universe construction | One market/theme flow covers topic, suggestions, review, and approval | `render_research_workspace`; `src/research_universe_builder_page.py`; builder orchestration/service boundaries | Accidentally changing RCE prompts/provider behavior or Benchmark-of-Record semantics | Existing outputs consumed unchanged; anchors and seed optional; add/exclude/restore; clear approval; provenance visible | No; consume existing outputs only |
| 4. Progressive navigation | Only valid workflow steps and role-appropriate tools appear | `app.py` navigation/sidebar; authorization/config surfaces | Orphaning deep tools; losing context on rerun | Pages appear by state/role; Home always available; invalid steps inaccessible; all handoffs preserve context | No |
| 5. Universe handoff and completeness contract | Approved membership reaches analysis intact | Handoff adapters around universe definition/snapshot, SAM/OD invocations; repository metadata tests later | Protected production behavior; mismatched identity/version; hidden exclusions | Input/output reconciliation for every constituent; explicit failure/no-result statuses; no scoring/filter changes | Interface/orchestration only; production reasoning must remain untouched |
| 6. Population analysis presentation | User compares every constituent with appropriate charts and tables | Security Research/SAM presentation functions in `app.py`; view-model tests | Mistaking display filtering for membership; expensive reruns | Full constituent ledger; filters show total vs visible; population charts only for multi-company sets; row drill-down works | No |
| 7. Single-company analysis presentation | One company receives a coherent narrative view | Security Research/SAM presentation; company identity/handoff state | Implying unsupported fundamental/catalyst coverage; one-row population residue | No one-row distributions; supported dimensions and gaps explicit; same SAM results; parent return path | No |
| 8. Company-to-market transition | User can expand a company into market/competition research | Company Analysis CTA; workflow-context adapter; RCE input boundary | Unsafe inferred context; duplicate analysis; automatic membership | Anchor preserved; prefill editable and provenance-labeled; enters canonical market/theme flow before candidate approval | No prompt/reasoning change; input handoff only |
| 9. Opportunities integration | Opportunities follows analysis and preserves all constituents | Opportunity Research presentation; OD result/status adapter; diagnostics separation | Ranked subset mistaken for population; protected OD behavior | Every universe member visible or explicitly statused; ranking/filtering do not alter membership; advanced option tools separated | No scoring or OD behavior change |
| 10. Recent Research and persistence | User can reliably save and resume work | Research Repository schema/service and UI in a separately approved sprint | Schema migration, ownership/privacy, stale version rehydration | Durable IDs, timestamps, state/version rehydration, session vs saved distinction, migration/rollback plan | No reasoning change; persistence behavior only |

This order differs slightly from a purely visual sequence by adding the workflow context contract before consolidation and the full-universe handoff contract before population presentation. Those two small foundations reduce the risk of visually connecting pages that still cannot safely share state.

## 14. Unresolved product decisions

1. Does selecting an intent expand an inline Home form or navigate immediately to a dedicated step?
2. What is the durable top-level object: Research Project, Research Session, or another term, and who owns it?
3. Does approval create a Research Universe Definition, a snapshot, or both immediately, and how are revisions named?
4. How should anchors be dispositioned when candidate discovery does not return them: forced inclusion, explicit reconciliation, or suggestion only?
5. Which seeded sets are normal-user starting points versus curator-only benchmarks?
6. What minimum evidence safely pre-populates market/competition context from Company Analysis, and when must the user write the topic?
7. Which fundamental, catalyst, and risk dimensions are currently supported enough to promise on Company Analysis?
8. What constitutes “analysis complete” when a constituent has missing data or a provider error?
9. Should Opportunities represent security-level opportunity, option-contract opportunity, or a clearly separated combination?
10. Which Level 2 controls are on by default, and is there an explicit experience-level preference?
11. What authorization model gates Administration, Curator Tools, and Developer Diagnostics?
12. How should historical repository observations map to a resumable research object without rewriting existing evidence semantics?
13. What freshness/version rules permit reuse of a direct Company Analysis inside a later population run?
14. Is Research History the right durable label, or should saved projects and observation history remain separate?

## 15. Architecture references and implementation note

This IA builds on the existing Research Universe definition/snapshot architecture and product vision in:

- `docs/architecture/Research_Universe_Design_Specification.md`
- `docs/architecture/Architectural_Principles.md`
- `docs/product/Product_Vision_and_Experience_Architecture.md`
- `docs/product/Research_Universe_Construction_Standard.md`

The diagrams are maintained separately in `docs/architecture/Product_Information_Architecture_v1.0_diagram.md`.

No recommendation in this document authorizes changes to RCE prompts or reasoning, provider behavior, candidate generation, benchmark scoring, evaluation fixtures, certified artifacts, Benchmark of Record behavior, SAM, Opportunity Discovery, Study Protocols, production scoring, or cloud jobs.
