# Research Universe Construction Standard v0.1

## Purpose

The Research Universe Construction Standard (RUCS) defines how the Research Conversation Engine should construct Proposed Research Universes from a user's Research Mission.

RUCS is a product methodology document. It standardizes the reasoning artifact that comes before company selection, the standards for candidate inclusion, and the boundaries between RCE and downstream analytical models.

RUCS does not implement scoring, prompts, persistence, database schema, UI behavior, SAM behavior, Opportunity Discovery behavior, OAM behavior, Study Protocol behavior, cloud jobs, or repository behavior.

---

## 1. Multi-Stage RCE Reasoning Workflow

RCE should be designed as an internal research-planning workflow, not as a single-step company-list generator.

The internal workflow is:

User Question -> Interpretation -> Research Planning -> Universe Construction -> Universe Review -> User Presentation

Each stage has a distinct purpose and output. The user does not need to see every internal artifact, but the final presentation should be traceable back to the internal reasoning chain.

### 1.1 Interpretation

Purpose:
Understand what the user is really asking.

Output:
Research Intent Profile.

The Research Intent Profile should capture the user's original question, interpreted intent, relevant domains, lenses, entities, themes, scope, time horizon, asset focus, assumptions, confidence, and whether clarification is required before proposing artifacts.

Interpretation should classify intent. It should not select securities, score securities, evaluate options, or imply conclusions.

### 1.2 Research Planning

Purpose:
Determine how an analyst would structure the research.

Output:
Research Plan.

Required Research Plan fields:

- Research objective.
- Primary theme.
- Research lens.
- Included areas.
- Excluded areas.
- Adjacent areas.
- Candidate subdomains.
- Assumptions.
- Known blind spots.

The Research Plan is the bridge between intent and universe construction. It should explain how the research question will be decomposed before specific Candidate Securities are proposed.

### 1.3 Universe Construction

Purpose:
Construct a Proposed Research Universe from the Research Plan.

Output:
Candidate Securities with ticker, company, subdomain, rationale, and confidence.

Universe Construction should use the Research Plan to select representative, explainable, research-useful candidates across the included areas and candidate subdomains. It should avoid defaulting to the most popular or largest names unless they are central to the research objective.

### 1.4 Universe Review

Purpose:
Evaluate whether the proposed universe is useful before showing it.

Output:
Universe Review.

Required Universe Review fields:

- Coverage assessment.
- Relevance assessment.
- Informational diversity assessment.
- Missing areas.
- Weak candidates.
- Redundant candidates.
- Recommended improvements.
- Draft Research Utility Score.

Universe Review is an internal quality-control stage. It should assess the Proposed Research Universe as a research artifact, not as a set of attractive securities.

The Draft Research Utility Score is future-facing and experimental. It is not implemented in v0.1 and should not affect executable behavior until a later sprint defines scoring rules, persistence, display, and validation.

### 1.5 User Presentation

Purpose:
Translate internal artifacts into user-friendly guidance.

Output:
Clean UI sections.

User Presentation should convert the internal Research Intent Profile, Research Plan, Proposed Research Universe, and Universe Review into sections the user can inspect and refine:

- Here's how I understand your question.
- How we'll approach it.
- Areas included.
- Areas excluded.
- Companies to start with.
- Assumptions.
- Ways to refine this.

User Presentation should not expose internal reasoning noise, hidden ranking, or unsupported certainty. It should preserve enough explanation for the user to understand the proposed research boundary and edit it before downstream analysis.

---

## 2. Core Principle

RCE should optimize Proposed Research Universes for research usefulness, not popularity.

A useful Proposed Research Universe helps a user investigate an idea with enough breadth, rationale, and boundary clarity to support downstream research. It is not a list of the most famous companies, the largest market capitalizations, the most actively traded securities, or the companies that appear most often in market commentary.

Popularity may be relevant when a company is central to a theme, but popularity alone is not a sufficient inclusion standard.

---

## 3. Coverage Before Ranking

RCE should prioritize coverage before ranking.

The first construction question is:

What parts of the investable ecosystem need representation for this research question to be studied responsibly?

Only after the ecosystem is mapped should RCE propose candidate securities. Candidate order should support reviewability, not imply security quality, option quality, expected return, or trade priority.

The Proposed Research Universe should therefore include:

- Core areas that are directly in scope.
- Supporting areas that materially affect the theme or thesis.
- Representative candidates across relevant subdomains.
- Explicit exclusions when adjacent areas are intentionally left out.
- Coverage limitations when the proposed list is incomplete or uncertain.

---

## 4. Research Map First, Company List Second

RCE should construct a Research Map before proposing companies.

The Research Map is an ephemeral session-specific decomposition of the user's topic. It explains how the research objective is broken into investable subdomains, business models, supply-chain roles, customer groups, risk areas, or event exposures.

The Research Map is not:

- A canonical taxonomy.
- A persisted industry classification system.
- A source of truth about all possible companies.
- A ranking model.
- A security-quality model.

The Research Map should make the Proposed Research Universe easier to inspect by showing why each candidate area exists before individual companies appear.

---

## 5. Included, Excluded, and Adjacent Areas

Every Proposed Research Universe should distinguish:

- Included areas: subdomains that are inside the proposed research boundary.
- Excluded areas: subdomains that might look related but are intentionally outside the current boundary.
- Adjacent areas: related areas that may be useful for later refinement but are not necessary for the first proposed universe.

Included areas should be selected because they help answer the Research Mission. Excluded and adjacent areas should be named when they prevent ambiguity.

Examples:

- An AI infrastructure universe may include semiconductors, cloud platforms, data center equipment, power infrastructure, and networking.
- It may exclude general software businesses with weak infrastructure exposure.
- It may mark robotics, consumer AI apps, and private companies as adjacent areas for later refinement.

---

## 6. Candidate Selection Standards

A Candidate Security may be proposed only when there is a plausible research-scope reason for inclusion.

Candidate Securities should satisfy at least one of these standards:

- Direct exposure: The company has a direct business, product, asset, or revenue connection to the Research Mission.
- Ecosystem role: The company enables, supplies, distributes, finances, or is materially affected by the theme being researched.
- Comparative relevance: The company helps compare business models, incumbents, challengers, substitutes, or peer groups.
- Boundary clarity: The company helps illustrate the edge of the research boundary, including cases that may later be removed.
- User-specified relevance: The company was mentioned by the user or follows from an explicit user constraint.

Candidate selection should not imply that a security is attractive, investable, technically strong, liquid, or suitable. Those questions belong to downstream research.

Each candidate should include:

- Ticker when available.
- Company name.
- Candidate subdomain or category.
- Inclusion rationale.
- Confidence or limitation note where useful.

---

## 7. Informational Diversity

The Proposed Research Universe should preserve informational diversity.

Informational diversity means the candidate list should contain different kinds of evidence-bearing companies rather than many near-duplicates. The list should help downstream research compare how different parts of the ecosystem behave.

Useful diversity may include:

- Business model diversity.
- Value-chain diversity.
- Large-cap anchors and smaller specialized names when appropriate.
- Direct beneficiaries and enabling suppliers.
- Incumbents and challengers.
- Domestic and international exposure when the user scope allows it.
- Different risk profiles or thesis sensitivities.

Informational diversity is not forced equal weighting. Some areas may deserve more candidates because they are central to the Research Mission. The standard is whether the Proposed Research Universe improves research coverage and comparison, not whether every category has the same count.

---

## 8. Assumptions and Refinements

RCE should use assumptions to move from an interpretable question to a useful Proposed Research Universe without unnecessary delay.

Default assumptions may include:

- U.S.-listed securities unless the user says otherwise.
- Equity research unless the user requests options or another asset type.
- General investment research unless a narrower strategy is stated.
- Medium-term research perspective unless an event or horizon is specified.

Assumptions must be visible. They should be framed as editable defaults, not hidden decisions.

Refinements should let the user adjust:

- Included areas.
- Excluded or adjacent areas.
- Candidate membership.
- Candidate rationale.
- Universe name and purpose.
- Asset scope, geography, time horizon, or research lens.

Follow-up user input should refine the current Research Mission and Proposed Research Universe rather than reopening an indefinite chat.

---

## 9. Relationship to SAM, OD, and OAM

RUCS governs only upstream Proposed Research Universe construction.

Relationship boundaries:

- RCE uses RUCS to translate intent into a Proposed Research Universe.
- A user-reviewed Research Universe Definition may later produce a Research Universe Snapshot.
- SAM may characterize securities in a snapshot after the universe is approved.
- Opportunity Discovery may search for visible opportunities within an approved snapshot.
- OAM may evaluate option contracts found by Opportunity Discovery.

RUCS does not:

- Score securities.
- Rank securities by attractiveness.
- Evaluate options.
- Change OAM scoring.
- Change SAM calculations.
- Change Opportunity Discovery behavior.
- Change Study Protocol execution.
- Change repository semantics.
- Create investment advice or suitability conclusions.

RUCS is about constructing a useful research population. SAM, OD, and OAM remain downstream evidence systems.

---

## 10. Future Concept: Research Utility Score

Research Utility Score is a future experimental score for the quality of a Proposed Research Universe.

It would evaluate the usefulness of the proposed universe as a research artifact, not the quality of the securities inside it.

Research Utility Score is not implemented in v0.1.

Possible future dimensions:

- Coverage: Does the universe represent the major parts of the Research Map needed to study the mission?
- Relevance: Do included candidates have a clear relationship to the Research Mission?
- Informational Diversity: Does the list contain evidence-bearing variety rather than redundant near-duplicates?
- Explainability: Are included, excluded, and adjacent areas understandable, and does each candidate have a reviewable rationale?
- Refinement Readiness: Can the user easily narrow, broaden, rename, or correct the universe before saving?

Research Utility Score must not be interpreted as:

- A security ranking.
- An investment-quality score.
- An OAM score.
- A SAM score.
- A prediction.
- A recommendation.

Any future implementation would require a separate product and technical specification.

---

## 11. Benchmark QA Scenarios

These scenarios define expected behavior for evaluating future RCE prompt, provider, and presentation changes. They are documentation-only benchmark cases, not automated tests in v0.1.

### 11.1 AI Networking / Interconnects

Expected research lens:
Theme / Narrative, Competitive Position, Fundamental, and Infrastructure.

Included areas:
AI networking chips, Ethernet switching, optical interconnects, data center switching, high-speed connectivity, network testing, and cloud-scale infrastructure suppliers.

Excluded areas:
General enterprise software, consumer AI applications, unrelated telecom carriers, and broad semiconductor names without meaningful networking or interconnect exposure.

Examples of strong candidates:
Broadcom, Marvell Technology, Arista Networks, Nvidia, Coherent, Lumentum, and Cisco when framed as networking infrastructure exposure.

Examples of weak/off-target candidates:
Consumer app companies, generic SaaS companies, telecom service providers without AI data center interconnect exposure, and semiconductor firms with no clear networking role.

### 11.2 AI Cancer Drug Discovery

Expected research lens:
Theme / Narrative, Fundamental, Competitive Position, Healthcare, and Event-Driven.

Included areas:
AI-enabled drug discovery platforms, oncology-focused biotechnology, precision medicine, computational biology, clinical trial analytics, diagnostics, and enabling life-science data platforms.

Excluded areas:
General AI software with no healthcare exposure, broad pharmaceutical companies with no clear AI oncology program, medical device companies unrelated to oncology discovery, and private-only research labs when the scope is public equities.

Examples of strong candidates:
Recursion Pharmaceuticals, Schrodinger, Exscientia, Tempus AI, Guardant Health, Illumina, and oncology-focused platform companies when the rationale is explicit.

Examples of weak/off-target candidates:
Mega-cap AI infrastructure companies without cancer-discovery exposure, general hospital operators, insurers, and biotech names included only because they are popular.

### 11.3 Data Center Power Buildout

Expected research lens:
Theme / Narrative, Macro Exposure, Fundamental, Infrastructure, and Event-Driven.

Included areas:
Regulated utilities, independent power producers, grid equipment, electrical equipment, backup power, power management, transmission infrastructure, and data center energy services.

Excluded areas:
Data center landlords without clear power-buildout angle unless explicitly requested, generic renewable funds, oil and gas producers without power infrastructure exposure, and software companies benefiting only indirectly from AI demand.

Examples of strong candidates:
GE Vernova, Eaton, Vertiv, Quanta Services, Constellation Energy, Vistra, NextEra Energy, and Schneider Electric when listing international names is allowed.

Examples of weak/off-target candidates:
Cloud software companies, unrelated utilities with no capacity-buildout relevance, consumer energy retailers, and AI chip companies unless the user asks for the full AI infrastructure chain.

### 11.4 Cybersecurity Market

Expected research lens:
Competitive Position, Fundamental, Theme / Narrative, Risk, and Opportunity Research only if the user asks for options.

Included areas:
Endpoint security, cloud security, identity and access management, network security, zero trust, secure access service edge, vulnerability management, security analytics, and platform consolidators.

Excluded areas:
General IT services, hardware resellers, broad software companies where security is not material, defense contractors without cybersecurity as a meaningful business line, and private cybersecurity startups unless context-only.

Examples of strong candidates:
Palo Alto Networks, CrowdStrike, Zscaler, Cloudflare, Fortinet, Okta, CyberArk, Tenable, Rapid7, and SentinelOne.

Examples of weak/off-target candidates:
Generic cloud infrastructure providers without a security thesis, low-relevance IT consultants, consumer antivirus brands without public equity relevance, and unrelated software companies added for name recognition.

### 11.5 Micron Earnings Call Options

Expected research lens:
Options, Event-Driven, Risk, and single-security Opportunity Research.

Included areas:
Micron as the underlying security, earnings-event context, bullish call option candidates, expiration window, liquidity, spread, delta, open interest, implied volatility, and user risk constraints.

Excluded areas:
Broad semiconductor universe construction unless requested, technical setup if the user explicitly excludes it, unrelated memory peers unless used only as context, and put strategies when the user asks for calls.

Examples of strong candidates:
MU as a single-security Research Universe and option contracts matching the user-stated direction, event window, and risk constraints after OD/OAM analysis.

Examples of weak/off-target candidates:
Nvidia, AMD, or other semiconductor tickers presented as substitutes for the requested MU option research; common-stock recommendations; price targets; and options surfaced without liquidity or risk context.

### 11.6 Fashion Brands Taking Market Share

Expected research lens:
Competitive Position, Fundamental, Valuation, Theme / Narrative, and Consumer.

Included areas:
Athletic apparel, footwear, luxury brands, specialty apparel, off-price retail, direct-to-consumer brands, department-store exposure when relevant, and market-share challengers versus incumbents.

Excluded areas:
General retail with no fashion or apparel exposure, consumer staples, e-commerce platforms without fashion-brand thesis, private brands unless context-only, and suppliers with no brand-level market-share relevance.

Examples of strong candidates:
Nike, Lululemon, Deckers, On Holding, Ralph Lauren, Tapestry, Capri Holdings, Abercrombie & Fitch, Urban Outfitters, and Burlington Stores when their segment relevance is clear.

Examples of weak/off-target candidates:
Grocery retailers, broad marketplaces without fashion-brand focus, unrelated consumer product companies, and apparel names included only because they recently moved in price.

---

## 12. Recommended Implementation Sprint

The recommended follow-on implementation sprint is:

RCE Multi-Stage Artifact Pipeline v0.1.

Scope:

- Add structured internal artifacts for Research Plan and Universe Review behind the existing provider abstraction.
- Extend provider output parsing to include Research Plan, Candidate Securities, Universe Review, and future-facing Draft Research Utility Score fields.
- Keep Research Utility Score display gated or omitted until scoring semantics are separately approved.
- Preserve session-only output unless a later persistence sprint explicitly saves Research Universe Definitions.
- Add benchmark QA fixtures for the scenarios in this document.

Non-goals:

- No SAM changes.
- No OD changes.
- No OAM changes.
- No Study Protocol changes.
- No repository schema changes.
- No cloud job changes.
- No universe persistence changes.
- No investment recommendation behavior.

---

## 13. Validation

This standard is documentation-only.

Validation for RUCS v0.1:

- No executable behavior changes.
- No prompt behavior changes.
- No scoring implementation.
- No Research Utility Score implementation.
- No SAM, OD, OAM, Study Protocol, repository, cloud, or UI behavior changes.

---

## Status

Status: Designed / Planned.

Version: v0.1.

---

## 14. Versioned RCE Benchmark Library

The documentation-only scenarios above now have a separate benchmark QA subsystem. Canonical reviewed JSON artifacts may express expected core, adjacent, optional, and excluded categories; positive and negative security references; evidence summaries; caveats; and source provenance.

Benchmark expectations guide comparative QA only. They are not immutable truth, a canonical taxonomy, a Research Universe Definition, a Research Universe Snapshot, production scoring input, or permission to change RCE reasoning. Private companies, international listings, funds, and distressed/exclusion cases must be retained with explicit classifications rather than dropped.

Fixtures are validated and imported transactionally into a dedicated benchmark database as documented in `docs/research/RCE_Benchmark_Library.md`. This addition does not modify RCE prompts, SAM, OD, OAM, Study Protocols, Research Universe persistence, production scoring, or cloud jobs.
