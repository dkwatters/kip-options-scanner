# Product Vision and Experience Architecture v1.0

## Purpose

This document defines the product vision and experience architecture for the Kip Options research platform.

It sits above technical architecture, model specifications, and PRDs. It describes what the platform is, who it serves, what user questions it helps answer, and how the experience should guide a user from an investment idea to repeatable research.

This is a product document, not an implementation plan. It does not define scoring rules, model parameters, database schema, APIs, cloud infrastructure, or executable behavior.

---

## 1. Product Vision

Kip Options is a configurable investment research platform that translates an investor's question, thesis, or mission into a repeatable research workflow.

The platform helps users move from "I have an idea" to "I have evidence I can review, compare, and revisit." It is designed to organize research around the user's intent, not around a default scanner, chart, model, or data feed.

At its best, the platform should feel like a research workspace that can adapt to different levels of investor sophistication. A beginner should be able to start with a plain-language question. An experienced researcher should be able to configure universes, compare strategies, inspect model behavior, and study outcomes over time.

The product vision is not to predict markets or tell users what to buy. The vision is to help investors form better questions, create structured research processes, preserve observations, and compare evidence over time.

The formal upstream design for classifying user questions and turning them into conversation artifacts is documented in `docs/product/Research_Question_Taxonomy_and_Conversation_Design.md`.

---

## 2. Core Product Belief

Nothing we build matters if we do not start with the user's question, mission, and entry point.

Every major experience should begin by understanding what the user is trying to accomplish. The same platform can support discovery, comparison, monitoring, education, and historical study, but only if the user intent is clear before the product exposes data, models, or configuration.

The central product question is:

What are we researching?

The platform begins with curiosity rather than tickers.

Conversation starts the process. Evidence completes it.

The application remembers research rather than conversations. A conversation may briefly clarify intent, but the durable product object is the Research Session: the original question, mission, proposed or approved universe, findings, refinements, decisions, and saved notes that can be revisited later. Message history is not the platform memory model.

Product principles:

- Every investment begins with curiosity.
- Conversation starts the process. Evidence completes it.
- AI facilitates research. It does not perform research.
- The platform remembers research, not conversations.
- The best interface is the one users stop noticing after the first minute.

---

## 3. What Problem We Are Solving

Investors are surrounded by data, tools, metrics, charts, screeners, social opinions, analyst commentary, and market narratives.

More data does not automatically create better research. Many users can find lists of stocks, charts, option chains, indicators, or headlines, but still struggle to answer basic research questions:

- Where should I start?
- Why is this company interesting?
- Which securities are actually in scope for this idea?
- What evidence supports or weakens the thesis?
- Is this opportunity interesting once quality, risk, and context are considered?
- Have similar research approaches worked better or worse over time?

The problem is not only information access. The problem is turning an investment idea into structured, repeatable evidence.

The platform exists to close that gap.

---

## 4. Experience Philosophy

The product experience should follow these principles:

- Questions before data.
- Research before recommendations.
- Ideas before indicators.
- Repeatable observations before opinions.
- Progressive sophistication.
- Complexity should be revealed as the user becomes ready for it.

The platform should avoid forcing every user into the same advanced workflow. A beginner does not need to see every model, configuration option, or diagnostic view. A power user should not be trapped in a simplified interface that hides the levers needed for serious research.

The experience should begin with plain-language intent, then progressively introduce research structure:

- What is the user trying to understand?
- What securities should be studied?
- What evidence should be collected?
- What observations are repeatable?
- What comparisons are useful?
- What confidence, if any, is justified by the evidence?

---

## 5. User Sophistication Levels / Personas

### A. Curious Beginner

The Curious Beginner is an investor with little knowledge of options, market structure, volatility, liquidity, momentum, or technical analysis.

Example user:

A 20-year-old investor who believes artificial intelligence is important but does not yet know how to research companies, evaluate setups, or understand option quality.

Mission examples:

- "I think AI is important. Where do I start?"
- "Help me understand what companies are interesting."
- "What should I learn before comparing these stocks?"

Experience needs:

- Simple language.
- Guided entry.
- Education built into the workflow.
- Minimal exposed complexity.
- Clear explanations of why the platform is asking for a choice.
- Research summaries that teach without overwhelming.

For this user, the platform should feel like a guided research assistant. It should help the user form a reasonable first Research Mission, select or create an understandable Research Universe, and learn what evidence is being collected.

### B. Growing Investor

The Growing Investor understands basic stock concepts and some market language. This user may know what sectors, growth stocks, risk, and price trends are, but may not be ready for advanced model diagnostics or deep option analysis.

Mission examples:

- "Show me strong stocks in a theme."
- "Help me understand why this stock looks interesting."
- "Find companies in my watchlist that look worth studying."

Experience needs:

- Introduce trend, momentum, quality, and risk in plain language.
- Keep advanced technical detail available but not dominant.
- Explain observations as evidence, not certainty.
- Show comparison across securities without forcing model configuration.
- Let the user save or revisit research.

For this user, the platform should support guided exploration and comparison. It should make clear which securities are being studied, why they are in scope, and what the platform observed.

### C. Experienced Investor / Trader

The Experienced Investor / Trader has a medium understanding of technical analysis, option quality, and research process. This user may already have theses, watchlists, and preferred strategies.

Mission examples:

- "Build a research universe around my thesis."
- "Compare technical setups with option quality."
- "Help me find opportunities that fit my strategy."

Experience needs:

- Expose Research Universes.
- Expose Security Analysis.
- Expose Opportunity Discovery.
- Expose Option Analysis.
- Expose Study Protocols.
- Support inspection of model behavior and near misses.
- Preserve enough context to make repeated research comparable.

For this user, the platform should behave like a configurable research cockpit. It should allow a thesis to become a defined universe, a defined universe to become repeatable observations, and observations to become evidence that can be compared over time.

### D. Research Power User

The Research Power User wants configuration, comparison, automation, historical analysis, and repeatability. This user cares not only about individual securities or opportunities, but also about whether research strategies behave differently across time and market conditions.

Mission examples:

- "Compare momentum-generated universes against manually curated universes."
- "Evaluate which research strategies performed better over time."
- "Track model behavior across different market regimes."

Experience needs:

- Advanced configuration.
- Study Protocol creation and comparison.
- Model comparison.
- Outcome tracking.
- Historical research.
- Research strategy comparison.
- Automation and scheduled observation.
- Clear separation between evidence, interpretation, and decisions.

For this user, the platform should support research programs, not just one-time scans. It should help compare strategies, evaluate consistency, and preserve historical context.

---

## 6. The Research Journey

The full question-driven research journey is:

Question
-> Research Conversation
-> Research Guidance
-> Research Mission
-> Research Universe
-> Security Analysis
-> Opportunity Discovery
-> Findings
-> Research Refinement

The earlier technical shorthand remains useful after intent has been translated:

User Question / Mission -> Research Strategy -> Research Universe -> Security Research -> Opportunity Research -> Historical Observation -> Confidence / Decision

This journey is not always linear. A user may start with a broad question, discover an interesting security, refine the universe, run a new strategy, or compare observations across time.

The product should still preserve the conceptual order:

- Start with intent.
- Define how the intent will be investigated.
- Identify the securities in scope.
- Study the underlying securities.
- Study the opportunities that appear within that population.
- Preserve observations.
- Help the user decide what level of confidence is justified.

The final step is not a platform recommendation. It is a user decision informed by structured evidence.

---

## 6A. Beginner-First Entry

Natural-language questions are the primary entry point because the first problem for many users is not finding a ticker box. It is forming a researchable question.

A beginner may start with "I think AI is important" or "What should I know before comparing retail stocks?" The product should accept that plain-language curiosity, clarify only what is needed, and translate it into a Research Mission and Research Universe the user can review.

This does not mean experienced users should be slowed down. Advanced users should retain rapid access to Research Universes, Security Research, Opportunity Research, Study Protocols, and the Research Repository. Beginner-first means the default entry path is understandable without market fluency, while expert paths remain direct and efficient.

---

## 7. Research Mission

A Research Mission is the top-level user intent.

It answers:

What is the user trying to research?

A Research Mission may be an explicit thesis, an exploratory question, or a comparison the user wants to run.

Examples:

- "AI infrastructure spending will keep growing."
- "Find technically strong growth stocks."
- "Find quality option opportunities in my watchlist."
- "Compare which research approach works best."

The Research Mission should be the natural starting point for the product experience. It gives the platform enough context to suggest a Research Strategy, select or create a Research Universe, and guide the user through appropriate analysis.

---

## 8. Research Strategy

A Research Strategy is how the platform investigates the Research Mission.

It may define:

- How the Research Universe is selected or generated.
- Which analysis models are used.
- What observations are collected.
- What comparisons are being made.
- What study or protocol is being run.
- What evidence should be revisited later.

The strategy should be understandable to the user. A beginner may see it as a guided plan. An advanced user may see it as a configurable research design.

Research Strategy is the bridge between intent and execution. It prevents the product from jumping directly from a user question to a generic scan.

---

## 9. Research Conversation Engine

The Research Conversation Engine (RCE) is the guided product workflow that translates a user's plain-language research question into structured research artifacts the user can review before analysis begins.

RCE is fed by the Research Question Taxonomy (RQT), which classifies the user's research intent before the conversation proposes a mission, strategy, or universe. RQT is a taxonomy of intent, not a list of canned questions.

RCE helps the user move quickly from a question to a reviewable candidate research artifact:

- The user's intent.
- What the Research Mission is.
- The ephemeral Research Map used to decompose the investable ecosystem.
- Which portions of that map are included or excluded.
- Which securities are plausible candidates.
- Why each candidate security may belong in scope.
- What should be included, excluded, renamed, or saved.
- Which downstream research path should run next.
- What assumptions were made so the user can refine rather than wait through clarification.

RCE is AI-assisted, but not autonomous. It proposes an AI-Assisted Research Universe Definition for user review. The user may edit the candidate list, inclusion rationale, name, purpose, and boundaries before saving a User-Approved Research Universe.

The v1.0 RCE policy is Research Launch. For reasonably interpretable company, theme, industry, or market questions, RCE should return a concise interpretation, assumptions, proposed research mission, dynamic Research Map, included areas, excluded areas, Proposed Research Universe, candidate securities, and coverage assessment immediately. If interpretation confidence is at or above the configurable threshold, default `0.70`, RCE must not ask clarifying questions. It may ask one optional clarification only when confidence is below threshold, and the next response must terminate in a Proposed Research Universe.

RCE constructs a fresh Research Map for each research session before it proposes companies. The map is an ephemeral reasoning artifact, not a manually curated taxonomy. It explains how the model decomposed the user's topic, why certain subdomains are in scope, and which adjacent areas were intentionally left out.

The formal methodology for Proposed Research Universe construction is RUCS, documented in `docs/product/Research_Universe_Construction_Standard.md`. RUCS requires research usefulness over popularity, coverage before ranking, Research Map first and company list second, explicit included/excluded/adjacent areas, candidate selection standards, informational diversity, visible assumptions, and refinement readiness.

The intended internal RCE reasoning workflow is User Question -> Interpretation -> Research Planning -> Universe Construction -> Universe Review -> User Presentation. The user should see a clean research launch, while the system preserves clear internal stages for intent classification, analyst-style planning, candidate construction, quality review, and presentation.

RCE interpretation is model-agnostic. The platform should depend on a Research Conversation provider interface rather than a specific AI vendor, model family, or hosted API. Provider metadata should preserve the provider name, model name, prompt version, request timestamp, response timestamp, structured response, confidence, warnings, errors, and optional raw response so future implementations can compare interpretations across providers without changing downstream research behavior.

The first live provider implementation is OpenAI-backed RCE interpretation. It is selected with `RCE_PROVIDER=openai`, uses `OPENAI_API_KEY`, and may set `RCE_OPENAI_MODEL`; otherwise the deterministic mock provider remains available for local setup and tests. OpenAI output is session-only in the Research Workspace for now. It does not save Research Universe Definitions, create Research Universe Snapshots, run SAM, OD, or OAM, or change scoring, Study Protocol, cloud job, database, or repository behavior.

RCE boundaries:

- RCE exists only to understand intent, state assumptions, clarify only when confidence is too low, define a Research Mission, and propose a Research Universe.
- RCE does not score securities.
- RCE does not evaluate options.
- RCE does not recommend trades.
- RCE does not create investment advice or suitability conclusions.
- RCE does not replace analytical models.
- RCE does not become a chatbot.
- RCE does not answer arbitrary questions outside the research workflow.
- RCE only helps translate user intent into structured research artifacts.

The RCE workflow is:

User question -> optional clarification when confidence is too low -> dynamic Research Map -> included/excluded scope -> Proposed Research Universe -> coverage assessment -> user review/edit/name -> Research Universe Definition -> Research Universe Snapshot -> SAM/SAE -> OD/OAM/OAE -> Research Repository

RCE should feel like a short research launch, not an extended AI conversation, while preserving the same disciplined research boundaries downstream.

The detailed RQT/RCE conversation model, including intent domains, lenses, confidence handling, personas, representative scenarios, and future prompt template needs, is specified in `docs/product/Research_Question_Taxonomy_and_Conversation_Design.md`.

---

## 9A. Research Conversation vs Research Guidance

Research Conversation and Research Guidance are related but distinct.

Research Conversation is intentionally short. It exists at the beginning of a workflow to understand intent, state assumptions, ask no more than one necessary clarifying question, define a Research Mission, and terminate with a Proposed Research Universe. It should produce a useful candidate artifact first whenever the question is reasonably interpretable. Future follow-up questions are Research Refinements that update the Research Mission and Proposed Research Universe; they do not reopen the original conversation.

Research Guidance is persistent. It remains available throughout a Research Session to explain what the user is looking at, why a research step exists, what evidence has been collected, what is still missing, and what refinements are possible. Guidance is not a free-form chat transcript. It is contextual product support attached to the current mission, universe, evidence, findings, and saved notes.

Conversation starts the process. Research artifacts persist. Guidance keeps the research understandable. Evidence completes it.

---

## 9B. Research Session

A Research Session is the first-class record of a user's research process.

It should preserve:

- Original Question.
- Research Mission.
- Research Universe.
- Findings.
- Refinements.
- Decisions.
- Saved Notes.

The Research Session is the durable memory of the application. It records what was researched, what evidence was found, what the user changed, and what the user decided to save. It does not preserve conversation for its own sake.

Research Sessions allow a user to return later and understand the research path without replaying an AI chat. The user should be able to see the original question, the approved universe, security analysis, opportunity discovery results, findings, refinements, and notes as a coherent research artifact.

---

## 9C. Research Refinement

Research Refinement is a modification to existing research, not a continuation of an AI chat.

A refinement may:

- Narrow or broaden a Research Universe.
- Add or remove candidate securities.
- Change a research lens.
- Shift from Security Research to Opportunity Research.
- Save a new note or decision.
- Create a new snapshot for comparison.
- Re-run analysis with a clearer mission.

Refinement should be explicit and attributable to the Research Session. The platform should show what changed and why, so later findings can be interpreted against the correct mission, universe, and evidence.

---

## 10. AI-Assisted Research Universe Definition

An AI-Assisted Research Universe Definition is a proposed Research Universe Definition created from a user's Research Mission and reviewed before use.

It should include:

- Mission interpretation.
- Dynamic Research Map generated for the session.
- Included and excluded areas from that map.
- Candidate securities.
- Inclusion rationale for each candidate.
- Selection boundaries and exclusions.
- Suggested name and purpose.
- Source notes and confidence limitations.
- Coverage assessment explaining which ecosystem areas are represented or intentionally omitted.

It is not final until the user reviews, edits, names, and saves it. After approval, it becomes a User-Approved Research Universe and can be materialized as a Research Universe Snapshot.

---

## 11. Research Universe

A Research Universe is the set of securities being studied for a Research Mission or Research Strategy.

It is the bridge between an investment idea and analysis.

A Research Universe may be:

- Manually defined by the user.
- Selected from a predefined list.
- Dynamically generated from criteria.
- Reused across repeated studies.

Downstream analysis should not care how the Research Universe was created. Once the population is selected, Security Research, Opportunity Research, Study Protocols, and historical comparisons should treat it as the defined set of securities in scope.

Product terminology should use Research Universe consistently.

"Corpus" should not be used as a product term. "Reference Universe" has been superseded by Research Universe and Research Universe Definition.

Research Universe Definition is the saved description or recipe for a universe. A point-in-time Research Universe Snapshot preserves the exact securities studied during a specific observation.

---

## 12. Security Research and Opportunity Research

The product experience is evolving toward two parallel research domains.

### Security Research

Security Research analyzes the underlying securities.

It helps answer:

- What is happening with this security?
- What is its observable condition?
- How does it compare with the rest of the Research Universe?
- How has it behaved across repeated observations?

The user-facing model is the Security Analysis Model.

The user-facing explorer is the Security Analysis Explorer.

Security Research should help users understand the underlying securities before they evaluate specific opportunities.

### Opportunity Research

Opportunity Research discovers and analyzes opportunities within a Research Universe. Today, those opportunities are options.

It helps answer:

- What opportunities are visible now?
- Which opportunities satisfy the active quality model?
- Which opportunities are close but not yet acceptable?
- How did the opportunity analysis behave across a universe or study?

Opportunity Discovery remains the discovery component.

The user-facing model is the Option Analysis Model.

The user-facing explorer is the Option Analysis Explorer.

Opportunity Research should help users inspect opportunity quality without hiding the underlying research context.

---

## 13. Progressive Disclosure

The same platform should serve all four personas by exposing more sophistication only when it helps the user accomplish the mission.

Progressive disclosure means:

- Beginners start with questions, guided workflows, and explanations.
- Growing investors see comparisons, research summaries, and plain-language factors.
- Experienced users access Research Universes, Security Research, Opportunity Research, and Study Protocols.
- Power users configure strategies, compare historical behavior, and evaluate outcomes.

Complexity should be available, but not forced.

The product should reveal advanced tools when they answer the user's next question:

- "Why is this security interesting?"
- "What changed since the last observation?"
- "How does this universe compare with another one?"
- "Which research strategy produced better evidence?"
- "What happened after these opportunities appeared?"

---

## 14. What Makes the Platform Different

The platform is different because it organizes research, not just data.

It does not stop at showing a scanner result or a chart. It helps users connect a question to a research process, preserve the observations, and compare evidence over time.

Key differentiators:

- It starts from the user's mission.
- It organizes securities into explicit Research Universes.
- It separates security research from opportunity research.
- It remembers observations.
- It supports repeatable Study Protocols.
- It compares research strategies over time.
- It helps users move from question to evidence.

The platform should make research more structured, more reviewable, and more repeatable.

---

## 15. User Stories for RCE

### Curious Beginner

As a Curious Beginner, I want to describe an idea like "I think AI is important" and see a plain-language proposed universe, so I can understand which companies might be worth researching and why they were included.

RCE should keep the workflow simple: interpret the question, propose a small candidate universe with readable inclusion rationale, let the user remove unfamiliar or unwanted names, and save the universe before proceeding to Security Research.

### Growing Investor

As a Growing Investor, I want RCE to turn a theme, watchlist, or sector idea into a reviewable universe, so I can compare securities without needing to configure technical gates or model internals.

RCE should show candidate securities, explain each inclusion as research scope rather than a recommendation, support edits and naming, and let the user choose Security Research or Opportunity Research after saving.

### Experienced Investor / Trader

As an Experienced Investor / Trader, I want RCE to help structure my thesis into a Research Universe Definition, so I can preserve the universe boundary before running SAM, OD, or option analysis.

RCE should expose more control over candidate membership, exclusions, naming, rationale, and snapshot timing while keeping OAM, SAM, and Study Protocol behavior unchanged.

### Research Power User

As a Research Power User, I want RCE-generated universe definitions to be reviewable, versionable, and comparable with manually curated universes, so I can study how different research population designs behave over time.

RCE should preserve structured interpretation, candidate rationale, user edits, approval state, and snapshot identity so downstream evidence remains reproducible.

---

## 16. First-Pass RCE UX Proposal

The first RCE experience should live in a Research Workspace landing page rather than inside a scanner or diagnostics view.

Implemented conversation-forward landing-page direction:

1. Research Workspace opens with the user's curiosity: "What can I help you understand today?"
2. The natural-language question box is the dominant first action and captures a plain-language question, thesis, theme, company, opportunity request, comparison request, or learning topic.
3. Four coaching cards provide optional starting rails: Explore an Investment Idea, Research a Company, Find Investment Opportunities, and Compare & Learn.
4. Selecting a coaching card prefills the question box, stores the selected research path, and shows a placeholder conversation preview without navigating away or running analysis.
5. When a question is entered, the page shows interpretation, Proposed Research Mission, Research Map, Included Areas, Excluded Areas, Candidate Companies, Coverage Assessment, Assumptions, and Ways to Refine before analysis begins.
6. Continue Previous Research shows available CSV-backed Research Universes and recent observations when available.
7. Already know where you want to go? lets experienced users skip directly to Security Research, Opportunity Research, or the Research Repository.

Current implementation boundary:

- The landing page captures the research question and can call the configured RCE provider for session-only interpretation.
- RCE is not a chatbot wrapper. Conversation initiates research; evidence completes it.
- It can classify intent and display Candidate Securities for review when the provider returns them.
- It does not save a Research Universe Definition.
- It does not change Security Research, Opportunity Research, repository behavior, scoring, or analytical model behavior.

Future full RCE flow:

1. Research Workspace landing page asks: "What are we researching?"
2. Mission input prompt accepts a plain-language question, thesis, theme, or watchlist intent.
3. RCE structured interpretation summarizes the question, likely scope, assumptions, and suggested research path.
4. Proposed universe preview leads with the dynamic Research Map, then lists Included Areas, Excluded Areas, Candidate Securities with Inclusion Rationale, Coverage Assessment, Assumptions, and Ways to Refine, defaulting to the first 25 rows with an option to inspect more when available.
5. User can edit membership, remove candidates, adjust rationale notes, choose or edit the universe name, and save.
6. Saving creates a Research Universe Definition in an approved state.
7. The platform materializes a Research Universe Snapshot when the user proceeds to analysis.
8. The user chooses Security Research or Opportunity Research as the next step.

The preview should clearly distinguish "candidate for research" from "recommended investment" and include the note: "This is a candidate research list, not an investment recommendation." Controls should emphasize review, edit, name, save, refine, and proceed.

---

## 17. Design Implications

Future UX should begin with one of these questions:

- "What are you trying to accomplish today?"
- "What are we researching?"
- "What can I help you understand today?"

The experience should not default directly into a scanner, chart, preselected universe, or diagnostics page.

Design implications:

- The home experience should orient around the user's plain-language question before asking for tickers, universes, or analytical controls.
- The Research Workspace should support an RCE mission input prompt before showing scanners or model diagnostics.
- RCE should present structured interpretation and guidance after the initial question, then move toward reviewable research artifacts.
- RCE should not feel like a generic chatbot wrapper; conversation is the entry point, not the evidence layer.
- Candidate Securities should include Inclusion Rationale and should be editable before approval.
- The user should be able to select, create, or refine a Research Universe as part of the workflow.
- Security Research and Opportunity Research should feel connected but distinct.
- Beginner, intermediate, and advanced modes should expose different levels of control.
- Saved research should preserve the mission, strategy, universe, observations, and interpretation.
- Explanations should be contextual, not generic education blocks detached from the workflow.

The product should make the user's intent visible throughout the experience.

---

## 18. Future Experience Direction

The likely future home page is a Research Workspace.

The Research Workspace should help users:

- Start from a Research Mission.
- Select or create a Research Universe.
- Choose a guided or advanced Research Strategy.
- Run Security Research and Opportunity Research in context.
- Save observations.
- Review prior studies.
- Compare strategies historically.
- Validate outcomes over time.

Future experience directions include:

- Guided research creation.
- Beginner, intermediate, and advanced modes.
- Research Universe selection and creation as a core workflow.
- AI-assisted Research Mission interpretation.
- AI-assisted Research Universe Definition proposal with user approval.
- RUCS-guided Proposed Research Universe review.
- Future experimental Research Utility Score for assessing the quality of a Proposed Research Universe as a research artifact, not the quality of its securities.
- AI-assisted Research Strategy creation.
- Historical strategy comparison.
- Outcome validation.
- Clear separation between exploratory research and repeatable Study Protocols.

AI assistance should eventually help users translate plain-language missions into structured strategies. It should not bypass user understanding or turn the platform into a recommendation engine.

---

## 19. Relationship to Technical Architecture

Existing platform components already support this vision conceptually:

- Research Conversation Engine should become the upstream intent-translation layer.
- Research Repository preserves observations and evidence.
- Study Protocols make repeated research comparable.
- Security Analysis Model supports Security Research.
- Opportunity Discovery finds visible opportunities within a Research Universe.
- Option Analysis Model supports Opportunity Research.
- Cloud execution supports scheduled and repeatable observation.

These components are technical foundations for the product vision, but the user experience should not begin with technical components. It should begin with the user's mission and progressively reveal the supporting system as needed.

The product vision guides how these components should be presented, connected, and explained.

---

## Documentation Notes

This document is intentionally non-technical. Detailed architecture, domain terminology, and model behavior are documented separately:

- `docs/architecture/Research_Roadmap.md`
- `docs/architecture/Research_Universe_Design_Specification.md`
- `docs/product/Research_Universe_Construction_Standard.md`
- `docs/glossary/Stock_Screener_Domain_Model_and_Glossary.md`
- `docs/research/Research_Notebook.md`
