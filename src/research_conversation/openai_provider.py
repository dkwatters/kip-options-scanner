from __future__ import annotations

import json
from typing import Any

from src.research_conversation import (
    DEFAULT_RCE_CONFIDENCE_THRESHOLD,
    DEFAULT_RCE_PROMPT_VERSION,
    ProviderMetadata,
    RCE_PARSER_MODE,
    RCE_SCHEMA_VERSION,
    ResearchConversationRequest,
    ResearchConversationResponse,
    apply_research_launch_policy,
    empty_research_conversation_structure,
    rce_candidate_count,
    utc_now,
    with_rce_diagnostics,
)


OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
RCE_OPENAI_MODEL_ENV = "RCE_OPENAI_MODEL"
DEFAULT_RCE_OPENAI_MODEL = "gpt-4.1-mini"
OPENAI_PROVIDER_NAME = "openai"
LIVE_OPENAI_PROVIDER_VERIFICATION_MARKER = "LIVE_OPENAI_RCE_RESPONSE"

OPENAI_RCE_RESPONSE_FORMAT = {
    "type": "json_schema",
    "name": "rce_response",
    "strict": False,
    "schema": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": True,
    },
}

OPENAI_RCE_ENRICHMENT_RESPONSE_FORMAT = {
    "type": "json_schema",
    "name": "rce_enrichment_response",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "candidate_securities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": ["string", "null"]},
                        "company_name": {"type": "string"},
                        "discovery_lenses": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": [
                                    "direct_competitors",
                                    "industry_landscape_peers",
                                    "value_chain_relationships",
                                    "adjacent_beneficiaries",
                                    "substitution_disruption_threats",
                                    "cross_seed_dependencies",
                                ],
                            },
                        },
                        "related_seed_matching_keys": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "reason_discovered": {"type": "string"},
                        "evidence_references": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "ticker",
                        "company_name",
                        "discovery_lenses",
                        "related_seed_matching_keys",
                        "reason_discovered",
                        "evidence_references",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["candidate_securities"],
        "additionalProperties": False,
    },
}

RCE_SYSTEM_PROMPT = """You are the Research Conversation Engine for an investment research platform.

Your job is NOT to recommend investments.

Your job is to translate a user's natural-language question into structured research artifacts.
Think like a senior investment analyst, research librarian, and thematic equity researcher constructing the first draft of a study.
Do not answer the user's question directly. Build the best possible Proposed Research Universe for downstream deterministic analysis.

Core behavior:
- The conversation exists only to launch structured research.
- Use a maximum two-turn model: user question, optional clarification only when confidence is below threshold, then Proposed Research Universe.
- If interpretation confidence is at least 0.70, do not ask clarifying questions.
- If the question is reasonably interpretable, return a candidate research universe immediately.
- Treat assumptions as defaults instead of asking blocking scope questions.
- Follow-up questions after the proposal are Research Refinements that update the mission and proposed universe; they do not reopen the original conversation.
- For a reasonably interpretable theme, company, or industry question, include 25 to 50 candidate securities when appropriate.
- Optimize candidate selection for ecosystem coverage, not popularity.
- Avoid defaulting only to mega-cap companies when the theme supports a broader representative universe.

Multi-stage RCE artifact workflow:
1. Interpretation: understand what the user is really asking and output interpretation / Research Intent Profile fields.
2. Research Planning: determine how an analyst would structure the research and output research_plan.
3. Universe Construction: construct proposed_research_universe with candidate securities.
4. Universe Review: evaluate whether the proposed universe is useful before showing it and output universe_review.
5. User Presentation: translate internal artifacts into user-friendly guidance and output user_presentation.

Research Universe construction methodology:
1. Interpret the research objective: primary theme, research focus, and implied investment question.
2. Construct a dynamic Research Map before selecting companies. Decompose the investable ecosystem into logical subdomains relevant to this specific question. Do not depend on manually maintained taxonomies.
3. Decide which parts of the Research Map are in scope, which adjacent areas should be excluded, and which blind spots remain.
4. Construct the Proposed Research Universe with ticker, company, subdomain, why it belongs, and confidence.
5. Review completeness, relevance, informational diversity, missing areas, weak candidates, redundant candidates, and recommended improvements.
6. Present clean user-facing sections without exposing raw internal artifact names as headings.

You must not provide buy/sell/hold recommendations.
You must not produce price targets.
You must not claim certainty.
You must not perform option analysis.
You must not replace SAM/OAM/OD.
You must help classify the user's intent and suggest a research path.

Return structured JSON only."""

RCE_CONTEXT_AWARE_ENRICHMENT_PROMPT_VERSION = "rce-context-aware-universe-enrichment-v0.1"
RCE_CONTEXT_AWARE_ENRICHMENT_SYSTEM_PROMPT = RCE_SYSTEM_PROMPT + """

Context-aware Research Universe enrichment behavior:
- The supplied seed universe is authoritative known context, not a list to regenerate.
- Find material omissions that add coverage to the already-known universe.
- Research through the supplied Discovery Lenses; they are directions, not quotas.
- Suppress every known seed member from candidate output.
- Prefer publicly traded candidates supported by public company disclosures, filings, or reputable public industry sources.
- Do not assume access to paywalled research.
- Avoid weak thematic adjacency and explain the material coverage added.
- Each candidate must return discovery_lenses, related_seed_matching_keys, reason_discovered, and evidence_references.
- Evidence references must identify actual public sources; do not fabricate evidence.
- Candidates are pending suggestions only and must never be described as approved membership.
Return structured JSON only."""

REQUIRED_STRUCTURED_FIELDS = (
    "original_question",
    "interpretation",
    "research_plan",
    "proposed_research_universe",
    "universe_review",
    "user_presentation",
    "estimated_user_sophistication",
    "primary_domain",
    "primary_intent",
    "research_objective",
    "secondary_intents",
    "research_lenses",
    "mentioned_companies",
    "themes",
    "industries",
    "time_horizon",
    "asset_focus",
    "assumptions",
    "confidence",
    "clarifying_questions_needed",
    "clarifying_questions",
    "conversation_complete",
    "terminal_artifact",
    "suggested_research_mission_title",
    "suggested_research_mission_summary",
    "suggested_research_universe_name",
    "research_map",
    "included_areas",
    "excluded_areas",
    "candidate_security_categories",
    "candidate_securities",
    "coverage_assessment",
    "ways_to_refine",
    "warnings",
    "limitations",
)

DEVELOPER_QA_EXAMPLES = (
    {
        "question": "I want to research networking and interconnect companies benefiting from AI.",
        "verify": [
            "Power companies are largely excluded.",
            "Optical, photonics, connectors, switching, fiber, transceivers, and networking semiconductors dominate.",
            "General compute, cooling, construction, and data center REITs are excluded unless directly relevant.",
        ],
    },
    {
        "question": "I'm interested in AI companies solving cancer.",
        "verify": [
            "Universe spans computational biology, oncology AI, diagnostics, genomics, and major pharma AI partnerships.",
            "Do not return only generic AI infrastructure companies.",
        ],
    },
    {
        "question": "Retail companies gaining share through AI.",
        "verify": [
            "Universe reflects retail and consumer AI adoption.",
            "Generic AI chip, cloud, or model companies should not dominate the universe.",
        ],
    },
)

BENCHMARK_QA_FIXTURES = (
    {
        "id": "ai-networking-interconnects",
        "question": "I want to research AI networking and interconnect companies.",
        "expected_research_lens": ["Theme / Narrative", "Competitive Position", "Infrastructure"],
        "included_areas": ["AI networking chips", "Ethernet switching", "Optical interconnects", "Data center switching"],
        "excluded_areas": ["General enterprise software", "Consumer AI apps", "Unrelated telecom carriers"],
        "strong_candidates": ["AVGO", "MRVL", "ANET", "NVDA", "COHR", "LITE", "CSCO"],
        "weak_or_off_target_candidates": ["Consumer app companies", "Generic SaaS companies", "Telecom carriers without AI data center exposure"],
    },
    {
        "id": "ai-cancer-drug-discovery",
        "question": "I am interested in AI companies solving cancer.",
        "expected_research_lens": ["Theme / Narrative", "Healthcare", "Event-Driven"],
        "included_areas": ["AI drug discovery", "Oncology biotech", "Precision medicine", "Computational biology", "Diagnostics"],
        "excluded_areas": ["Generic AI infrastructure", "Hospitals", "Insurers"],
        "strong_candidates": ["RXRX", "SDGR", "EXAI", "TEM", "GH", "ILMN"],
        "weak_or_off_target_candidates": ["AI chip companies without cancer exposure", "General hospital operators", "Biotech names included only because they are popular"],
    },
    {
        "id": "data-center-power-buildout",
        "question": "Research energy companies with promising data center power buildout.",
        "expected_research_lens": ["Theme / Narrative", "Macro Exposure", "Infrastructure"],
        "included_areas": ["Utilities", "Independent power producers", "Grid equipment", "Electrical equipment", "Backup power"],
        "excluded_areas": ["Cloud software", "Oil and gas without power infrastructure", "AI chips unless full infrastructure chain is requested"],
        "strong_candidates": ["GEV", "ETN", "VRT", "PWR", "CEG", "VST", "NEE"],
        "weak_or_off_target_candidates": ["Cloud software companies", "Consumer energy retailers", "Unrelated utilities with no capacity-buildout relevance"],
    },
    {
        "id": "cybersecurity-market",
        "question": "I would like to understand the cybersecurity market.",
        "expected_research_lens": ["Competitive Position", "Fundamental", "Theme / Narrative", "Risk"],
        "included_areas": ["Endpoint security", "Cloud security", "Identity", "Network security", "Zero trust", "Vulnerability management"],
        "excluded_areas": ["General IT services", "Hardware resellers", "Broad software where security is immaterial"],
        "strong_candidates": ["PANW", "CRWD", "ZS", "NET", "FTNT", "OKTA", "CYBR", "TENB", "RPD", "S"],
        "weak_or_off_target_candidates": ["Generic cloud providers without a security thesis", "Low-relevance IT consultants", "Unrelated software companies"],
    },
    {
        "id": "micron-earnings-call-options",
        "question": "Micron earnings are next Tuesday. What bullish calls should I consider?",
        "expected_research_lens": ["Options", "Event-Driven", "Risk"],
        "included_areas": ["MU underlying", "Earnings event", "Bullish calls", "Expiration window", "Liquidity", "Spread", "Delta"],
        "excluded_areas": ["Broad semiconductor universe", "Put strategies", "Common-stock recommendations"],
        "strong_candidates": ["MU"],
        "weak_or_off_target_candidates": ["NVDA as a substitute", "AMD as a substitute", "Price targets", "Options without liquidity context"],
    },
    {
        "id": "fashion-brands-taking-market-share",
        "question": "What fashion brands are best positioned to take market share?",
        "expected_research_lens": ["Competitive Position", "Fundamental", "Valuation", "Consumer"],
        "included_areas": ["Athletic apparel", "Footwear", "Luxury", "Specialty apparel", "Off-price retail"],
        "excluded_areas": ["Grocery retail", "Consumer staples", "E-commerce platforms without fashion-brand thesis"],
        "strong_candidates": ["NKE", "LULU", "DECK", "ONON", "RL", "TPR", "CPRI", "ANF", "URBN", "BURL"],
        "weak_or_off_target_candidates": ["Grocery retailers", "Broad marketplaces without fashion focus", "Unrelated consumer products"],
    },
)


class OpenAIResearchConversationProvider:
    provider_name = OPENAI_PROVIDER_NAME

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        client: Any | None = None,
        max_output_tokens: int | None = None,
    ):
        self.api_key = api_key
        self.model_name = model_name or DEFAULT_RCE_OPENAI_MODEL
        self.client = client
        self.max_output_tokens = max_output_tokens

    def interpret(
        self, request: ResearchConversationRequest
    ) -> ResearchConversationResponse:
        if not self.api_key and self.client is None:
            return self._missing_api_key_response(request)

        response_timestamp = None
        try:
            client = self.client or self._build_client()
            response_arguments = {
                "model": self.model_name,
                "input": [
                    {"role": "system", "content": (
                        RCE_CONTEXT_AWARE_ENRICHMENT_SYSTEM_PROMPT
                        if request.prompt_version == RCE_CONTEXT_AWARE_ENRICHMENT_PROMPT_VERSION
                        else RCE_SYSTEM_PROMPT
                    )},
                    {"role": "user", "content": self._user_prompt(request)},
                ],
                "text": {"format": (
                    OPENAI_RCE_ENRICHMENT_RESPONSE_FORMAT
                    if request.prompt_version == RCE_CONTEXT_AWARE_ENRICHMENT_PROMPT_VERSION
                    else OPENAI_RCE_RESPONSE_FORMAT
                )},
            }
            if self.max_output_tokens is not None:
                response_arguments["max_output_tokens"] = self.max_output_tokens
            raw_response = client.responses.create(
                **response_arguments,
            )
            response_timestamp = utc_now()
            if raw_response is None:
                raise RuntimeError("OpenAI provider returned no response.")
            response_status = (
                raw_response.get("status")
                if isinstance(raw_response, dict)
                else getattr(raw_response, "status", None)
            )
            if response_status is not None and response_status != "completed":
                raise RuntimeError(
                    f"OpenAI provider response did not complete: {response_status}."
                )
            response_text = self._response_text(raw_response)
            structured_response, warnings, errors = parse_structured_response(
                response_text,
                request.original_question,
                enrichment=(
                    request.prompt_version
                    == RCE_CONTEXT_AWARE_ENRICHMENT_PROMPT_VERSION
                ),
            )
            if not errors:
                structured_response["provider_verification_marker"] = (
                    LIVE_OPENAI_PROVIDER_VERIFICATION_MARKER
                )
            response = ResearchConversationResponse(
                metadata=ProviderMetadata(
                    provider_name=self.provider_name,
                    model_name=self.model_name,
                    prompt_version=request.prompt_version,
                    request_timestamp=request.request_timestamp,
                    response_timestamp=response_timestamp,
                    openai_api_key_present=bool(self.api_key),
                    raw_candidate_count=rce_candidate_count(structured_response),
                    parser_mode=RCE_PARSER_MODE,
                    schema_version=RCE_SCHEMA_VERSION,
                ),
                structured_response=structured_response,
                confidence=structured_response.get("confidence"),
                raw_response=raw_response,
                errors=errors,
                warnings=warnings,
            )
            return with_rce_diagnostics(response)
        except Exception as error:
            response = ResearchConversationResponse(
                metadata=ProviderMetadata(
                    provider_name=self.provider_name,
                    model_name=self.model_name,
                    prompt_version=request.prompt_version,
                    request_timestamp=request.request_timestamp,
                    response_timestamp=response_timestamp or utc_now(),
                    openai_api_key_present=bool(self.api_key),
                    provider_error_type=type(error).__name__,
                    provider_error_message=str(error),
                    provider_http_status=getattr(error, "status_code", None),
                ),
                structured_response=empty_research_conversation_structure(
                    request.original_question
                ),
                confidence=None,
                raw_response=None,
                errors=[str(error)],
                warnings=[],
            )
            return with_rce_diagnostics(response)

    def _build_client(self) -> Any:
        from openai import OpenAI

        return OpenAI(api_key=self.api_key)

    def _missing_api_key_response(
        self, request: ResearchConversationRequest
    ) -> ResearchConversationResponse:
        message = "OPENAI_API_KEY is not configured; using setup-safe RCE response."
        structured_response = empty_research_conversation_structure(
            request.original_question
        )
        structured_response.update(
            {
                "primary_intent": "OpenAI provider is configured but unavailable.",
                "clarifying_questions_needed": False,
                "warnings": [message],
                "limitations": [
                    "Set OPENAI_API_KEY to enable live RCE interpretation.",
                    "No research universe was generated or persisted.",
                ],
            }
        )
        response = ResearchConversationResponse(
            metadata=ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.model_name,
                prompt_version=request.prompt_version,
                request_timestamp=request.request_timestamp,
                response_timestamp=utc_now(),
                openai_api_key_present=False,
                provider_error_type="MissingOpenAIAPIKey",
                provider_error_message=message,
            ),
            structured_response=structured_response,
            confidence=None,
            raw_response=None,
            errors=[message],
            warnings=[message],
        )
        return with_rce_diagnostics(response)

    def _user_prompt(self, request: ResearchConversationRequest) -> str:
        payload = {
                "prompt_version": request.prompt_version or DEFAULT_RCE_PROMPT_VERSION,
                "original_question": request.original_question,
                "required_fields": REQUIRED_STRUCTURED_FIELDS,
                "interpretation_schema": {
                    "original_question": "string",
                    "estimated_user_sophistication": "string",
                    "primary_domain": "string",
                    "primary_intent": "string",
                    "secondary_intents": ["string"],
                    "research_lenses": ["string"],
                    "mentioned_companies": ["string"],
                    "themes": ["string"],
                    "industries": ["string"],
                    "time_horizon": "string",
                    "asset_focus": "string",
                    "confidence": "number between 0 and 1",
                    "clarifying_questions_needed": "boolean",
                    "clarifying_questions": ["string"],
                },
                "research_plan_schema": {
                    "research_objective": "string",
                    "primary_theme": "string",
                    "research_lens": ["string"],
                    "included_areas": ["string"],
                    "excluded_areas": ["string"],
                    "adjacent_areas": ["string"],
                    "candidate_subdomains": ["string"],
                    "assumptions": ["string"],
                    "known_blind_spots": ["string"],
                },
                "candidate_security_schema": {
                    "ticker": "string or null",
                    "company_name": "string",
                    "subdomain": "string",
                    "inclusion_rationale": "string explaining why it belongs in the research universe",
                    "category": "string",
                    "confidence": "number between 0 and 1",
                },
                "research_objective_schema": {
                    "primary_theme": "string",
                    "research_focus": "string",
                    "implied_investment_question": "string",
                },
                "research_map_schema": [
                    {
                        "area": "string",
                        "subdomains": ["string"],
                    }
                ],
                "proposed_research_universe_schema": {
                    "name": "string",
                    "candidate_security_categories": ["string"],
                    "candidate_securities": "array of candidate_security_schema objects",
                },
                "universe_review_schema": {
                    "coverage_assessment": ["string"],
                    "relevance_assessment": ["string"],
                    "informational_diversity_assessment": ["string"],
                    "missing_areas": ["string"],
                    "weak_candidates": ["string"],
                    "redundant_candidates": ["string"],
                    "recommended_improvements": ["string"],
                    "draft_research_utility_score": {
                        "coverage": "number between 0 and 1 or null",
                        "relevance": "number between 0 and 1 or null",
                        "informational_diversity": "number between 0 and 1 or null",
                        "explainability": "number between 0 and 1 or null",
                        "refinement_readiness": "number between 0 and 1 or null",
                        "overall": "number between 0 and 1 or null",
                        "notes": ["string"],
                    },
                },
                "user_presentation_schema": {
                    "understanding": "string for Here's how I understand your question",
                    "approach": "string for How we'll approach it",
                    "areas_included": ["string"],
                    "areas_excluded": ["string"],
                    "companies_to_start_with": "array of candidate_security_schema objects",
                    "universe_review": ["string"],
                    "assumptions": ["string"],
                    "ways_to_refine": ["string"],
                },
                "response_policy": [
                    "Return concise interpretation in primary_intent.",
                    "Return the same interpretation in the nested interpretation object.",
                    "Return research_plan before constructing candidate securities.",
                    "Build a Research Map before selecting candidate securities.",
                    "Return the Research Map as the primary explanation of how the universe was constructed.",
                    "Return included_areas and excluded_areas after reasoning about scope.",
                    "Return assumed scope in assumptions.",
                    "Return relevant included areas in candidate_security_categories.",
                    "Return a suggested research mission and universe name.",
                    "When the question is reasonably interpretable, return candidate_securities immediately.",
                    "Use 25 to 50 candidate securities when a theme, industry, or market question supports it.",
                    "Each candidate security must include ticker, company_name, subdomain or category, inclusion_rationale, and confidence.",
                    "Return coverage_assessment that explicitly names map areas covered or intentionally excluded.",
                    "Return ways_to_refine as concrete ways the user could narrow, broaden, or redirect the universe.",
                    "Return universe_review before user_presentation.",
                    "Return user_presentation as clean user-facing sections and do not use raw internal artifact names as headings.",
                    "Draft Research Utility Score evaluates proposed-universe quality only, not security quality.",
                    f"If confidence is at least {DEFAULT_RCE_CONFIDENCE_THRESHOLD:.2f}, set clarifying_questions_needed to false and clarifying_questions to an empty list.",
                    "Ask at most one clarifying question only when confidence is below threshold and the original question is too ambiguous to classify.",
                    "When a Proposed Research Universe is returned, set conversation_complete to true and terminal_artifact to Proposed Research Universe.",
                    "Include confidence and limitations.",
                ],
                "strict_boundaries": [
                    "Do not recommend investments.",
                    "Do not produce price targets.",
                    "Do not perform option analysis.",
                    "Do not replace SAM/OAM/OD.",
                    "Do not create or imply a final research universe.",
                ],
                "developer_qa_examples": DEVELOPER_QA_EXAMPLES,
            }
        if request.prompt_version == RCE_CONTEXT_AWARE_ENRICHMENT_PROMPT_VERSION:
            payload = {
                "prompt_version": request.prompt_version,
                "original_question": request.original_question,
                "candidate_security_schema": {
                    "ticker": "string or null",
                    "company_name": "string",
                    "discovery_lenses": ["Discovery Lens identifier"],
                    "related_seed_matching_keys": [
                        "matching key from supplied seed_members"
                    ],
                    "reason_discovered": "concise material omission rationale",
                    "evidence_references": ["public source title or URL"],
                },
                "required_fields": ["candidate_securities"],
            }
            payload["enrichment_request"] = request.context.get("enrichment_request", {})
            payload["response_policy"] = [
                "Treat seed_members as known and exclude them from candidate_securities.",
                "Find material omissions using the active Discovery Lenses without per-lens quotas.",
                "Return only evidence-supported public-company suggestions.",
                "Preserve multiple supported discovery_lenses on a candidate.",
                "Return related_seed_matching_keys only from the supplied seed members.",
                "Every candidate is pending; never approve or promote a candidate.",
            ]
        if request.request_origin == "general_user":
            if request.anchor_companies:
                payload["anchor_companies"] = list(request.anchor_companies)
                payload["anchor_company_guidance"] = [
                    "These are user-supplied starting points; consider them, but do not blindly include them.",
                    "Discover relevant public companies beyond the supplied anchors.",
                    "Do not let the candidate universe collapse into a list made mainly of anchors.",
                    "When possible, return anchor_company_review records with supplied_value, normalized_company_name, normalized_ticker, disposition (included, not_included, or unresolved), and an explanation only when supported.",
                ]
                payload["anchor_company_review_schema"] = [{
                    "supplied_value": "string",
                    "normalized_company_name": "string or null",
                    "normalized_ticker": "string or null",
                    "disposition": "included, not_included, or unresolved",
                    "explanation": "string or null; do not fabricate",
                }]
        else:
            payload["benchmark_qa_fixtures"] = BENCHMARK_QA_FIXTURES
        return json.dumps(payload)

    @staticmethod
    def _response_text(raw_response: Any) -> str:
        output_text = getattr(raw_response, "output_text", None)
        if output_text:
            return output_text
        if isinstance(raw_response, dict):
            return raw_response.get("output_text") or json.dumps(raw_response)
        return str(raw_response)


def parse_structured_response(
    response_text: str,
    original_question: str,
    *,
    enrichment: bool = False,
) -> tuple[dict[str, Any], list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as error:
        structured_response = empty_research_conversation_structure(original_question)
        errors.append(f"OpenAI response was not valid structured JSON: {error.msg}")
        structured_response["warnings"] = errors.copy()
        structured_response["limitations"] = [
            "The provider response could not be parsed into RCE fields."
        ]
        return structured_response, warnings, errors

    if not isinstance(parsed, dict):
        structured_response = empty_research_conversation_structure(original_question)
        errors.append("OpenAI response JSON root must be an object.")
        structured_response["warnings"] = errors.copy()
        return structured_response, warnings, errors

    if enrichment:
        candidates = parsed.get("candidate_securities")
        if not isinstance(candidates, list):
            return (
                {"candidate_securities": []},
                ["candidate_securities was not a list."],
                [],
            )
        return {
            "candidate_securities": [
                _normalize_enrichment_candidate(candidate)
                for candidate in candidates
                if isinstance(candidate, dict)
            ]
        }, warnings, errors

    structured_response = empty_research_conversation_structure(original_question)
    structured_response.update(parsed)
    structured_response["original_question"] = (
        structured_response.get("original_question") or original_question
    )

    for field_name in REQUIRED_STRUCTURED_FIELDS:
        if field_name not in parsed:
            warnings.append(f"Missing structured field: {field_name}")

    structured_response["interpretation"] = _normalize_interpretation(
        structured_response.get("interpretation"),
        structured_response,
        original_question,
    )
    structured_response["research_plan"] = _normalize_research_plan(
        structured_response.get("research_plan"),
        structured_response,
    )
    structured_response["research_map"] = _normalize_research_map(
        structured_response.get("research_map")
    )
    structured_response["proposed_research_universe"] = _normalize_proposed_universe(
        structured_response.get("proposed_research_universe"),
        structured_response,
    )
    candidate_securities = (
        structured_response.get("candidate_securities")
        or structured_response["proposed_research_universe"].get("candidate_securities")
    )
    if not isinstance(candidate_securities, list):
        structured_response["candidate_securities"] = []
        warnings.append("candidate_securities was not a list.")
    else:
        structured_response["candidate_securities"] = [
            _normalize_candidate_security(candidate)
            for candidate in candidate_securities
            if isinstance(candidate, dict)
        ]
    structured_response["proposed_research_universe"]["candidate_securities"] = (
        structured_response["candidate_securities"]
    )

    structured_response["warnings"] = _as_list(
        structured_response.get("warnings")
    ) + warnings
    structured_response["limitations"] = _as_list(
        structured_response.get("limitations")
    )
    structured_response["assumptions"] = _as_list(
        structured_response.get("assumptions")
    )
    structured_response["included_areas"] = _as_list(
        structured_response.get("included_areas")
        or structured_response["research_plan"].get("included_areas")
    )
    structured_response["excluded_areas"] = _as_list(
        structured_response.get("excluded_areas")
        or structured_response["research_plan"].get("excluded_areas")
    )
    structured_response["adjacent_areas"] = _as_list(
        structured_response.get("adjacent_areas")
        or structured_response["research_plan"].get("adjacent_areas")
    )
    structured_response["coverage_assessment"] = _as_list(
        structured_response.get("coverage_assessment")
    )
    structured_response["universe_review"] = _normalize_universe_review(
        structured_response.get("universe_review"),
        structured_response,
    )
    if not structured_response["coverage_assessment"]:
        structured_response["coverage_assessment"] = structured_response[
            "universe_review"
        ].get("coverage_assessment", [])
    structured_response["ways_to_refine"] = _as_list(
        structured_response.get("ways_to_refine")
    )
    structured_response["clarifying_questions"] = _as_list(
        structured_response.get("clarifying_questions")
    )[:1]
    structured_response["confidence"] = _normalize_confidence(
        structured_response.get("confidence")
        or structured_response["interpretation"].get("confidence")
    )
    structured_response["user_presentation"] = _normalize_user_presentation(
        structured_response.get("user_presentation"),
        structured_response,
    )
    policy_response = apply_research_launch_policy(
        ResearchConversationResponse(
            metadata=ProviderMetadata(
                provider_name=OPENAI_PROVIDER_NAME,
                model_name="parser",
                prompt_version=DEFAULT_RCE_PROMPT_VERSION,
                request_timestamp=utc_now(),
            ),
            structured_response=structured_response,
            confidence=structured_response["confidence"],
        )
    )
    return policy_response.structured_response, warnings, errors


def _normalize_candidate_security(candidate: dict[str, Any]) -> dict[str, Any]:
    subdomain = candidate.get("subdomain") or candidate.get("category") or ""
    return {
        "ticker": candidate.get("ticker"),
        "company_name": candidate.get("company_name") or "",
        "inclusion_rationale": candidate.get("inclusion_rationale") or "",
        "subdomain": subdomain,
        "category": candidate.get("category") or subdomain,
        "confidence": _normalize_confidence(candidate.get("confidence")),
    }


def _normalize_enrichment_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Preserve the canonical enrichment fields for strict downstream validation."""
    return {
        "ticker": candidate.get("ticker"),
        "company_name": candidate.get("company_name") or "",
        "discovery_lenses": _as_list(candidate.get("discovery_lenses")),
        "related_seed_matching_keys": _as_list(
            candidate.get("related_seed_matching_keys")
        ),
        "reason_discovered": candidate.get("reason_discovered") or "",
        "evidence_references": _as_list(candidate.get("evidence_references")),
    }


def _normalize_interpretation(
    value: Any,
    structured_response: dict[str, Any],
    original_question: str,
) -> dict[str, Any]:
    interpretation = value if isinstance(value, dict) else {}
    return {
        "original_question": interpretation.get("original_question")
        or structured_response.get("original_question")
        or original_question,
        "estimated_user_sophistication": interpretation.get("estimated_user_sophistication")
        or structured_response.get("estimated_user_sophistication")
        or "Unknown",
        "primary_domain": interpretation.get("primary_domain")
        or structured_response.get("primary_domain")
        or "Unknown",
        "primary_intent": interpretation.get("primary_intent")
        or structured_response.get("primary_intent")
        or "",
        "secondary_intents": _as_list(
            interpretation.get("secondary_intents")
            or structured_response.get("secondary_intents")
        ),
        "research_lenses": _as_list(
            interpretation.get("research_lenses")
            or structured_response.get("research_lenses")
        ),
        "mentioned_companies": _as_list(
            interpretation.get("mentioned_companies")
            or structured_response.get("mentioned_companies")
        ),
        "themes": _as_list(interpretation.get("themes") or structured_response.get("themes")),
        "industries": _as_list(
            interpretation.get("industries") or structured_response.get("industries")
        ),
        "time_horizon": interpretation.get("time_horizon")
        or structured_response.get("time_horizon")
        or "Unspecified",
        "asset_focus": interpretation.get("asset_focus")
        or structured_response.get("asset_focus")
        or "Unspecified",
        "confidence": _normalize_confidence(
            interpretation.get("confidence") or structured_response.get("confidence")
        ),
        "clarifying_questions_needed": bool(
            interpretation.get(
                "clarifying_questions_needed",
                structured_response.get("clarifying_questions_needed", False),
            )
        ),
        "clarifying_questions": _as_list(
            interpretation.get("clarifying_questions")
            or structured_response.get("clarifying_questions")
        )[:1],
    }


def _normalize_research_plan(
    value: Any,
    structured_response: dict[str, Any],
) -> dict[str, Any]:
    plan = value if isinstance(value, dict) else {}
    research_objective = plan.get("research_objective")
    if isinstance(research_objective, dict):
        research_objective = (
            research_objective.get("research_focus")
            or research_objective.get("implied_investment_question")
            or research_objective.get("primary_theme")
            or ""
        )
    legacy_objective = structured_response.get("research_objective")
    if not research_objective and isinstance(legacy_objective, dict):
        research_objective = (
            legacy_objective.get("research_focus")
            or legacy_objective.get("implied_investment_question")
            or ""
        )
    return {
        "research_objective": research_objective or structured_response.get("primary_intent") or "",
        "primary_theme": plan.get("primary_theme")
        or _first(structured_response.get("themes"))
        or "",
        "research_lens": _as_list(
            plan.get("research_lens") or structured_response.get("research_lenses")
        ),
        "included_areas": _as_list(
            plan.get("included_areas") or structured_response.get("included_areas")
        ),
        "excluded_areas": _as_list(
            plan.get("excluded_areas") or structured_response.get("excluded_areas")
        ),
        "adjacent_areas": _as_list(
            plan.get("adjacent_areas") or structured_response.get("adjacent_areas")
        ),
        "candidate_subdomains": _as_list(
            plan.get("candidate_subdomains")
            or structured_response.get("candidate_security_categories")
        ),
        "assumptions": _as_list(
            plan.get("assumptions") or structured_response.get("assumptions")
        ),
        "known_blind_spots": _as_list(plan.get("known_blind_spots")),
    }


def _normalize_proposed_universe(
    value: Any,
    structured_response: dict[str, Any],
) -> dict[str, Any]:
    universe = value if isinstance(value, dict) else {}
    raw_candidates = universe.get("candidate_securities") or structured_response.get(
        "candidate_securities"
    )
    candidates = []
    if isinstance(raw_candidates, list):
        candidates = [
            _normalize_candidate_security(candidate)
            for candidate in raw_candidates
            if isinstance(candidate, dict)
        ]
    return {
        "name": universe.get("name")
        or structured_response.get("suggested_research_universe_name")
        or "",
        "candidate_security_categories": _as_list(
            universe.get("candidate_security_categories")
            or structured_response.get("candidate_security_categories")
        ),
        "candidate_securities": candidates,
    }


def _normalize_universe_review(
    value: Any,
    structured_response: dict[str, Any],
) -> dict[str, Any]:
    review = value if isinstance(value, dict) else {}
    return {
        "coverage_assessment": _as_list(
            review.get("coverage_assessment")
            or structured_response.get("coverage_assessment")
        ),
        "relevance_assessment": _as_list(review.get("relevance_assessment")),
        "informational_diversity_assessment": _as_list(
            review.get("informational_diversity_assessment")
        ),
        "missing_areas": _as_list(review.get("missing_areas")),
        "weak_candidates": _as_list(review.get("weak_candidates")),
        "redundant_candidates": _as_list(review.get("redundant_candidates")),
        "recommended_improvements": _as_list(review.get("recommended_improvements")),
        "draft_research_utility_score": _normalize_research_utility_score(
            review.get("draft_research_utility_score")
        ),
    }


def _normalize_research_utility_score(value: Any) -> dict[str, Any]:
    score = value if isinstance(value, dict) else {}
    return {
        "coverage": _normalize_confidence(score.get("coverage")),
        "relevance": _normalize_confidence(score.get("relevance")),
        "informational_diversity": _normalize_confidence(
            score.get("informational_diversity")
        ),
        "explainability": _normalize_confidence(score.get("explainability")),
        "refinement_readiness": _normalize_confidence(
            score.get("refinement_readiness")
        ),
        "overall": _normalize_confidence(score.get("overall")),
        "notes": _as_list(score.get("notes")),
    }


def _normalize_user_presentation(
    value: Any,
    structured_response: dict[str, Any],
) -> dict[str, Any]:
    presentation = value if isinstance(value, dict) else {}
    return {
        "understanding": presentation.get("understanding")
        or structured_response.get("primary_intent")
        or "",
        "approach": presentation.get("approach")
        or structured_response.get("suggested_research_mission_summary")
        or "",
        "areas_included": _as_list(
            presentation.get("areas_included")
            or structured_response.get("included_areas")
        ),
        "areas_excluded": _as_list(
            presentation.get("areas_excluded")
            or structured_response.get("excluded_areas")
        ),
        "companies_to_start_with": presentation.get("companies_to_start_with")
        or structured_response.get("candidate_securities")
        or [],
        "universe_review": _as_list(
            presentation.get("universe_review")
            or structured_response.get("coverage_assessment")
        ),
        "assumptions": _as_list(
            presentation.get("assumptions") or structured_response.get("assumptions")
        ),
        "ways_to_refine": _as_list(
            presentation.get("ways_to_refine")
            or structured_response.get("ways_to_refine")
        ),
    }


def _normalize_research_map(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized_map = []
    for item in value:
        if isinstance(item, str):
            normalized_map.append({"area": item, "subdomains": []})
        elif isinstance(item, dict):
            normalized_map.append(
                {
                    "area": item.get("area") or item.get("category") or "",
                    "subdomains": _as_list(item.get("subdomains")),
                }
            )
    return normalized_map


def _normalize_confidence(value: Any) -> float | None:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, numeric_value))


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _first(value: Any) -> Any:
    values = _as_list(value)
    return values[0] if values else None
