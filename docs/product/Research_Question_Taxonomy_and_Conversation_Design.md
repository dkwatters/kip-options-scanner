# Research Question Taxonomy and Conversation Design v0.1

## Purpose

This specification defines the first formal design for the Research Question Taxonomy (RQT) and Research Conversation Engine (RCE).

It is a documentation and product-design artifact only. It does not implement prompts, executable behavior, scoring, database schema, Opportunity Discovery behavior, Security Analysis Model behavior, Option Analysis Model behavior, Study Protocol behavior, repository behavior, cloud infrastructure, or UI behavior.

RQT and RCE exist to help the platform understand a user's natural-language research question, translate it into structured research artifacts, and preserve user review before downstream analysis begins.

The product philosophy behind this layer is:

- The platform begins with curiosity rather than tickers.
- Conversation starts the process. Evidence completes it.
- The application remembers research rather than conversations.

---

## 1. RQT Purpose

The Research Question Taxonomy is not a list of canned questions.

RQT is a taxonomy of research intent. It classifies what the user is trying to accomplish, what kind of research workflow is likely needed, which research lenses are implied, what scope is known or missing, and what clarification is required before the platform proposes a Research Mission, Research Strategy, or Research Universe Definition.

RQT should help the platform answer:

- What is the user asking for?
- Is the user trying to discover, evaluate, compare, learn, validate, monitor, build, or research an opportunity?
- Which analytical lenses are implied?
- Which securities, themes, industries, asset types, and time horizons are in scope?
- How much should the conversation explain before proposing artifacts?
- What must be confirmed before downstream research begins?

RQT output is interpretive metadata. It is not a score, a recommendation, a research conclusion, or an autonomous decision.

---

## 2. Core Flow

The intended flow is:

Question -> Research Conversation -> Research Guidance -> Research Mission -> Research Universe -> Security Analysis -> Opportunity Discovery -> Findings -> Research Refinement

The implementation-oriented flow is:

Natural-language user question -> Research Question Taxonomy classification -> Research Intent Profile -> Research Conversation Engine -> Research Mission -> Research Strategy -> Research Universe Definition -> Research Universe Snapshot -> Security Research / Opportunity Research -> Findings -> Research Refinement

Conceptual responsibilities:

- Natural-language user question: the user's plain-language entry point.
- RQT classification: intent classification across domains, lenses, entities, scope, and confidence.
- Research Intent Profile: structured representation of the interpreted question.
- RCE: brief guided conversation that turns the profile into user-reviewable artifacts.
- Research Guidance: persistent contextual guidance attached to the Research Session after conversation ends.
- Research Mission: the top-level question or thesis being researched.
- Research Strategy: the user-understandable plan for investigating the mission.
- Research Universe Definition: the saved population specification after user review.
- Research Universe Snapshot: the exact point-in-time securities used for analysis.
- Security Research / Opportunity Research: downstream analysis over the approved snapshot.
- Findings: evidence-backed observations saved from analysis.
- Research Refinement: explicit changes to the mission, universe, lenses, findings, decisions, or notes.

RQT and RCE are upstream of analysis. They do not change the downstream models.

---

## 3. Research Intent Domains

### Discover

Purpose: Help the user find securities, themes, industries, or candidates worth researching.

Representative user questions:

- "Show me AI stocks."
- "What companies are exposed to data center power demand?"
- "Find interesting infrastructure stocks."

Likely platform response:

- Interpret the theme or scope.
- Ask clarifying questions if the theme is broad.
- Propose a Research Mission and candidate Research Universe Definition.
- Explain candidate inclusion rationale.

Likely downstream components:

- RCE.
- Research Universe Definition.
- Research Universe Snapshot.
- Security Research.
- Opportunity Research if the user asks for current option opportunities.

### Evaluate

Purpose: Help the user investigate whether a company, theme, or universe appears well supported by evidence.

Representative user questions:

- "Is Caterpillar actually exposed to data center growth?"
- "Does this stock look strong enough to research further?"
- "Is this theme backed by fundamentals or just narrative?"

Likely platform response:

- Translate the question into an evidence-seeking Research Mission.
- Identify relevant lenses and candidate evidence types.
- Propose Security Research as the likely first path.

Likely downstream components:

- RCE.
- Security Research.
- Research Repository.
- Research Notebook.

### Opportunity Research

Purpose: Help the user inspect current opportunity availability within a defined or proposed universe, especially option opportunities.

Representative user questions:

- "Micron earnings are next Tuesday. I do not care about technical setup. What bullish calls should I consider?"
- "Find call opportunities in my AI watchlist."
- "Show near misses for liquid calls in semiconductors."

Likely platform response:

- Clarify the security or universe, option direction, expiration window, and user constraints.
- State that the platform will surface research candidates, not trade recommendations.
- Route to Opportunity Research only after scope confirmation.

Likely downstream components:

- RCE.
- Research Universe Snapshot.
- Opportunity Discovery.
- Option Analysis Model.
- Option Analysis Explorer.
- Research Repository.

### Compare

Purpose: Help the user compare companies, universes, themes, strategies, or evidence sets.

Representative user questions:

- "Compare Caterpillar and GE Vernova for data center exposure."
- "Which fashion brands are best positioned to take market share?"
- "How does this universe compare with my AI infrastructure universe?"

Likely platform response:

- Identify comparison dimensions.
- Propose a Research Mission and Research Strategy centered on side-by-side evidence.
- Build or reuse one or more Research Universes.

Likely downstream components:

- RCE.
- Research Universe Definition.
- Security Research.
- Research Notebook.
- Future Study Protocol comparisons.

### Learn

Purpose: Help the user understand a topic, company, model concept, or research workflow before analysis.

Representative user questions:

- "What should I know before researching options?"
- "How do I evaluate semiconductor stocks?"
- "What does open interest mean?"

Likely platform response:

- Provide plain-language explanation appropriate to the user's sophistication.
- Offer to turn the learning topic into a Research Mission if the user wants evidence.
- Avoid implying an investment conclusion.

Likely downstream components:

- RCE if the learning question becomes research.
- Research Notebook for saved learning notes.
- Security Research or Opportunity Research only after a research scope exists.

### Validate

Purpose: Help the user test whether a thesis, rumor, narrative, or assumption is supported by research evidence.

Representative user questions:

- "My friend keeps talking about Caterpillar and GE Vernova because of data centers. Is that true?"
- "Is AI power demand really helping utilities?"
- "Does this thesis have evidence behind it?"

Likely platform response:

- Restate the thesis.
- Identify what would count as supporting or weakening evidence.
- Propose a validation-oriented Research Mission and candidate universe.

Likely downstream components:

- RCE.
- Security Research.
- Research Notebook.
- Research Repository.

### Monitor

Purpose: Help the user create a repeatable observation process for a company, universe, event, or strategy.

Representative user questions:

- "Watch these AI infrastructure names for improving setups."
- "Track MU into earnings."
- "Monitor retail stocks for improving momentum."

Likely platform response:

- Clarify cadence, universe, trigger conditions, and evidence to preserve.
- Propose a Research Mission and Research Strategy that may later become a Study Protocol.

Likely downstream components:

- RCE.
- Research Universe Definition.
- Research Universe Snapshot.
- Study Protocols.
- Security Research.
- Opportunity Research.
- Research Repository.

### Build

Purpose: Help the user construct a watchlist, Research Universe, research strategy, or repeatable process.

Representative user questions:

- "Build me a data center power universe."
- "Create a retail turnaround research universe."
- "Build a strategy for finding bullish call candidates after earnings."

Likely platform response:

- Translate the construction request into a proposed Research Mission and Research Strategy.
- Propose candidate membership, inclusion rationale, boundaries, and exclusions.
- Require user review, edit, name, and save before downstream use.

Likely downstream components:

- RCE.
- AI-Assisted Research Universe Definition.
- Research Universe Definition.
- Research Universe Snapshot.
- Future Study Protocols.

---

## 4. Research Lenses

Research lenses are cross-cutting perspectives that modify how a domain should be interpreted. One user question may include multiple lenses.

Core lenses:

- Technical: price action, momentum, moving averages, RSI, MACD, volatility, setup quality, and other security-level technical observations.
- Fundamental: revenue, margins, balance sheet, cash flow, profitability, growth quality, and operating performance.
- Options: contract quality, liquidity, delta, spread, open interest, volume, expiration, and option-specific structure.
- Income: dividends, yield, payout sustainability, covered-call suitability, cash flow stability, and income-oriented research.
- Risk: drawdown, volatility, leverage, concentration, liquidity, event risk, downside exposure, and thesis fragility.
- Valuation: multiples, growth-adjusted valuation, peer comparison, discounted expectations, and valuation risk.
- Competitive Position: market share, moat, pricing power, product position, substitution risk, and peer threats.
- Event-Driven: earnings, guidance, product launches, regulatory events, government awards, litigation, mergers, and catalysts.
- Macro Exposure: rates, inflation, energy prices, currency, fiscal policy, government spending, trade policy, and economic cycle exposure.
- Theme / Narrative: AI, data centers, electrification, reshoring, defense modernization, retail recovery, consumer behavior, or other market narratives.

Lens handling rules:

- Lenses can be explicit or inferred.
- RQT should distinguish primary and secondary lenses where practical.
- Lens inference should be confidence-scored.
- RCE should confirm inferred lenses when they materially affect downstream research.
- A lens does not imply a conclusion; it only describes how to investigate the question.

---

## 5. Research Intent Profile

The Research Intent Profile is the structured output produced by RQT classification. It is the handoff object from classification to RCE.

Example fields:

```yaml
original_question: "Show me AI stocks."
primary_domain: "Discover"
primary_intent: "Find securities exposed to the AI theme for further research."
secondary_intents: ["Build"]
research_lenses: ["Theme / Narrative", "Technical", "Fundamental"]
mentioned_companies: []
themes: ["Artificial intelligence"]
industries: ["Semiconductors", "Software", "Cloud infrastructure", "Power infrastructure"]
time_horizon: "Unspecified"
asset_focus: "Equities"
estimated_user_sophistication: "Growing Investor"
confidence: "Medium"
clarifying_questions_needed: true
```

Field definitions:

- `original_question`: the user's exact question or request.
- `primary_domain`: the dominant Research Intent Domain.
- `primary_intent`: plain-language summary of what the user is trying to accomplish.
- `secondary_intents`: other relevant domains.
- `research_lenses`: cross-cutting research lenses implied by the question.
- `mentioned_companies`: tickers or company names explicitly mentioned.
- `themes`: named narratives or thematic exposures.
- `industries`: sectors, industries, or business categories in scope.
- `time_horizon`: stated or inferred time frame.
- `asset_focus`: equities, options, ETFs, mixed, or unspecified.
- `estimated_user_sophistication`: persona estimate used only to tune explanation depth.
- `confidence`: confidence in the interpretation, not in the investment idea.
- `clarifying_questions_needed`: whether RCE should ask before proposing artifacts.

Optional future fields:

- `geography`.
- `event_context`.
- `directional_bias`.
- `exclusions`.
- `constraints`.
- `preferred_downstream_path`.
- `universe_seed_type`.
- `requires_user_confirmation`.

---

## 6. RCE Purpose

The Research Conversation Engine is the guided workflow that turns the Research Intent Profile into user-reviewable research artifacts.

RCE exists only to:

- Understand intent.
- Clarify when necessary.
- Define a Research Mission.
- Propose a Research Universe.

RCE helps produce:

- A structured interpretation of the user's question.
- A proposed Research Mission.
- A proposed Research Strategy.
- A proposed Research Universe Definition.
- Candidate Securities with Inclusion Rationale.
- Clarifying questions where needed.
- A user-review, edit, name, and save workflow.
- A handoff to Security Research or Opportunity Research after approval.

RCE boundaries:

- RCE does not recommend trades.
- RCE does not score securities.
- RCE does not evaluate options.
- RCE does not replace analytical models.
- RCE does not become a chatbot.
- RCE does not answer arbitrary questions.
- RCE does not bypass user review.
- RCE does not change Opportunity Discovery behavior.
- RCE does not change Security Analysis Model behavior.
- RCE does not change Option Analysis Model behavior.
- RCE does not change Study Protocol behavior.
- RCE does not create investment advice or suitability conclusions.
- RCE helps translate intent into structured research artifacts.

Conversation should be brief. It should end when the Research Mission, proposed universe, and downstream path are clear enough for user review.

Research Guidance is persistent. It explains the current Research Session after the initial conversation: what the mission is, what universe is in scope, what analysis has run, what findings exist, what remains uncertain, and what refinements are possible. Guidance is contextual product support, not an open-ended AI chat transcript.

---

## 6A. Research Session and Refinement

A Research Session is the durable product record created from a user's research process.

It includes:

- Original Question.
- Research Mission.
- Research Universe.
- Findings.
- Refinements.
- Decisions.
- Saved Notes.

The Research Session is what the application remembers. It should preserve research state and evidence, not a conversation log for its own sake.

Research Refinement means modifying existing research. It may adjust the mission, universe, lenses, candidate membership, notes, findings, or downstream path. Refinement should be recorded as a structured change to the Research Session rather than treated as another turn in a generic chat.

---

## 7. Conversation Pattern

Preferred conversation flow:

User question -> "Here's how I understand your question" -> user confirmation/refinement -> proposed Research Mission -> proposed Research Universe Definition -> candidate securities with inclusion rationale -> user review/edit/name/save -> proceed to Security Research or Opportunity Research

Detailed pattern:

1. User asks a plain-language question.
2. RQT classifies intent and produces a Research Intent Profile.
3. RCE restates the interpreted question in user-facing language.
4. RCE identifies key assumptions and missing scope.
5. User confirms, corrects, or refines the interpretation.
6. RCE proposes a Research Mission.
7. RCE proposes a Research Strategy.
8. RCE proposes a Research Universe Definition.
9. RCE lists Candidate Securities with Inclusion Rationale.
10. User reviews, edits, removes, adds, names, and saves.
11. A Research Universe Snapshot is created when proceeding to analysis.
12. User chooses Security Research or Opportunity Research.

The conversation should preserve the distinction between:

- "This company may belong in the research universe."
- "This company is attractive."

RCE may say the first. It must not imply the second without downstream evidence, and even downstream evidence should remain research support rather than a trade recommendation.

---

## 8. Confidence Handling

### High-Confidence Interpretation

Example: "Micron earnings are next week. Show me calls."

Behavior:

- Restate the interpretation briefly.
- Confirm key constraints only if missing constraints materially affect the workflow.
- Proceed directly to proposed Research Mission and downstream path.
- Make the non-recommendation boundary explicit when options are involved.

Likely response style:

"Here's how I understand it: you want to research bullish MU call candidates around the upcoming earnings event, with the focus on option opportunity quality rather than a broad technical setup review."

### Medium-Confidence Interpretation

Example: "AI power companies."

Behavior:

- Restate the likely intent.
- Ask one or two clarifying questions or present assumptions for confirmation.
- Propose a draft mission and candidate scope after clarification.

Likely response style:

"I read this as a request to discover companies exposed to rising power demand from AI data centers. Before proposing a universe, I would confirm whether you mean utilities, power equipment, grid infrastructure, independent power producers, or all of the above."

### Low-Confidence Interpretation

Example: "Good retirement stocks."

Behavior:

- Avoid pretending the request is specific enough for universe construction.
- Ask clarifying questions about goals, risk tolerance, asset focus, income needs, time horizon, and research boundaries.
- Keep the conversation educational and research-oriented.
- Do not recommend securities.

Likely response style:

"I need more structure before turning this into research. 'Good retirement stocks' could mean income, low volatility, dividend growth, capital preservation, or long-term growth. I would ask what outcome you want to research before proposing any universe."

---

## 9. Persona-Aware Conversation

### Curious Beginner

Conversation style:

- Plain language.
- Short explanations of why the platform is asking a question.
- Avoid model acronyms unless introduced.
- Emphasize that candidate securities are for research, not recommendations.

RCE behavior:

- Ask fewer but clearer questions.
- Propose smaller candidate universes.
- Explain inclusion rationale in everyday terms.
- Prefer Security Research before Opportunity Research unless the user explicitly asks about options.

### Growing Investor

Conversation style:

- Use market terms with brief context.
- Show choices without overwhelming configuration.
- Explain research lenses and evidence categories.

RCE behavior:

- Offer candidate universe preview and editable rationale.
- Show likely downstream path.
- Support comparison and theme validation workflows.

### Experienced Investor / Trader

Conversation style:

- Be concise and precise.
- Respect explicit constraints such as "ignore technical setup" or "calls only."
- Surface assumptions, option constraints, and event context.

RCE behavior:

- Move quickly from interpretation to artifact proposal.
- Preserve user constraints in the Research Intent Profile.
- Offer Opportunity Research when the user requests option candidates.
- Keep trade recommendation boundaries clear.

### Research Power User

Conversation style:

- Structured and artifact-oriented.
- Expose classification, assumptions, versioning needs, and reproducibility boundaries.
- Minimize tutorial language.

RCE behavior:

- Show full Research Intent Profile when useful.
- Support universe naming, exclusions, rationale edits, and strategy selection.
- Preserve metadata needed for later comparison and Study Protocol design.

---

## 10. Representative Scenarios

### A. Beginner Theme Validation

User question: "My friend keeps talking about Caterpillar and GE Vernova because of data centers. Is that true?"

Likely RQT classification:

- Primary domain: Validate.
- Secondary domains: Learn, Compare.
- Research lenses: Theme / Narrative, Fundamental, Competitive Position, Macro Exposure.
- Asset focus: Equities.
- Confidence: High.
- Estimated user sophistication: Curious Beginner.

Research Intent Profile:

```yaml
original_question: "My friend keeps talking about Caterpillar and GE Vernova because of data centers. Is that true?"
primary_domain: "Validate"
primary_intent: "Validate whether Caterpillar and GE Vernova have credible exposure to data center growth."
secondary_intents: ["Learn", "Compare"]
research_lenses: ["Theme / Narrative", "Fundamental", "Competitive Position", "Macro Exposure"]
mentioned_companies: ["Caterpillar", "GE Vernova"]
themes: ["Data centers", "AI infrastructure", "Power demand"]
industries: ["Industrial machinery", "Power equipment", "Energy infrastructure"]
time_horizon: "Unspecified"
asset_focus: "Equities"
estimated_user_sophistication: "Curious Beginner"
confidence: "High"
clarifying_questions_needed: false
```

Likely RCE response:

"Here's how I understand your question: you want to know whether Caterpillar and GE Vernova are genuinely connected to data center growth, not whether they are automatically good investments. I would set this up as a theme-validation mission comparing each company's exposure, evidence, and risks."

Likely downstream path:

- Proposed Research Mission: validate data center exposure for CAT and GEV.
- Proposed Research Universe Definition: CAT, GEV, and optional peer/context names after review.
- Security Research first.
- Research Notebook summary after evidence review.

### B. Single-Company Opportunity

User question: "Micron earnings are next Tuesday. I don't care about technical setup. What bullish calls should I consider?"

Likely RQT classification:

- Primary domain: Opportunity Research.
- Secondary domains: Monitor.
- Research lenses: Options, Event-Driven, Risk.
- Asset focus: Options on MU.
- Confidence: High.
- Estimated user sophistication: Experienced Investor / Trader.

Research Intent Profile:

```yaml
original_question: "Micron earnings are next Tuesday. I don't care about technical setup. What bullish calls should I consider?"
primary_domain: "Opportunity Research"
primary_intent: "Research bullish MU call candidates around an earnings event while excluding technical setup from the primary workflow."
secondary_intents: ["Monitor"]
research_lenses: ["Options", "Event-Driven", "Risk"]
mentioned_companies: ["Micron"]
themes: ["Earnings event", "Semiconductors"]
industries: ["Semiconductors", "Memory"]
time_horizon: "Next Tuesday earnings event"
asset_focus: "Options"
estimated_user_sophistication: "Experienced Investor / Trader"
confidence: "High"
clarifying_questions_needed: true
```

Likely RCE response:

"Here's how I understand it: you want option research for bullish MU calls around the upcoming earnings event, and you do not want technical setup to drive the workflow. I can structure this as an Opportunity Research mission after confirming expiration range and risk constraints. This will surface research candidates, not trade recommendations."

Likely downstream path:

- Research Mission: bullish MU call opportunity research around earnings.
- Research Universe Definition: single-security MU universe.
- Research Universe Snapshot.
- Opportunity Discovery.
- Option Analysis Model and Option Analysis Explorer.
- Research Repository archive if run.

### C. Broad Theme

User question: "Show me AI stocks."

Likely RQT classification:

- Primary domain: Discover.
- Secondary domains: Build, Learn.
- Research lenses: Theme / Narrative, Fundamental, Technical.
- Asset focus: Equities.
- Confidence: Medium.
- Estimated user sophistication: Growing Investor.

Research Intent Profile:

```yaml
original_question: "Show me AI stocks."
primary_domain: "Discover"
primary_intent: "Discover securities exposed to the AI theme for further research."
secondary_intents: ["Build", "Learn"]
research_lenses: ["Theme / Narrative", "Fundamental", "Technical"]
mentioned_companies: []
themes: ["Artificial intelligence"]
industries: ["Semiconductors", "Software", "Cloud infrastructure", "Data center infrastructure"]
time_horizon: "Unspecified"
asset_focus: "Equities"
estimated_user_sophistication: "Growing Investor"
confidence: "Medium"
clarifying_questions_needed: true
```

Likely RCE response:

"Here's how I understand your question: you want a starting universe of companies exposed to AI. AI is broad, so I would first clarify whether you want chips, cloud software, data center infrastructure, power infrastructure, or a mixed starter universe."

Likely downstream path:

- Clarification.
- Proposed AI Research Universe Definition.
- Candidate Securities with inclusion rationale.
- User review/edit/name/save.
- Security Research first; Opportunity Research optional later.

### D. Industry Exploration

User question: "I'd like to know the most promising retail stocks."

Likely RQT classification:

- Primary domain: Discover.
- Secondary domains: Evaluate, Compare.
- Research lenses: Fundamental, Competitive Position, Valuation, Risk.
- Asset focus: Equities.
- Confidence: Medium.
- Estimated user sophistication: Growing Investor.

Research Intent Profile:

```yaml
original_question: "I'd like to know the most promising retail stocks."
primary_domain: "Discover"
primary_intent: "Explore retail stocks that may be promising enough for deeper research."
secondary_intents: ["Evaluate", "Compare"]
research_lenses: ["Fundamental", "Competitive Position", "Valuation", "Risk"]
mentioned_companies: []
themes: ["Retail"]
industries: ["Retail", "Consumer discretionary", "Consumer staples"]
time_horizon: "Unspecified"
asset_focus: "Equities"
estimated_user_sophistication: "Growing Investor"
confidence: "Medium"
clarifying_questions_needed: true
```

Likely RCE response:

"Here's how I understand it: you want to explore retail companies and compare which ones may deserve deeper research. I would clarify whether 'promising' means growth, turnaround potential, resilience, valuation, market-share gains, or options opportunity."

Likely downstream path:

- Clarify promising criteria.
- Build a Retail Research Universe Definition.
- Security Research and comparison.
- Research Notebook observations.

### E. Government Spending

User question: "What companies does the DoD have an eye on investing in?"

Likely RQT classification:

- Primary domain: Discover.
- Secondary domains: Validate, Monitor.
- Research lenses: Macro Exposure, Event-Driven, Fundamental, Theme / Narrative.
- Asset focus: Equities.
- Confidence: Medium.
- Estimated user sophistication: Growing Investor.

Research Intent Profile:

```yaml
original_question: "What companies does the DoD have an eye on investing in?"
primary_domain: "Discover"
primary_intent: "Identify public companies potentially exposed to Department of Defense investment priorities or funding attention."
secondary_intents: ["Validate", "Monitor"]
research_lenses: ["Macro Exposure", "Event-Driven", "Fundamental", "Theme / Narrative"]
mentioned_companies: []
themes: ["Defense spending", "Government investment", "National security priorities"]
industries: ["Defense", "Aerospace", "Cybersecurity", "Semiconductors", "Energy", "Advanced manufacturing"]
time_horizon: "Unspecified"
asset_focus: "Equities"
estimated_user_sophistication: "Growing Investor"
confidence: "Medium"
clarifying_questions_needed: true
```

Likely RCE response:

"Here's how I understand your question: you want to research publicly traded companies that may benefit from DoD funding priorities, contracts, or strategic investment attention. I would clarify whether you mean current contracts, announced investment programs, policy priorities, or a watchlist to monitor."

Likely downstream path:

- Clarify funding type and source expectations.
- Build defense/government-priority candidate universe.
- Security Research.
- Future Monitor workflow if the user wants repeated updates.

### F. Competitive Positioning

User question: "What fashion brands are best positioned to take market share?"

Likely RQT classification:

- Primary domain: Compare.
- Secondary domains: Discover, Evaluate.
- Research lenses: Competitive Position, Fundamental, Valuation, Theme / Narrative.
- Asset focus: Equities.
- Confidence: Medium.
- Estimated user sophistication: Growing Investor.

Research Intent Profile:

```yaml
original_question: "What fashion brands are best positioned to take market share?"
primary_domain: "Compare"
primary_intent: "Compare public fashion and apparel brands for market-share positioning."
secondary_intents: ["Discover", "Evaluate"]
research_lenses: ["Competitive Position", "Fundamental", "Valuation", "Theme / Narrative"]
mentioned_companies: []
themes: ["Fashion", "Market share", "Consumer brands"]
industries: ["Apparel", "Footwear", "Luxury", "Retail"]
time_horizon: "Unspecified"
asset_focus: "Equities"
estimated_user_sophistication: "Growing Investor"
confidence: "Medium"
clarifying_questions_needed: true
```

Likely RCE response:

"Here's how I understand it: you want to compare public fashion and apparel brands by competitive position and market-share potential. I would clarify whether you want luxury, athletic apparel, broad apparel retail, footwear, or a mixed public-company universe."

Likely downstream path:

- Clarify fashion segment.
- Proposed comparative Research Universe Definition.
- Security Research with competitive-position lens.
- Research Notebook comparison summary.

### G. Infrastructure Theme

User question: "Research energy companies with promising power build-out coming online in the next 24 months."

Likely RQT classification:

- Primary domain: Discover.
- Secondary domains: Evaluate, Monitor, Build.
- Research lenses: Fundamental, Macro Exposure, Event-Driven, Theme / Narrative, Risk.
- Asset focus: Equities.
- Confidence: High.
- Estimated user sophistication: Experienced Investor / Trader.

Research Intent Profile:

```yaml
original_question: "Research energy companies with promising power build-out coming online in the next 24 months."
primary_domain: "Discover"
primary_intent: "Identify and research energy companies with meaningful power capacity or infrastructure build-out expected within 24 months."
secondary_intents: ["Evaluate", "Monitor", "Build"]
research_lenses: ["Fundamental", "Macro Exposure", "Event-Driven", "Theme / Narrative", "Risk"]
mentioned_companies: []
themes: ["Power build-out", "Energy infrastructure", "Data center power demand"]
industries: ["Utilities", "Independent power producers", "Power infrastructure", "Energy"]
time_horizon: "24 months"
asset_focus: "Equities"
estimated_user_sophistication: "Experienced Investor / Trader"
confidence: "High"
clarifying_questions_needed: true
```

Likely RCE response:

"Here's how I understand it: you want to build a research universe of energy companies with power infrastructure or capacity additions expected within the next 24 months. I would clarify whether you want regulated utilities, independent power producers, grid equipment, generation developers, or a mixed infrastructure universe."

Likely downstream path:

- Clarify energy segment and build-out evidence.
- Proposed Research Mission and Research Strategy.
- Proposed Research Universe Definition with inclusion rationale.
- Security Research first.
- Monitor or Study Protocol design later if repeated tracking is desired.

---

## 11. Prompting Strategy

This document does not implement prompts. It defines future prompt template needs.

Future prompt templates:

- Classification prompt: converts the original user question into a Research Intent Profile with domain, lenses, entities, scope, sophistication estimate, confidence, and clarification need.
- Clarification prompt: asks the smallest useful number of questions needed to improve the Research Intent Profile before artifact generation.
- Candidate universe generation prompt: proposes Candidate Securities, inclusion rationale, exclusions, uncertainty notes, and source needs for user review.
- Research mission summary prompt: creates a concise Research Mission and Research Strategy from the confirmed Research Intent Profile.
- Inclusion rationale prompt: explains why each Candidate Security may belong in the proposed Research Universe without implying attractiveness, ranking, or recommendation.

Prompt design constraints:

- Prompts must preserve non-recommendation boundaries.
- Prompts must separate intent classification from security analysis.
- Prompts must ask for user confirmation where confidence is low or scope is broad.
- Prompts must avoid making unsupported factual claims when fresh data is required.
- Prompts must produce reviewable artifacts, not autonomous decisions.

---

## 12. Relationship to Existing Documentation

Related product and architecture documents:

- `docs/product/Product_Vision_and_Experience_Architecture.md` defines the broader product vision and experience philosophy.
- `docs/architecture/Research_Roadmap.md` places RQT and RCE in the planned platform evolution.
- `docs/glossary/Stock_Screener_Domain_Model_and_Glossary.md` defines domain terms used by this specification.
- `docs/research/Research_Notebook.md` records the design milestone and future research questions.
- `docs/architecture/Research_Universe_Design_Specification.md` defines the universe artifact that RCE eventually proposes and the snapshot downstream analysis consumes.

This specification refines the upstream intent layer that comes before Research Universe Definition and Snapshot creation.

---

## Non-Goals

- No executable implementation.
- No prompt implementation.
- No database schema change.
- No scoring change.
- No Opportunity Discovery behavior change.
- No Security Analysis Model behavior change.
- No Option Analysis Model behavior change.
- No Study Protocol behavior change.
- No cloud infrastructure change.
- No repository behavior change.
- No UI behavior change.
- No trade recommendation behavior.

---

## Design Status

Status: Designed / Planned.

Version: v0.1.

Validation requirement: documentation-only changes plus existing test and compile checks.
