import unittest
import json
from pathlib import Path

from src.research_conversation import (
    DEFAULT_RESEARCH_LAUNCH_ASSUMPTIONS,
    MockResearchConversationProvider,
    OPENAI_FALLBACK_WARNING,
    ProviderMetadata,
    ResearchMap,
    ResearchPlan,
    ResearchConversationRequest,
    ResearchConversationResponse,
    ResearchConversationService,
    ResearchUtilityScoreDraft,
    UniverseReview,
    create_research_conversation_provider,
    research_conversation_confidence_threshold,
    utc_now,
)
from src.research_conversation.openai_provider import (
    DEVELOPER_QA_EXAMPLES,
    OpenAIResearchConversationProvider,
    RCE_SYSTEM_PROMPT,
    parse_structured_response,
)


class FailingResearchConversationProvider:
    provider_name = "failing-provider"
    model_name = "failing-model"

    def interpret(self, request):
        raise RuntimeError("provider unavailable")


class FailingOpenAIResearchConversationProvider:
    provider_name = "openai"
    model_name = "test-openai-model"

    def interpret(self, request):
        response_timestamp = utc_now()
        return ResearchConversationResponse(
            metadata=ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.model_name,
                prompt_version=request.prompt_version,
                request_timestamp=request.request_timestamp,
                response_timestamp=response_timestamp,
                openai_api_key_present=True,
                provider_error_message="simulated OpenAI failure",
            ),
            structured_response={},
            confidence=None,
            errors=["simulated OpenAI failure"],
            warnings=[],
        )


class AlternateMockResearchConversationProvider:
    provider_name = "alternate-mock"
    model_name = "alternate-rce-v0.1"

    def interpret(self, request):
        response_timestamp = utc_now()
        return ResearchConversationResponse(
            metadata=ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.model_name,
                prompt_version=request.prompt_version,
                request_timestamp=request.request_timestamp,
                response_timestamp=response_timestamp,
            ),
            structured_response={
                "original_question": request.original_question,
                "primary_domain": "Compare",
                "primary_intent": "Alternate deterministic mock interpretation.",
            },
            confidence=0.75,
        )


class HighConfidenceClarifyingProvider:
    provider_name = "high-confidence"
    model_name = "test-model"

    def interpret(self, request):
        response_timestamp = utc_now()
        return ResearchConversationResponse(
            metadata=ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.model_name,
                prompt_version=request.prompt_version,
                request_timestamp=request.request_timestamp,
                response_timestamp=response_timestamp,
            ),
            structured_response={
                "original_question": request.original_question,
                "primary_domain": "Discover",
                "primary_intent": "Build a research universe.",
                "assumptions": [],
                "confidence": 0.82,
                "clarifying_questions_needed": True,
                "clarifying_questions": ["Should this include only U.S. companies?"],
                "candidate_securities": [],
            },
            confidence=0.82,
        )


class LowConfidenceProvider:
    provider_name = "low-confidence"
    model_name = "test-model"

    def interpret(self, request):
        response_timestamp = utc_now()
        return ResearchConversationResponse(
            metadata=ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.model_name,
                prompt_version=request.prompt_version,
                request_timestamp=request.request_timestamp,
                response_timestamp=response_timestamp,
            ),
            structured_response={
                "original_question": request.original_question,
                "primary_domain": "Unknown",
                "primary_intent": "Question is too ambiguous to classify.",
                "assumptions": [],
                "confidence": 0.42,
                "clarifying_questions_needed": True,
                "clarifying_questions": ["What market, theme, or company should we research?"],
                "candidate_securities": [],
            },
            confidence=0.42,
        )


class ResearchConversationTest(unittest.TestCase):
    def test_artifact_models_serialize_to_dicts(self):
        plan = ResearchPlan(
            research_objective="Research AI networking.",
            primary_theme="AI networking",
            research_lens=["Theme / Narrative"],
            included_areas=["Switching"],
            excluded_areas=["Consumer apps"],
            adjacent_areas=["Power"],
            candidate_subdomains=["Optical"],
            assumptions=["U.S.-listed equities"],
            known_blind_spots=["Private companies excluded"],
        )
        research_map = ResearchMap(areas=[{"area": "Switching", "subdomains": []}])
        score = ResearchUtilityScoreDraft(
            coverage=0.8,
            relevance=0.9,
            informational_diversity=0.7,
            explainability=0.85,
            refinement_readiness=0.8,
            overall=0.81,
            notes=["Draft only"],
        )
        review = UniverseReview(
            coverage_assessment=["Switching covered"],
            draft_research_utility_score=score,
        )

        self.assertEqual(plan.to_dict()["primary_theme"], "AI networking")
        self.assertEqual(research_map.to_dict()["areas"][0]["area"], "Switching")
        self.assertEqual(
            review.to_dict()["draft_research_utility_score"]["overall"], 0.81
        )

    def test_service_can_use_mock_provider(self):
        service = ResearchConversationService(MockResearchConversationProvider())

        response = service.interpret("Show me AI infrastructure companies.")

        self.assertFalse(response.has_errors)
        self.assertEqual(response.metadata.provider_name, "mock")
        self.assertEqual(response.metadata.model_name, "mock-rce-v0.2")
        self.assertEqual(
            response.structured_response["original_question"],
            "Show me AI infrastructure companies.",
        )
        self.assertEqual(response.structured_response["primary_domain"], "Discover")
        self.assertEqual(response.confidence, 0.72)
        self.assertGreaterEqual(
            len(response.structured_response["candidate_securities"]), 1
        )
        self.assertIn("interpretation", response.structured_response)
        self.assertIn("research_plan", response.structured_response)
        self.assertIn("proposed_research_universe", response.structured_response)
        self.assertIn("universe_review", response.structured_response)
        self.assertIn("user_presentation", response.structured_response)

    def test_provider_metadata_is_captured(self):
        service = ResearchConversationService(MockResearchConversationProvider())

        response = service.interpret("Research robotics.")

        self.assertEqual(
            response.metadata.prompt_version,
            "rce-multi-stage-artifact-pipeline-v0.1",
        )
        self.assertIsNotNone(response.metadata.request_timestamp)
        self.assertIsNotNone(response.metadata.response_timestamp)
        self.assertGreaterEqual(
            response.metadata.response_timestamp,
            response.metadata.request_timestamp,
        )

    def test_provider_errors_are_handled_cleanly(self):
        service = ResearchConversationService(FailingResearchConversationProvider())

        response = service.interpret("Research energy infrastructure.")

        self.assertTrue(response.has_errors)
        self.assertEqual(response.metadata.provider_name, "failing-provider")
        self.assertEqual(response.metadata.model_name, "failing-model")
        self.assertEqual(response.structured_response, {})
        self.assertEqual(response.errors, ["provider unavailable"])

    def test_same_request_can_be_sent_to_different_providers(self):
        request = ResearchConversationRequest(
            original_question="Compare AI and robotics."
        )
        mock_response = MockResearchConversationProvider().interpret(request)
        alternate_response = AlternateMockResearchConversationProvider().interpret(
            request
        )

        self.assertEqual(
            mock_response.structured_response["original_question"],
            alternate_response.structured_response["original_question"],
        )
        self.assertNotEqual(
            mock_response.metadata.provider_name,
            alternate_response.metadata.provider_name,
        )
        self.assertNotEqual(
            mock_response.structured_response["primary_domain"],
            alternate_response.structured_response["primary_domain"],
        )

    def test_mock_provider_remains_deterministic(self):
        request = ResearchConversationRequest(original_question="Research robotics.")

        first_response = MockResearchConversationProvider().interpret(request)
        second_response = MockResearchConversationProvider().interpret(request)

        self.assertEqual(
            first_response.structured_response,
            second_response.structured_response,
        )

    def test_mock_provider_returns_cybersecurity_candidate_list(self):
        request = ResearchConversationRequest(
            original_question="I'd like to understand the cybersecurity market."
        )

        response = MockResearchConversationProvider().interpret(request)
        candidates = response.structured_response["candidate_securities"]

        self.assertFalse(response.has_errors)
        self.assertEqual(
            response.structured_response["suggested_research_universe_name"],
            "Cybersecurity Candidate Research List",
        )
        self.assertEqual(len(candidates), 25)
        self.assertEqual(candidates[0]["ticker"], "PANW")
        self.assertIn("assumptions", response.structured_response)
        self.assertFalse(response.structured_response["clarifying_questions_needed"])
        self.assertEqual(response.structured_response["clarifying_questions"], [])
        self.assertTrue(response.structured_response["conversation_complete"])
        self.assertEqual(
            response.structured_response["terminal_artifact"],
            "Proposed Research Universe",
        )
        self.assertEqual(
            response.structured_response["research_plan"]["primary_theme"],
            "Cybersecurity",
        )
        self.assertEqual(
            response.structured_response["proposed_research_universe"]["candidate_securities"][0]["ticker"],
            "PANW",
        )
        self.assertIn(
            "coverage_assessment",
            response.structured_response["universe_review"],
        )
        self.assertIn(
            "ways_to_refine",
            response.structured_response["user_presentation"],
        )

    def test_confidence_threshold_suppresses_unnecessary_clarification(self):
        service = ResearchConversationService(
            HighConfidenceClarifyingProvider(),
            confidence_threshold=0.70,
        )

        response = service.interpret("Research infrastructure software.")

        self.assertFalse(response.structured_response["clarifying_questions_needed"])
        self.assertEqual(response.structured_response["clarifying_questions"], [])
        self.assertTrue(response.structured_response["conversation_complete"])
        self.assertEqual(
            response.structured_response["terminal_artifact"],
            "Proposed Research Universe",
        )

    def test_low_confidence_allows_one_optional_clarification(self):
        service = ResearchConversationService(
            LowConfidenceProvider(),
            confidence_threshold=0.70,
        )

        response = service.interpret("Help me with the market.")

        self.assertTrue(response.structured_response["clarifying_questions_needed"])
        self.assertEqual(
            response.structured_response["clarifying_questions"],
            ["What market, theme, or company should we research?"],
        )
        self.assertFalse(response.structured_response["conversation_complete"])
        self.assertEqual(
            response.structured_response["terminal_artifact"],
            "Optional Clarification",
        )

    def test_conversation_terminates_after_optional_clarification_turn(self):
        service = ResearchConversationService(
            LowConfidenceProvider(),
            confidence_threshold=0.70,
        )

        response = service.interpret(
            "Technology companies.",
            context={"clarification_turns": 1},
        )

        self.assertFalse(response.structured_response["clarifying_questions_needed"])
        self.assertEqual(response.structured_response["clarifying_questions"], [])
        self.assertTrue(response.structured_response["conversation_complete"])
        self.assertEqual(
            response.structured_response["terminal_artifact"],
            "Proposed Research Universe",
        )

    def test_assumptions_replace_blocking_scope_questions(self):
        service = ResearchConversationService(HighConfidenceClarifyingProvider())

        response = service.interpret("Research software companies.")

        self.assertEqual(response.structured_response["clarifying_questions"], [])
        for assumption in DEFAULT_RESEARCH_LAUNCH_ASSUMPTIONS:
            self.assertIn(assumption, response.structured_response["assumptions"])

    def test_confidence_threshold_can_be_configured_from_env(self):
        self.assertEqual(
            research_conversation_confidence_threshold(
                {"RCE_CONFIDENCE_THRESHOLD": "0.85"}
            ),
            0.85,
        )

    def test_openai_provider_can_be_instantiated_without_calling_api(self):
        provider = OpenAIResearchConversationProvider(
            api_key="test-key",
            model_name="test-model",
        )

        self.assertEqual(provider.provider_name, "openai")
        self.assertEqual(provider.model_name, "test-model")

    def test_openai_provider_missing_api_key_is_handled_cleanly(self):
        provider = OpenAIResearchConversationProvider(api_key=None)

        response = provider.interpret(
            ResearchConversationRequest(original_question="Research nuclear power.")
        )

        self.assertTrue(response.has_errors)
        self.assertEqual(response.metadata.provider_name, "openai")
        self.assertIn("OPENAI_API_KEY", response.errors[0])
        self.assertEqual(
            response.structured_response["original_question"],
            "Research nuclear power.",
        )
        diagnostics = response.metadata.diagnostics()
        self.assertFalse(diagnostics["openai_api_key_present"])
        self.assertEqual(diagnostics["raw_candidate_count"], 0)
        self.assertEqual(diagnostics["provider_error_type"], "MissingOpenAIAPIKey")
        self.assertIn("OPENAI_API_KEY", diagnostics["provider_error_message"])

    def test_openai_failure_falls_back_to_visible_mock_response(self):
        service = ResearchConversationService(FailingOpenAIResearchConversationProvider())

        response = service.interpret("Research cybersecurity companies.")

        self.assertFalse(response.has_errors)
        self.assertEqual(response.metadata.provider_name, "mock")
        self.assertEqual(response.metadata.selected_provider_name, "openai")
        self.assertTrue(response.metadata.fallback_used)
        self.assertTrue(response.metadata.mock_provider_used)
        self.assertIn(OPENAI_FALLBACK_WARNING, response.warnings)
        self.assertEqual(
            response.metadata.provider_error_message,
            "simulated OpenAI failure",
        )
        self.assertEqual(response.metadata.provider_error_type, "RCEProviderError")
        self.assertGreater(response.metadata.raw_candidate_count, 0)

    def test_mock_provider_identification_is_in_diagnostics(self):
        response = MockResearchConversationProvider().interpret(
            ResearchConversationRequest(original_question="Research robotics.")
        )

        diagnostics = response.metadata.diagnostics()
        self.assertEqual(diagnostics["active_provider_name"], "mock")
        self.assertTrue(diagnostics["mock_provider_used"])
        self.assertFalse(diagnostics["fallback_used"])
        self.assertEqual(
            diagnostics["raw_candidate_count"],
            len(response.structured_response["candidate_securities"]),
        )

    def test_service_response_includes_diagnostics_metadata(self):
        service = ResearchConversationService(MockResearchConversationProvider())

        response = service.interpret("Research AI infrastructure.")
        diagnostics = response.metadata.diagnostics()

        self.assertEqual(diagnostics["active_provider_name"], "mock")
        self.assertEqual(diagnostics["active_model_name"], "mock-rce-v0.2")
        self.assertEqual(
            diagnostics["prompt_version"],
            "rce-multi-stage-artifact-pipeline-v0.1",
        )
        self.assertIsNotNone(diagnostics["request_timestamp"])
        self.assertIsNotNone(diagnostics["response_timestamp"])
        self.assertIsNotNone(diagnostics["latency_seconds"])
        self.assertEqual(diagnostics["parser_mode"], "structured-json-normalizer")
        self.assertEqual(diagnostics["schema_version"], "rce-response-schema-v0.1")
        self.assertIn("provider_error_type", diagnostics)

    def test_candidate_count_diagnostics_track_provider_and_display(self):
        service = ResearchConversationService(MockResearchConversationProvider())

        response = service.interpret("I'd like to understand the cybersecurity market.")

        self.assertEqual(response.metadata.raw_candidate_count, 25)
        self.assertEqual(response.metadata.displayed_candidate_count, 25)

    def test_openai_response_parser_handles_valid_structured_json(self):
        response_text = """
        {
          "original_question": "Show me AI infrastructure companies.",
          "interpretation": {
            "original_question": "Show me AI infrastructure companies.",
            "estimated_user_sophistication": "Growing Investor",
            "primary_domain": "Discover",
            "primary_intent": "Identify a research universe around AI infrastructure.",
            "secondary_intents": ["Compare"],
            "research_lenses": ["Theme / Narrative"],
            "mentioned_companies": [],
            "themes": ["AI infrastructure"],
            "industries": ["Semiconductors"],
            "time_horizon": "Medium term",
            "asset_focus": "Equities",
            "confidence": 0.82,
            "clarifying_questions_needed": false,
            "clarifying_questions": []
          },
          "research_plan": {
            "research_objective": "Build an AI infrastructure research universe.",
            "primary_theme": "AI infrastructure",
            "research_lens": ["Theme / Narrative"],
            "included_areas": ["Compute", "Networking"],
            "excluded_areas": ["Power", "Cooling"],
            "adjacent_areas": ["Data center REITs"],
            "candidate_subdomains": ["Accelerators", "Switching", "Optical"],
            "assumptions": ["I assumed U.S.-listed public companies."],
            "known_blind_spots": ["Private infrastructure suppliers excluded."]
          },
          "proposed_research_universe": {
            "name": "AI Infrastructure Candidates",
            "candidate_security_categories": ["Semiconductors"],
            "candidate_securities": [
              {
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "inclusion_rationale": "Supplies accelerated compute platforms.",
                "subdomain": "Accelerators",
                "confidence": 0.9
              }
            ]
          },
          "universe_review": {
            "coverage_assessment": ["Compute included", "Power excluded by scope"],
            "relevance_assessment": ["Candidates map to infrastructure exposure."],
            "informational_diversity_assessment": ["Compute and networking represented."],
            "missing_areas": ["Power"],
            "weak_candidates": [],
            "redundant_candidates": [],
            "recommended_improvements": ["Add power if the user wants full infrastructure."],
            "draft_research_utility_score": {
              "coverage": 0.75,
              "relevance": 0.85,
              "informational_diversity": 0.7,
              "explainability": 0.9,
              "refinement_readiness": 0.8,
              "overall": 0.8,
              "notes": ["Experimental only."]
            }
          },
          "user_presentation": {
            "understanding": "You want to research AI infrastructure.",
            "approach": "Map infrastructure subdomains before selecting companies.",
            "areas_included": ["Compute", "Networking"],
            "areas_excluded": ["Power", "Cooling"],
            "companies_to_start_with": [
              {
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "inclusion_rationale": "Supplies accelerated compute platforms.",
                "subdomain": "Accelerators",
                "confidence": 0.9
              }
            ],
            "universe_review": ["Compute included", "Power excluded by scope"],
            "assumptions": ["I assumed U.S.-listed public companies."],
            "ways_to_refine": ["Narrow to networking only."]
          },
          "estimated_user_sophistication": "Growing Investor",
          "primary_domain": "Discover",
          "primary_intent": "Identify a research universe around AI infrastructure.",
          "research_objective": {
            "primary_theme": "AI infrastructure",
            "research_focus": "Infrastructure suppliers",
            "implied_investment_question": "Which public companies are exposed to AI infrastructure buildout?"
          },
          "secondary_intents": ["Compare"],
          "research_lenses": ["Theme / Narrative"],
          "mentioned_companies": [],
          "themes": ["AI infrastructure"],
          "industries": ["Semiconductors"],
          "time_horizon": "Medium term",
          "asset_focus": "Equities",
          "assumptions": ["I assumed U.S.-listed public companies."],
          "confidence": 0.82,
          "clarifying_questions_needed": false,
          "clarifying_questions": [],
          "conversation_complete": true,
          "terminal_artifact": "Proposed Research Universe",
          "suggested_research_mission_title": "AI Infrastructure Beneficiaries",
          "suggested_research_mission_summary": "Build a reviewable scope.",
          "suggested_research_universe_name": "AI Infrastructure Candidates",
          "research_map": [
            {"area": "Compute", "subdomains": ["Accelerators"]},
            {"area": "Networking", "subdomains": ["Switching", "Optical"]}
          ],
          "included_areas": ["Compute", "Networking"],
          "excluded_areas": ["Power", "Cooling"],
          "candidate_security_categories": ["Semiconductors"],
          "candidate_securities": [
            {
              "ticker": "NVDA",
              "company_name": "NVIDIA",
              "inclusion_rationale": "Supplies accelerated compute platforms.",
              "subdomain": "Accelerators",
              "confidence": 0.9
            }
          ],
          "coverage_assessment": ["Compute included", "Power excluded by scope"],
          "ways_to_refine": ["Narrow to networking only."],
          "warnings": [],
          "limitations": ["Research interpretation only."]
        }
        """

        structured_response, warnings, errors = parse_structured_response(
            response_text,
            "Show me AI infrastructure companies.",
        )

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(structured_response["confidence"], 0.82)
        self.assertEqual(
            structured_response["assumptions"][0],
            "I assumed U.S.-listed public companies.",
        )
        self.assertEqual(
            structured_response["candidate_securities"][0]["ticker"], "NVDA"
        )
        self.assertEqual(
            structured_response["candidate_securities"][0]["subdomain"],
            "Accelerators",
        )
        self.assertEqual(structured_response["research_map"][1]["area"], "Networking")
        self.assertEqual(structured_response["excluded_areas"], ["Power", "Cooling"])
        self.assertEqual(
            structured_response["coverage_assessment"],
            ["Compute included", "Power excluded by scope"],
        )
        self.assertEqual(
            structured_response["research_plan"]["candidate_subdomains"][1],
            "Switching",
        )
        self.assertEqual(
            structured_response["universe_review"]["draft_research_utility_score"]["overall"],
            0.8,
        )
        self.assertEqual(
            structured_response["user_presentation"]["understanding"],
            "You want to research AI infrastructure.",
        )

    def test_openai_parser_preserves_provider_verification_marker(self):
        structured_response, warnings, errors = parse_structured_response(
            """
            {
              "original_question": "Research AI.",
              "primary_domain": "Discover",
              "primary_intent": "Build an AI research list.",
              "confidence": 0.8,
              "candidate_securities": [],
              "provider_verification_marker": "LIVE_OPENAI_RCE_RESPONSE"
            }
            """,
            "Research AI.",
        )

        self.assertEqual(errors, [])
        self.assertEqual(
            structured_response["provider_verification_marker"],
            "LIVE_OPENAI_RCE_RESPONSE",
        )

    def test_openai_response_parser_handles_missing_multistage_sections(self):
        response_text = """
        {
          "original_question": "Research cybersecurity companies.",
          "primary_domain": "Discover",
          "primary_intent": "Build a cybersecurity research list.",
          "confidence": 0.8,
          "assumptions": ["U.S.-listed equities"],
          "candidate_securities": [
            {
              "ticker": "PANW",
              "company_name": "Palo Alto Networks",
              "inclusion_rationale": "Cybersecurity platform vendor.",
              "category": "Platform security",
              "confidence": 0.9
            }
          ]
        }
        """

        structured_response, warnings, errors = parse_structured_response(
            response_text,
            "Research cybersecurity companies.",
        )

        self.assertEqual(errors, [])
        self.assertIn("Missing structured field: research_plan", warnings)
        self.assertIn("research_plan", structured_response)
        self.assertIn("universe_review", structured_response)
        self.assertIn("user_presentation", structured_response)
        self.assertEqual(
            structured_response["proposed_research_universe"]["candidate_securities"][0]["ticker"],
            "PANW",
        )

    def test_openai_response_parser_caps_clarifying_questions_after_candidates(self):
        response_text = """
        {
          "original_question": "Research cybersecurity companies.",
          "interpretation": {
            "original_question": "Research cybersecurity companies.",
            "estimated_user_sophistication": "Growing Investor",
            "primary_domain": "Discover",
            "primary_intent": "Build a cybersecurity research list.",
            "secondary_intents": [],
            "research_lenses": ["Theme / Narrative"],
            "mentioned_companies": [],
            "themes": ["Cybersecurity"],
            "industries": ["Software"],
            "time_horizon": "Unspecified",
            "asset_focus": "Equities",
            "confidence": 0.8,
            "clarifying_questions_needed": true,
            "clarifying_questions": [
              "Should this be pure-play only?",
              "Should cloud platforms be included?"
            ]
          },
          "research_plan": {
            "research_objective": "Build a cybersecurity research universe.",
            "primary_theme": "Cybersecurity",
            "research_lens": ["Theme / Narrative"],
            "included_areas": ["Platform security"],
            "excluded_areas": ["IT services"],
            "adjacent_areas": [],
            "candidate_subdomains": ["Platform security"],
            "assumptions": ["I assumed U.S.-listed equities."],
            "known_blind_spots": []
          },
          "proposed_research_universe": {
            "name": "Cybersecurity Candidates",
            "candidate_security_categories": ["Platform security"],
            "candidate_securities": [
              {
                "ticker": "PANW",
                "company_name": "Palo Alto Networks",
                "inclusion_rationale": "Cybersecurity platform vendor.",
                "category": "Platform security",
                "confidence": 0.9
              }
            ]
          },
          "universe_review": {
            "coverage_assessment": ["Platform security included"],
            "relevance_assessment": ["PANW is directly relevant."],
            "informational_diversity_assessment": ["Single candidate is narrow."],
            "missing_areas": ["Identity", "Endpoint"],
            "weak_candidates": [],
            "redundant_candidates": [],
            "recommended_improvements": ["Add identity and endpoint vendors."],
            "draft_research_utility_score": {
              "coverage": 0.4,
              "relevance": 0.9,
              "informational_diversity": 0.3,
              "explainability": 0.8,
              "refinement_readiness": 0.8,
              "overall": 0.64,
              "notes": []
            }
          },
          "user_presentation": {
            "understanding": "You want cybersecurity companies.",
            "approach": "Start with platform security.",
            "areas_included": ["Platform security"],
            "areas_excluded": ["IT services"],
            "companies_to_start_with": [
              {
                "ticker": "PANW",
                "company_name": "Palo Alto Networks",
                "inclusion_rationale": "Cybersecurity platform vendor.",
                "category": "Platform security",
                "confidence": 0.9
              }
            ],
            "universe_review": ["Platform security included"],
            "assumptions": ["I assumed U.S.-listed equities."],
            "ways_to_refine": ["Exclude cloud platforms."]
          },
          "estimated_user_sophistication": "Growing Investor",
          "primary_domain": "Discover",
          "primary_intent": "Build a cybersecurity research list.",
          "research_objective": {
            "primary_theme": "Cybersecurity",
            "research_focus": "Security vendors",
            "implied_investment_question": "Which companies define a cybersecurity research universe?"
          },
          "secondary_intents": [],
          "research_lenses": ["Theme / Narrative"],
          "mentioned_companies": [],
          "themes": ["Cybersecurity"],
          "industries": ["Software"],
          "time_horizon": "Unspecified",
          "asset_focus": "Equities",
          "assumptions": "I assumed U.S.-listed equities.",
          "confidence": 0.8,
          "clarifying_questions_needed": true,
          "clarifying_questions": [
            "Should this be pure-play only?",
            "Should cloud platforms be included?"
          ],
          "conversation_complete": false,
          "terminal_artifact": "",
          "suggested_research_mission_title": "Cybersecurity Research",
          "suggested_research_mission_summary": "Build a starter list.",
          "suggested_research_universe_name": "Cybersecurity Candidates",
          "research_map": [{"area": "Platform security", "subdomains": []}],
          "included_areas": ["Platform security"],
          "excluded_areas": ["IT services"],
          "candidate_security_categories": ["Platform security"],
          "candidate_securities": [
            {
              "ticker": "PANW",
              "company_name": "Palo Alto Networks",
              "inclusion_rationale": "Cybersecurity platform vendor.",
              "category": "Platform security",
              "confidence": 0.9
            }
          ],
          "coverage_assessment": ["Platform security included"],
          "ways_to_refine": ["Exclude cloud platforms."],
          "warnings": [],
          "limitations": []
        }
        """

        structured_response, warnings, errors = parse_structured_response(
            response_text,
            "Research cybersecurity companies.",
        )

        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertFalse(structured_response["clarifying_questions_needed"])
        self.assertEqual(structured_response["clarifying_questions"], [])
        self.assertTrue(structured_response["conversation_complete"])
        self.assertEqual(
            structured_response["assumptions"][0],
            "I assumed U.S.-listed equities.",
        )
        for assumption in DEFAULT_RESEARCH_LAUNCH_ASSUMPTIONS:
            self.assertIn(assumption, structured_response["assumptions"])

    def test_openai_prompt_requires_research_universe_methodology(self):
        provider = OpenAIResearchConversationProvider(api_key="test-key")
        prompt_payload = provider._user_prompt(
            ResearchConversationRequest(
                original_question=(
                    "I want to research networking and interconnect companies "
                    "benefiting from AI."
                )
            )
        )

        self.assertIn("Research Universe construction methodology", RCE_SYSTEM_PROMPT)
        self.assertIn("Construct a dynamic Research Map", RCE_SYSTEM_PROMPT)
        self.assertIn("Optimize candidate selection for ecosystem coverage", RCE_SYSTEM_PROMPT)
        self.assertIn("developer_qa_examples", prompt_payload)
        self.assertIn(DEVELOPER_QA_EXAMPLES[0]["question"], prompt_payload)
        self.assertIn("Power companies are largely excluded", prompt_payload)
        self.assertIn("AI companies solving cancer", prompt_payload)
        self.assertIn("Retail companies gaining share through AI", prompt_payload)
        self.assertIn("Multi-stage RCE artifact workflow", RCE_SYSTEM_PROMPT)
        self.assertIn("research_plan_schema", prompt_payload)
        self.assertIn("universe_review_schema", prompt_payload)
        self.assertIn("benchmark_qa_fixtures", prompt_payload)
        self.assertIn("provider_verification_marker", prompt_payload)
        self.assertIn("LIVE_OPENAI_RCE_RESPONSE", prompt_payload)

    def test_openai_response_parser_handles_malformed_response(self):
        structured_response, warnings, errors = parse_structured_response(
            "not json",
            "Research energy.",
        )

        self.assertEqual(warnings, [])
        self.assertTrue(errors)
        self.assertEqual(structured_response["original_question"], "Research energy.")
        self.assertEqual(structured_response["candidate_securities"], [])

    def test_service_can_switch_provider_based_on_config(self):
        mock_provider = create_research_conversation_provider({"RCE_PROVIDER": "mock"})
        openai_provider = create_research_conversation_provider(
            {
                "RCE_PROVIDER": "openai",
                "OPENAI_API_KEY": "test-key",
                "RCE_OPENAI_MODEL": "test-model",
            }
        )

        self.assertEqual(mock_provider.provider_name, "mock")
        self.assertEqual(openai_provider.provider_name, "openai")
        self.assertEqual(openai_provider.model_name, "test-model")

    def test_provider_config_defaults_to_mock(self):
        provider = create_research_conversation_provider({})

        self.assertEqual(provider.provider_name, "mock")

    def test_benchmark_qa_fixtures_exist_for_required_scenarios(self):
        fixture_path = Path("tests/fixtures/rce_benchmark_scenarios.json")
        scenarios = json.loads(fixture_path.read_text())
        scenario_ids = {scenario["id"] for scenario in scenarios}

        self.assertEqual(len(scenarios), 6)
        self.assertIn("ai-networking-interconnects", scenario_ids)
        self.assertIn("ai-cancer-drug-discovery", scenario_ids)
        self.assertIn("data-center-power-buildout", scenario_ids)
        self.assertIn("cybersecurity-market", scenario_ids)
        self.assertIn("micron-earnings-call-options", scenario_ids)
        self.assertIn("fashion-brands-taking-market-share", scenario_ids)

    def test_ui_helpers_can_prepare_multistage_artifacts(self):
        from app import rce_candidate_rows, rce_user_presentation

        structured_response = MockResearchConversationProvider().interpret(
            ResearchConversationRequest(
                original_question="I'd like to understand the cybersecurity market."
            )
        ).structured_response

        presentation = rce_user_presentation(structured_response)
        candidate_rows = rce_candidate_rows(presentation["companies_to_start_with"])

        self.assertIn("understanding", presentation)
        self.assertEqual(candidate_rows[0]["Ticker"], "PANW")
        self.assertTrue(presentation["universe_review"])


if __name__ == "__main__":
    unittest.main()
