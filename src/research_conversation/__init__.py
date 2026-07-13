from __future__ import annotations

import os
import logging
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Protocol


DEFAULT_RCE_PROMPT_VERSION = "rce-multi-stage-artifact-pipeline-v0.1"
DEFAULT_RCE_PROVIDER = "mock"
RCE_PROVIDER_ENV = "RCE_PROVIDER"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
RCE_OPENAI_MODEL_ENV = "RCE_OPENAI_MODEL"
RCE_CONFIDENCE_THRESHOLD_ENV = "RCE_CONFIDENCE_THRESHOLD"
DEFAULT_RCE_CONFIDENCE_THRESHOLD = 0.70
RCE_PARSER_MODE = "structured-json-normalizer"
RCE_SCHEMA_VERSION = "rce-response-schema-v0.1"
OPENAI_FALLBACK_WARNING = "OpenAI provider failed; using mock provider."
DEFAULT_RESEARCH_LAUNCH_ASSUMPTIONS = [
    "U.S.-listed companies",
    "General investment research",
    "Medium-term perspective",
]
RCE_ENTITY_VALIDATION_VERSION = "rce-entity-validation-v0.1"
TICKER_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ProviderMetadata:
    provider_name: str
    model_name: str
    prompt_version: str
    request_timestamp: datetime
    response_timestamp: datetime | None = None
    selected_provider_name: str | None = None
    fallback_used: bool = False
    fallback_provider_name: str | None = None
    mock_provider_used: bool = False
    openai_api_key_present: bool = False
    latency_seconds: float | None = None
    raw_candidate_count: int = 0
    displayed_candidate_count: int = 0
    parser_mode: str = RCE_PARSER_MODE
    schema_version: str = RCE_SCHEMA_VERSION
    provider_error_type: str | None = None
    provider_error_message: str | None = None
    provider_http_status: int | None = None

    def diagnostics(self) -> dict[str, Any]:
        return {
            "active_provider_name": self.provider_name,
            "selected_provider_name": self.selected_provider_name or self.provider_name,
            "active_model_name": self.model_name,
            "prompt_version": self.prompt_version,
            "openai_api_key_present": self.openai_api_key_present,
            "fallback_used": self.fallback_used,
            "fallback_provider_name": self.fallback_provider_name,
            "mock_provider_used": self.mock_provider_used,
            "request_timestamp": self.request_timestamp.isoformat(),
            "response_timestamp": (
                self.response_timestamp.isoformat()
                if self.response_timestamp is not None
                else None
            ),
            "latency_seconds": self.latency_seconds,
            "raw_candidate_count": self.raw_candidate_count,
            "displayed_candidate_count": self.displayed_candidate_count,
            "parser_mode": self.parser_mode,
            "schema_version": self.schema_version,
            "provider_error_type": self.provider_error_type,
            "provider_error_message": self.provider_error_message,
            "provider_http_status": self.provider_http_status,
        }


@dataclass(frozen=True)
class ResearchConversationRequest:
    original_question: str
    prompt_version: str = DEFAULT_RCE_PROMPT_VERSION
    request_timestamp: datetime = field(default_factory=utc_now)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResearchConversationResponse:
    metadata: ProviderMetadata
    structured_response: dict[str, Any]
    confidence: float | None = None
    raw_response: Any | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


@dataclass(frozen=True)
class ResearchPlan:
    research_objective: str = ""
    primary_theme: str = ""
    research_lens: list[str] = field(default_factory=list)
    included_areas: list[str] = field(default_factory=list)
    excluded_areas: list[str] = field(default_factory=list)
    adjacent_areas: list[str] = field(default_factory=list)
    candidate_subdomains: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    known_blind_spots: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "research_objective": self.research_objective,
            "primary_theme": self.primary_theme,
            "research_lens": self.research_lens,
            "included_areas": self.included_areas,
            "excluded_areas": self.excluded_areas,
            "adjacent_areas": self.adjacent_areas,
            "candidate_subdomains": self.candidate_subdomains,
            "assumptions": self.assumptions,
            "known_blind_spots": self.known_blind_spots,
        }


@dataclass(frozen=True)
class ResearchMap:
    areas: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"areas": self.areas}


@dataclass(frozen=True)
class ResearchUtilityScoreDraft:
    coverage: float | None = None
    relevance: float | None = None
    informational_diversity: float | None = None
    explainability: float | None = None
    refinement_readiness: float | None = None
    overall: float | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage": self.coverage,
            "relevance": self.relevance,
            "informational_diversity": self.informational_diversity,
            "explainability": self.explainability,
            "refinement_readiness": self.refinement_readiness,
            "overall": self.overall,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class UniverseReview:
    coverage_assessment: list[str] = field(default_factory=list)
    relevance_assessment: list[str] = field(default_factory=list)
    informational_diversity_assessment: list[str] = field(default_factory=list)
    missing_areas: list[str] = field(default_factory=list)
    weak_candidates: list[str] = field(default_factory=list)
    redundant_candidates: list[str] = field(default_factory=list)
    recommended_improvements: list[str] = field(default_factory=list)
    draft_research_utility_score: ResearchUtilityScoreDraft = field(
        default_factory=ResearchUtilityScoreDraft
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_assessment": self.coverage_assessment,
            "relevance_assessment": self.relevance_assessment,
            "informational_diversity_assessment": self.informational_diversity_assessment,
            "missing_areas": self.missing_areas,
            "weak_candidates": self.weak_candidates,
            "redundant_candidates": self.redundant_candidates,
            "recommended_improvements": self.recommended_improvements,
            "draft_research_utility_score": self.draft_research_utility_score.to_dict(),
        }


class ResearchConversationProvider(Protocol):
    provider_name: str
    model_name: str

    def interpret(
        self, request: ResearchConversationRequest
    ) -> ResearchConversationResponse:
        """Translate a research question into a structured RCE interpretation."""


class ResearchConversationService:
    def __init__(
        self,
        provider: ResearchConversationProvider,
        confidence_threshold: float = DEFAULT_RCE_CONFIDENCE_THRESHOLD,
    ):
        self.provider = provider
        self.confidence_threshold = confidence_threshold

    def interpret(
        self, original_question: str, context: dict[str, Any] | None = None
    ) -> ResearchConversationResponse:
        request = ResearchConversationRequest(
            original_question=original_question.strip(),
            context=context or {},
        )
        selected_provider_name = getattr(self.provider, "provider_name", "unknown")
        selected_model_name = getattr(self.provider, "model_name", "unknown")
        try:
            response = self.provider.interpret(request)
            response = apply_research_launch_policy(
                response,
                confidence_threshold=self.confidence_threshold,
                clarification_turns=int(request.context.get("clarification_turns", 0)),
            )
            if selected_provider_name == "openai" and response.has_errors:
                response = self._fallback_to_mock(request, response)
            response = with_rce_diagnostics(
                response,
                selected_provider_name=selected_provider_name,
            )
            log_rce_request(response)
            return response
        except Exception as error:
            response_timestamp = utc_now()
            response = ResearchConversationResponse(
                metadata=ProviderMetadata(
                    provider_name=getattr(self.provider, "provider_name", "unknown"),
                    model_name=getattr(self.provider, "model_name", "unknown"),
                    prompt_version=request.prompt_version,
                    request_timestamp=request.request_timestamp,
                    response_timestamp=response_timestamp,
                    selected_provider_name=selected_provider_name,
                    provider_error_type=type(error).__name__,
                    provider_error_message=str(error),
                    provider_http_status=getattr(error, "status_code", None),
                ),
                structured_response={},
                confidence=None,
                raw_response=None,
                errors=[str(error)],
                warnings=[],
            )
            if selected_provider_name == "openai":
                response = self._fallback_to_mock(request, response)
            response = with_rce_diagnostics(
                response,
                selected_provider_name=selected_provider_name,
            )
            log_rce_request(response)
            return response

    def _fallback_to_mock(
        self,
        request: ResearchConversationRequest,
        failed_response: ResearchConversationResponse,
    ) -> ResearchConversationResponse:
        mock_response = MockResearchConversationProvider().interpret(request)
        mock_response = apply_research_launch_policy(
            mock_response,
            confidence_threshold=self.confidence_threshold,
            clarification_turns=int(request.context.get("clarification_turns", 0)),
        )
        error_message = "; ".join(failed_response.errors) or "OpenAI provider failed."
        return replace(
            mock_response,
            metadata=replace(
                mock_response.metadata,
                selected_provider_name="openai",
                fallback_used=True,
                fallback_provider_name=mock_response.metadata.provider_name,
                provider_error_type=failed_response.metadata.provider_error_type,
                provider_error_message=error_message,
                provider_http_status=failed_response.metadata.provider_http_status,
                openai_api_key_present=bool(os.getenv(OPENAI_API_KEY_ENV)),
            ),
            errors=[],
            warnings=[
                OPENAI_FALLBACK_WARNING,
                *failed_response.errors,
                *mock_response.warnings,
            ],
        )


def empty_research_conversation_structure(original_question: str) -> dict[str, Any]:
    structured_response = {
        "original_question": original_question,
        "interpretation": {
            "original_question": original_question,
            "estimated_user_sophistication": "Unknown",
            "primary_domain": "Unknown",
            "primary_intent": "",
            "secondary_intents": [],
            "research_lenses": [],
            "mentioned_companies": [],
            "themes": [],
            "industries": [],
            "time_horizon": "Unspecified",
            "asset_focus": "Unspecified",
            "confidence": None,
            "clarifying_questions_needed": False,
            "clarifying_questions": [],
        },
        "research_plan": ResearchPlan().to_dict(),
        "proposed_research_universe": {
            "name": "",
            "candidate_security_categories": [],
            "candidate_securities": [],
        },
        "universe_review": UniverseReview().to_dict(),
        "user_presentation": {
            "understanding": "",
            "approach": "",
            "areas_included": [],
            "areas_excluded": [],
            "companies_to_start_with": [],
            "universe_review": [],
            "assumptions": [],
            "ways_to_refine": [],
        },
        "estimated_user_sophistication": "Unknown",
        "primary_domain": "Unknown",
        "primary_intent": "",
        "research_objective": {
            "primary_theme": "",
            "research_focus": "",
            "implied_investment_question": "",
        },
        "secondary_intents": [],
        "research_lenses": [],
        "mentioned_companies": [],
        "themes": [],
        "industries": [],
        "time_horizon": "Unspecified",
        "asset_focus": "Unspecified",
        "assumptions": [],
        "confidence": None,
        "clarifying_questions_needed": False,
        "clarifying_questions": [],
        "conversation_complete": False,
        "terminal_artifact": "",
        "suggested_research_mission_title": "",
        "suggested_research_mission_summary": "",
        "suggested_research_universe_name": "",
        "research_map": [],
        "included_areas": [],
        "excluded_areas": [],
        "candidate_security_categories": [],
        "candidate_securities": [],
        "coverage_assessment": [],
        "ways_to_refine": [],
        "warnings": [],
        "limitations": [],
        "entity_validation": empty_rce_entity_validation(),
    }
    return structured_response


def empty_rce_entity_validation() -> dict[str, Any]:
    return {
        "version": RCE_ENTITY_VALIDATION_VERSION,
        "candidate_count": 0,
        "valid_candidate_count": 0,
        "invalid_candidate_count": 0,
        "duplicate_tickers": [],
        "warnings": [],
    }


class MockResearchConversationProvider:
    provider_name = "mock"
    model_name = "mock-rce-v0.2"

    def interpret(
        self, request: ResearchConversationRequest
    ) -> ResearchConversationResponse:
        response_timestamp = utc_now()
        question = request.original_question.strip()
        warnings = []
        if not question:
            warnings.append("Original question is empty.")

        structured_response = _mock_structured_response(question, warnings)
        response = ResearchConversationResponse(
            metadata=ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.model_name,
                prompt_version=request.prompt_version,
                request_timestamp=request.request_timestamp,
                response_timestamp=response_timestamp,
            ),
            structured_response=structured_response,
            confidence=structured_response.get("confidence"),
            raw_response=None,
            errors=[],
            warnings=warnings,
        )
        return with_rce_diagnostics(response)


def _mock_structured_response(question: str, warnings: list[str]) -> dict[str, Any]:
    structured_response = empty_research_conversation_structure(question)
    if not question:
        structured_response.update(
            {
                "primary_domain": "Unknown",
                "primary_intent": "No research question was provided.",
                "clarifying_questions_needed": True,
                "clarifying_questions": [
                    "What company, theme, industry, or market question should we research?"
                ],
                "warnings": warnings,
                "limitations": [
                    "A candidate research list requires at least a minimal research topic.",
                    "This is a candidate research list, not an investment recommendation.",
                ],
            }
        )
        return structured_response
    normalized_question = question.lower()
    if any(term in normalized_question for term in ("cybersecurity", "cyber security", "security market")):
        return _cybersecurity_mock_response(structured_response, warnings)
    if "robot" in normalized_question or "automation" in normalized_question:
        return _robotics_mock_response(structured_response, warnings)
    return _broad_theme_mock_response(structured_response, warnings)


def _base_mock_update(
    structured_response: dict[str, Any],
    *,
    primary_intent: str,
    themes: list[str],
    industries: list[str],
    mission_title: str,
    mission_summary: str,
    universe_name: str,
    categories: list[str],
    candidates: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    research_plan = ResearchPlan(
        research_objective=mission_summary,
        primary_theme=themes[0] if themes else "",
        research_lens=["Theme / Narrative", "Competitive Position", "Risk"],
        included_areas=categories,
        excluded_areas=[],
        adjacent_areas=[],
        candidate_subdomains=categories,
        assumptions=[
            "U.S.-listed companies",
            "General investment research",
            "Medium-term perspective",
            "Recognizable companies with clear public-market exposure to the theme",
        ],
        known_blind_spots=[
            "Mock provider output does not verify current fundamentals or news.",
            "Private companies and non-listed exposures are not included.",
        ],
    ).to_dict()
    research_map = [{"area": category, "subdomains": []} for category in categories]
    universe_review = UniverseReview(
        coverage_assessment=[f"{category} included" for category in categories],
        relevance_assessment=[
            "Candidates are selected for plausible research-scope relevance."
        ],
        informational_diversity_assessment=[
            "The list spans multiple evidence-bearing subdomains."
        ],
        missing_areas=[],
        weak_candidates=[],
        redundant_candidates=[],
        recommended_improvements=[
            "Review whether the user wants pure-play companies only.",
            "Refine geography, market-cap range, or time horizon before saving.",
        ],
        draft_research_utility_score=ResearchUtilityScoreDraft(
            coverage=0.72,
            relevance=0.74,
            informational_diversity=0.72,
            explainability=0.78,
            refinement_readiness=0.8,
            overall=0.75,
            notes=["Draft score is experimental and not used for ranking securities."],
        ),
    ).to_dict()
    assumptions = research_plan["assumptions"]
    coverage_assessment = universe_review["coverage_assessment"]
    structured_response.update(
        {
            "estimated_user_sophistication": "Growing Investor",
            "primary_domain": "Discover",
            "primary_intent": primary_intent,
            "research_objective": {
                "primary_theme": themes[0] if themes else "",
                "research_focus": primary_intent,
                "implied_investment_question": (
                    "Which public companies form a useful first-pass research "
                    "universe for this theme?"
                ),
            },
            "secondary_intents": ["Evaluate"],
            "research_lenses": ["Theme / Narrative", "Competitive Position", "Risk"],
            "themes": themes,
            "industries": industries,
            "time_horizon": "Unspecified",
            "asset_focus": "Equities",
            "assumptions": assumptions,
            "confidence": 0.72,
            "clarifying_questions_needed": False,
            "clarifying_questions": [],
            "conversation_complete": True,
            "terminal_artifact": "Proposed Research Universe",
            "suggested_research_mission_title": mission_title,
            "suggested_research_mission_summary": mission_summary,
            "suggested_research_universe_name": universe_name,
            "interpretation": {
                "original_question": structured_response.get("original_question", ""),
                "estimated_user_sophistication": "Growing Investor",
                "primary_domain": "Discover",
                "primary_intent": primary_intent,
                "secondary_intents": ["Evaluate"],
                "research_lenses": ["Theme / Narrative", "Competitive Position", "Risk"],
                "mentioned_companies": [],
                "themes": themes,
                "industries": industries,
                "time_horizon": "Unspecified",
                "asset_focus": "Equities",
                "confidence": 0.72,
                "clarifying_questions_needed": False,
                "clarifying_questions": [],
            },
            "research_plan": research_plan,
            "research_map": research_map,
            "included_areas": categories,
            "excluded_areas": [],
            "adjacent_areas": [],
            "candidate_security_categories": categories,
            "candidate_securities": candidates,
            "proposed_research_universe": {
                "name": universe_name,
                "candidate_security_categories": categories,
                "candidate_securities": candidates,
            },
            "universe_review": universe_review,
            "coverage_assessment": coverage_assessment,
            "ways_to_refine": [
                "Narrow or broaden the company list.",
                "Add explicit exclusions or pure-play preferences.",
                "Adjust geography, market-cap range, or time horizon.",
            ],
            "warnings": warnings,
            "limitations": [
                "Mock provider output is deterministic and does not call a live AI model.",
                "Candidate membership is a starting point for research and needs evidence review.",
                "This is a candidate research list, not an investment recommendation.",
            ],
            "user_presentation": {
                "understanding": primary_intent,
                "approach": mission_summary,
                "areas_included": categories,
                "areas_excluded": [],
                "companies_to_start_with": candidates,
                "universe_review": coverage_assessment,
                "assumptions": assumptions,
                "ways_to_refine": [
                    "Narrow or broaden the company list.",
                    "Add explicit exclusions or pure-play preferences.",
                    "Adjust geography, market-cap range, or time horizon.",
                ],
            },
        }
    )
    return structured_response


def _candidate(
    ticker: str,
    company_name: str,
    category: str,
    inclusion_rationale: str,
    confidence: float,
) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "company_name": company_name,
        "category": category,
        "subdomain": category,
        "inclusion_rationale": inclusion_rationale,
        "confidence": confidence,
    }


def _cybersecurity_mock_response(
    structured_response: dict[str, Any], warnings: list[str]
) -> dict[str, Any]:
    candidates = [
        _candidate("PANW", "Palo Alto Networks", "Platform security", "Large cybersecurity platform spanning network, cloud, and security operations use cases.", 0.9),
        _candidate("CRWD", "CrowdStrike", "Endpoint and cloud security", "Endpoint detection leader with expanding cloud, identity, and managed security modules.", 0.9),
        _candidate("FTNT", "Fortinet", "Network security", "Firewall and secure networking vendor with broad enterprise and service-provider exposure.", 0.86),
        _candidate("ZS", "Zscaler", "Zero trust access", "Cloud-delivered zero trust and secure web gateway platform tied to network modernization.", 0.86),
        _candidate("OKTA", "Okta", "Identity security", "Identity and access management vendor central to workforce and customer authentication workflows.", 0.83),
        _candidate("NET", "Cloudflare", "Edge and application security", "Edge network platform with DDoS, web application firewall, and zero trust services.", 0.82),
        _candidate("S", "SentinelOne", "Endpoint security", "AI-oriented endpoint security vendor used as a challenger in endpoint detection and response.", 0.8),
        _candidate("CYBR", "CyberArk", "Privileged access security", "Privileged access management specialist with identity-security relevance.", 0.8),
        _candidate("CHKP", "Check Point Software", "Network security", "Established firewall and threat-prevention vendor with global enterprise exposure.", 0.78),
        _candidate("TENB", "Tenable", "Vulnerability management", "Vulnerability exposure management vendor tied to asset discovery and risk prioritization.", 0.78),
        _candidate("QLYS", "Qualys", "Vulnerability management", "Cloud security and vulnerability management platform with compliance and scanning use cases.", 0.77),
        _candidate("RPD", "Rapid7", "Security analytics", "Exposure management and security operations vendor relevant to vulnerability and incident workflows.", 0.75),
        _candidate("VRNS", "Varonis Systems", "Data security", "Data security platform focused on sensitive data discovery, access, and threat detection.", 0.75),
        _candidate("SAIL", "SailPoint", "Identity governance", "Identity governance vendor relevant to access certification and compliance-oriented security.", 0.74),
        _candidate("GEN", "Gen Digital", "Consumer security", "Consumer cyber safety company spanning antivirus, identity protection, and privacy brands.", 0.72),
        _candidate("BB", "BlackBerry", "Endpoint and embedded security", "Security software and embedded systems exposure, including endpoint management heritage.", 0.68),
        _candidate("IBM", "IBM", "Enterprise security services", "Diversified technology company with security software, consulting, and managed security operations.", 0.67),
        _candidate("MSFT", "Microsoft", "Platform security", "Large security business embedded across identity, endpoint, cloud, and productivity platforms.", 0.86),
        _candidate("GOOGL", "Alphabet", "Cloud and threat intelligence", "Google Cloud security, Mandiant threat intelligence, and Chronicle security operations exposure.", 0.8),
        _candidate("AMZN", "Amazon", "Cloud security infrastructure", "AWS security services and cloud infrastructure make it relevant to enterprise security architecture.", 0.76),
        _candidate("CSCO", "Cisco Systems", "Network and security infrastructure", "Networking incumbent with firewall, secure access, observability, and Splunk security analytics exposure.", 0.78),
        _candidate("ORCL", "Oracle", "Database and cloud security", "Enterprise database and cloud provider with security controls tied to regulated workloads.", 0.65),
        _candidate("DDOG", "Datadog", "Cloud security monitoring", "Cloud observability vendor expanding into cloud security posture and application security monitoring.", 0.72),
        _candidate("NOW", "ServiceNow", "Security operations workflow", "Workflow platform with security operations modules used to manage incidents and response processes.", 0.7),
        _candidate("PLTR", "Palantir Technologies", "Government and data security", "Data platform with government, defense, and secure analytics exposure relevant to cyber-adjacent workflows.", 0.66),
    ]
    return _base_mock_update(
        structured_response,
        primary_intent="Understand the cybersecurity market by building a starter universe across major security categories.",
        themes=["Cybersecurity", "Enterprise security", "Zero trust", "Cloud security"],
        industries=["Software", "Cloud infrastructure", "Network security"],
        mission_title="Cybersecurity Market Research",
        mission_summary="Investigate public companies exposed to cybersecurity demand, grouped by security category and business role before any downstream analysis.",
        universe_name="Cybersecurity Candidate Research List",
        categories=[
            "Platform security",
            "Endpoint and cloud security",
            "Identity security",
            "Network security",
            "Vulnerability management",
            "Cloud and application security",
        ],
        candidates=candidates,
        warnings=warnings,
    )


def _robotics_mock_response(
    structured_response: dict[str, Any], warnings: list[str]
) -> dict[str, Any]:
    candidates = [
        _candidate("ISRG", "Intuitive Surgical", "Medical robotics", "Leader in robotic-assisted surgery systems and related instruments.", 0.88),
        _candidate("TER", "Teradyne", "Industrial automation", "Owns Universal Robots and Mobile Industrial Robots exposure in collaborative automation.", 0.82),
        _candidate("ROK", "Rockwell Automation", "Factory automation", "Industrial automation vendor tied to manufacturing digitization and control systems.", 0.82),
        _candidate("ABBNY", "ABB", "Industrial robotics", "Global automation and robotics vendor with broad industrial end-market exposure.", 0.8),
        _candidate("HON", "Honeywell", "Warehouse automation", "Automation, controls, and warehouse productivity exposure across industrial customers.", 0.73),
        _candidate("EMR", "Emerson Electric", "Industrial automation", "Automation systems and software used in process industries.", 0.7),
        _candidate("CGNX", "Cognex", "Machine vision", "Machine vision systems support inspection and automation workflows.", 0.76),
        _candidate("ZBRA", "Zebra Technologies", "Automation enablement", "Enterprise asset intelligence and warehouse automation tools.", 0.68),
        _candidate("PATH", "UiPath", "Software automation", "Robotic process automation software exposure for enterprise workflows.", 0.72),
        _candidate("NVDA", "NVIDIA", "Robotics compute", "Accelerated compute and edge AI platforms can support robotics development.", 0.74),
    ]
    return _base_mock_update(
        structured_response,
        primary_intent="Build a starter research universe for robotics and automation exposure.",
        themes=["Robotics", "Automation"],
        industries=["Medical devices", "Industrial automation", "Software"],
        mission_title="Robotics and Automation Research",
        mission_summary="Compare companies with direct or enabling exposure to robotics, factory automation, and workflow automation.",
        universe_name="Robotics and Automation Candidates",
        categories=["Medical robotics", "Industrial automation", "Machine vision", "Software automation"],
        candidates=candidates,
        warnings=warnings,
    )


def _broad_theme_mock_response(
    structured_response: dict[str, Any], warnings: list[str]
) -> dict[str, Any]:
    candidates = [
        _candidate("NVDA", "NVIDIA", "AI infrastructure", "Accelerated compute supplier with broad exposure to AI infrastructure buildout.", 0.84),
        _candidate("MSFT", "Microsoft", "Cloud platform", "Cloud and enterprise software platform with AI infrastructure and application exposure.", 0.82),
        _candidate("AMZN", "Amazon", "Cloud platform", "AWS provides cloud infrastructure used by enterprises and AI workloads.", 0.8),
        _candidate("GOOGL", "Alphabet", "Cloud and AI platform", "Cloud, AI model, and digital infrastructure exposure.", 0.78),
        _candidate("META", "Meta Platforms", "AI applications", "Large-scale AI infrastructure spending and consumer AI application exposure.", 0.72),
        _candidate("AVGO", "Broadcom", "Semiconductors", "Networking and custom silicon exposure tied to data center infrastructure.", 0.76),
        _candidate("AMD", "Advanced Micro Devices", "Semiconductors", "CPU and accelerator supplier competing in data center compute.", 0.74),
        _candidate("ORCL", "Oracle", "Cloud platform", "Enterprise cloud and database provider with AI infrastructure ambitions.", 0.68),
        _candidate("ANET", "Arista Networks", "Data center networking", "High-speed networking supplier for cloud and AI data centers.", 0.74),
        _candidate("DELL", "Dell Technologies", "Server infrastructure", "Server and enterprise infrastructure exposure for AI and data center deployments.", 0.7),
    ]
    return _base_mock_update(
        structured_response,
        primary_intent="Translate the question into a reviewable research path and starter candidate list.",
        themes=["Broad technology theme"],
        industries=["Software", "Cloud infrastructure", "Semiconductors"],
        mission_title="Initial Theme Research",
        mission_summary="Use the submitted question to prepare a reviewable research mission and candidate list before downstream analysis.",
        universe_name="Draft Theme Candidate Research List",
        categories=["Cloud platform", "Semiconductors", "Data center infrastructure", "AI applications"],
        candidates=candidates,
        warnings=warnings,
    )


def apply_research_launch_policy(
    response: ResearchConversationResponse,
    *,
    confidence_threshold: float = DEFAULT_RCE_CONFIDENCE_THRESHOLD,
    clarification_turns: int = 0,
) -> ResearchConversationResponse:
    structured_response = dict(response.structured_response or {})
    structured_response = validate_rce_candidate_entities(structured_response)
    confidence = response.confidence
    if confidence is None:
        confidence = structured_response.get("confidence")
    normalized_confidence = _normalize_policy_confidence(confidence)
    candidate_securities = structured_response.get("candidate_securities") or []
    has_candidate_universe = bool(candidate_securities)
    meets_threshold = (
        normalized_confidence is not None
        and normalized_confidence >= confidence_threshold
    )
    must_terminally_propose = has_candidate_universe or meets_threshold or clarification_turns >= 1

    assumptions = _as_policy_list(structured_response.get("assumptions"))
    if must_terminally_propose:
        for assumption in DEFAULT_RESEARCH_LAUNCH_ASSUMPTIONS:
            if assumption not in assumptions:
                assumptions.append(assumption)
        structured_response["assumptions"] = assumptions
        structured_response["clarifying_questions_needed"] = False
        structured_response["clarifying_questions"] = []
        structured_response["conversation_complete"] = True
        structured_response["terminal_artifact"] = "Proposed Research Universe"
    else:
        structured_response["conversation_complete"] = False
        structured_response["terminal_artifact"] = "Optional Clarification"

    return replace(
        response,
        structured_response=structured_response,
        confidence=normalized_confidence,
    )


def validate_rce_candidate_entities(
    structured_response: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(structured_response, dict):
        return {}

    updated_response = dict(structured_response)
    candidates = updated_response.get("candidate_securities")
    if not isinstance(candidates, list):
        proposed_universe = updated_response.get("proposed_research_universe")
        if isinstance(proposed_universe, dict):
            candidates = proposed_universe.get("candidate_securities")
    if not isinstance(candidates, list):
        updated_response["candidate_securities"] = []
        updated_response["entity_validation"] = empty_rce_entity_validation()
        return updated_response

    normalized_candidates: list[dict[str, Any]] = []
    ticker_counts: dict[str, int] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        normalized_candidate = normalize_rce_candidate_entity(candidate)
        ticker = normalized_candidate.get("ticker")
        if ticker:
            ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
        normalized_candidates.append(normalized_candidate)

    duplicate_tickers = sorted(
        ticker for ticker, count in ticker_counts.items() if count > 1
    )
    response_warnings: list[str] = []
    validated_candidates = []
    for candidate in normalized_candidates:
        candidate_warnings = list(candidate.get("entity_validation_warnings", []))
        ticker = candidate.get("ticker")
        if ticker in duplicate_tickers:
            candidate_warnings.append(f"Duplicate ticker in candidate universe: {ticker}")
        candidate["entity_validation_warnings"] = candidate_warnings
        candidate["entity_validation_status"] = (
            "valid" if not candidate_warnings else "needs_review"
        )
        response_warnings.extend(candidate_warnings)
        validated_candidates.append(candidate)

    updated_response["candidate_securities"] = validated_candidates
    proposed_universe = updated_response.get("proposed_research_universe")
    if isinstance(proposed_universe, dict):
        updated_universe = dict(proposed_universe)
        updated_universe["candidate_securities"] = validated_candidates
        updated_response["proposed_research_universe"] = updated_universe

    presentation = updated_response.get("user_presentation")
    if isinstance(presentation, dict):
        updated_presentation = dict(presentation)
        presentation_candidates = updated_presentation.get("companies_to_start_with")
        if isinstance(presentation_candidates, list):
            updated_presentation["companies_to_start_with"] = validated_candidates
        updated_response["user_presentation"] = updated_presentation

    invalid_count = len(
        [
            candidate
            for candidate in validated_candidates
            if candidate.get("entity_validation_status") != "valid"
        ]
    )
    updated_response["entity_validation"] = {
        "version": RCE_ENTITY_VALIDATION_VERSION,
        "candidate_count": len(validated_candidates),
        "valid_candidate_count": len(validated_candidates) - invalid_count,
        "invalid_candidate_count": invalid_count,
        "duplicate_tickers": duplicate_tickers,
        "warnings": sorted(set(response_warnings)),
    }
    return updated_response


def normalize_rce_candidate_entity(candidate: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(candidate)
    raw_ticker = normalized.get("ticker")
    ticker = str(raw_ticker).strip().upper() if raw_ticker is not None else ""
    company_name = str(normalized.get("company_name") or "").strip()
    rationale = str(normalized.get("inclusion_rationale") or "").strip()
    subdomain = (
        str(normalized.get("subdomain") or normalized.get("category") or "").strip()
    )
    confidence = _normalize_policy_confidence(normalized.get("confidence"))
    warnings: list[str] = []

    if not ticker:
        normalized["ticker"] = None
        warnings.append("Candidate security is missing a ticker.")
    elif not TICKER_PATTERN.match(ticker):
        normalized["ticker"] = ticker
        warnings.append(f"Candidate ticker has an unexpected format: {ticker}")
    else:
        normalized["ticker"] = ticker

    if not company_name:
        warnings.append(f"Candidate {ticker or '<missing ticker>'} is missing company_name.")
    if not rationale:
        warnings.append(
            f"Candidate {ticker or company_name or '<unknown>'} is missing inclusion_rationale."
        )
    if not subdomain:
        warnings.append(f"Candidate {ticker or company_name or '<unknown>'} is missing subdomain.")
    if confidence is None:
        warnings.append(f"Candidate {ticker or company_name or '<unknown>'} is missing confidence.")

    normalized["company_name"] = company_name
    normalized["inclusion_rationale"] = rationale
    normalized["subdomain"] = subdomain
    normalized["category"] = str(normalized.get("category") or subdomain).strip()
    normalized["confidence"] = confidence
    normalized["entity_validation_warnings"] = warnings
    normalized["entity_validation_status"] = "valid" if not warnings else "needs_review"
    return normalized


def _normalize_policy_confidence(value: Any) -> float | None:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, numeric_value))


def _as_policy_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value.copy()
    return [value]


def with_rce_diagnostics(
    response: ResearchConversationResponse,
    *,
    selected_provider_name: str | None = None,
) -> ResearchConversationResponse:
    metadata = response.metadata
    raw_candidate_count = metadata.raw_candidate_count or rce_candidate_count(
        response.structured_response
    )
    displayed_candidate_count = rce_displayed_candidate_count(
        response.structured_response
    )
    latency_seconds = metadata.latency_seconds
    if latency_seconds is None and metadata.response_timestamp is not None:
        latency_seconds = (
            metadata.response_timestamp - metadata.request_timestamp
        ).total_seconds()
    provider_error_message = metadata.provider_error_message
    if provider_error_message is None and response.errors:
        provider_error_message = "; ".join(response.errors)
    provider_error_type = metadata.provider_error_type
    if provider_error_type is None and provider_error_message:
        provider_error_type = "RCEProviderError"

    updated_metadata = replace(
        metadata,
        selected_provider_name=selected_provider_name
        or metadata.selected_provider_name
        or metadata.provider_name,
        mock_provider_used=metadata.provider_name == "mock",
        latency_seconds=latency_seconds,
        raw_candidate_count=raw_candidate_count,
        displayed_candidate_count=displayed_candidate_count,
        provider_error_type=provider_error_type,
        provider_error_message=provider_error_message,
    )
    return replace(response, metadata=updated_metadata)


def rce_candidate_count(structured_response: dict[str, Any] | None) -> int:
    if not isinstance(structured_response, dict):
        return 0
    candidates = structured_response.get("candidate_securities")
    if not isinstance(candidates, list):
        proposed_universe = structured_response.get("proposed_research_universe")
        if isinstance(proposed_universe, dict):
            candidates = proposed_universe.get("candidate_securities")
    return len(candidates) if isinstance(candidates, list) else 0


def rce_displayed_candidate_count(structured_response: dict[str, Any] | None) -> int:
    if not isinstance(structured_response, dict):
        return 0
    presentation = structured_response.get("user_presentation")
    if isinstance(presentation, dict):
        candidates = presentation.get("companies_to_start_with")
        if isinstance(candidates, list):
            return len([candidate for candidate in candidates if isinstance(candidate, dict)])
    return rce_candidate_count(structured_response)


def log_rce_request(response: ResearchConversationResponse) -> None:
    diagnostics = response.metadata.diagnostics()
    message = (
        "RCE request "
        f"provider={diagnostics['active_provider_name']} "
        f"selected_provider={diagnostics['selected_provider_name']} "
        f"model={diagnostics['active_model_name']} "
        f"prompt={diagnostics['prompt_version']} "
        f"fallback={diagnostics['fallback_used']} "
        f"error={bool(diagnostics['provider_error_message'])} "
        f"latency_seconds={diagnostics['latency_seconds']} "
        f"raw_candidate_count={diagnostics['raw_candidate_count']} "
        f"displayed_candidate_count={diagnostics['displayed_candidate_count']}"
    )
    logger.info(message)
    print(message)


def research_conversation_confidence_threshold(
    env: dict[str, str] | None = None,
) -> float:
    environment = env if env is not None else os.environ
    raw_threshold = environment.get(RCE_CONFIDENCE_THRESHOLD_ENV)
    if raw_threshold is None or raw_threshold.strip() == "":
        return DEFAULT_RCE_CONFIDENCE_THRESHOLD
    normalized_threshold = _normalize_policy_confidence(raw_threshold)
    if normalized_threshold is None:
        return DEFAULT_RCE_CONFIDENCE_THRESHOLD
    return normalized_threshold


def create_research_conversation_provider(
    env: dict[str, str] | None = None,
) -> ResearchConversationProvider:
    environment = env if env is not None else os.environ
    provider_name = environment.get(RCE_PROVIDER_ENV, DEFAULT_RCE_PROVIDER).strip().lower()

    if provider_name == "openai":
        from src.research_conversation.openai_provider import OpenAIResearchConversationProvider

        return OpenAIResearchConversationProvider(
            api_key=environment.get(OPENAI_API_KEY_ENV),
            model_name=environment.get(RCE_OPENAI_MODEL_ENV),
        )

    return MockResearchConversationProvider()


__all__ = [
    "DEFAULT_RCE_PROMPT_VERSION",
    "DEFAULT_RCE_PROVIDER",
    "DEFAULT_RCE_CONFIDENCE_THRESHOLD",
    "DEFAULT_RESEARCH_LAUNCH_ASSUMPTIONS",
    "OPENAI_API_KEY_ENV",
    "OPENAI_FALLBACK_WARNING",
    "RCE_CONFIDENCE_THRESHOLD_ENV",
    "RCE_OPENAI_MODEL_ENV",
    "RCE_PARSER_MODE",
    "RCE_PROVIDER_ENV",
    "RCE_SCHEMA_VERSION",
    "RCE_ENTITY_VALIDATION_VERSION",
    "MockResearchConversationProvider",
    "ProviderMetadata",
    "ResearchMap",
    "ResearchPlan",
    "ResearchConversationProvider",
    "ResearchConversationRequest",
    "ResearchConversationResponse",
    "ResearchConversationService",
    "ResearchUtilityScoreDraft",
    "UniverseReview",
    "apply_research_launch_policy",
    "create_research_conversation_provider",
    "empty_research_conversation_structure",
    "log_rce_request",
    "rce_candidate_count",
    "rce_displayed_candidate_count",
    "research_conversation_confidence_threshold",
    "normalize_rce_candidate_entity",
    "utc_now",
    "validate_rce_candidate_entities",
    "with_rce_diagnostics",
]
