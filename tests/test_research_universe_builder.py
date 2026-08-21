import json
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.research_conversation import MockResearchConversationProvider, ResearchConversationRequest, ResearchConversationService
from src.research_conversation.openai_provider import OpenAIResearchConversationProvider
from src.research_universe_builder import (
    GENERAL_USER_ORIGIN, build_free_form_request, candidate_key, create_draft,
    parse_anchor_companies, reconcile_anchors,
)


class ResearchUniverseBuilderTest(unittest.TestCase):
    def test_universe_default_is_hidden_from_normal_continue_research(self):
        from src.research_universe_builder_page import _saved_options
        with TemporaryDirectory() as directory:
            data = Path(directory) / "data"
            data.mkdir()
            (data / "universe_default.csv").touch()
            genuine = data / "my_research_universe.csv"
            genuine.touch()
            self.assertEqual(_saved_options(Path(directory)), (genuine,))
        home_source = Path("app.py").read_text(encoding="utf-8")
        saved = home_source[home_source.index("def render_saved_research_universes") : home_source.index("def response_field")]
        self.assertIn('universe_path.stem.casefold() == "universe_default"', saved)

    def test_entry_point_is_registered_and_uses_shared_curator_language(self):
        app_source = Path("app.py").read_text(encoding="utf-8")
        page_source = Path("src/research_universe_builder_page.py").read_text(encoding="utf-8")
        self.assertIn('"Research Launchpad"', app_source)
        self.assertIn('"Research Universe Builder": "Research Launchpad"', app_source)
        self.assertIn("What are you interested in researching?", page_source)
        self.assertIn("Browse established research topics — optional", page_source)
        self.assertIn("Launch Research", page_source)
        self.assertIn("Companies you already know — optional", page_source)
        self.assertNotIn('placeholder="TSCO', page_source)
        renderer_source = Path("src/research_universe_review_page.py").read_text(encoding="utf-8")
        self.assertIn("Analyze Universe", renderer_source)
        self.assertNotIn('"Analyze Company"', renderer_source)
        self.assertIn("Suggestion details", renderer_source)
        self.assertNotIn("Authored Source Corpus", page_source)

    def test_established_topic_catalog_has_all_seventeen_readable_topics(self):
        from src.research_universe_builder_page import established_topics
        topics = established_topics()
        self.assertEqual(len(topics), 17)
        names = {row.benchmark_name for row in topics}
        self.assertIn("AI Data-Center Networking and Cabling", names)
        self.assertIn("Traditional Banking", names)

    def test_title_normalizes_repeated_universe_and_market_wording(self):
        from src.research_universe_builder_page import readable_universe_title
        self.assertEqual(readable_universe_title(None, None, "Semiconductor Memory Market Universe"), "Semiconductor Memory")
        self.assertEqual(readable_universe_title("Agricultural Robotics Research Universe", None, ""), "Agricultural Robotics")
        self.assertEqual(
            readable_universe_title(None, None, "I'd like to know about hyperscalers..."),
            "Hyperscalers",
        )
        self.assertEqual(
            readable_universe_title(None, None, "Research semiconductor and DRAM memory market universe research universe"),
            "Semiconductor and DRAM memory",
        )

    def test_established_topic_is_owned_by_universe(self):
        from src.research_universe import ResearchUniverseReviewService
        universe = ResearchUniverseReviewService().assemble(
            universe_id="topic", title="Robotics", established_topic="Agricultural Robotics",
        )
        self.assertEqual(universe.established_topic, "Agricultural Robotics")

    def test_established_topic_loads_every_authored_constituent_as_included(self):
        from src.rce_benchmark_explorer_service import RCEBenchmarkExplorerService
        from src.research_universe import ResearchUniverseReviewService
        from src.research_universe_builder_page import _topic_records
        service = RCEBenchmarkExplorerService()
        records = _topic_records(service, "ai-data-center-networking-cabling")
        universe = ResearchUniverseReviewService().assemble(
            universe_id="topic-test", title="Topic", starting_companies=records,
        )
        self.assertEqual(len(records), 17)
        self.assertEqual(len(universe.approved_membership), 17)
        self.assertTrue(all(row.disposition.value == "included" for row in universe.candidates))
        self.assertTrue(all(row.source_records[0].source_reference for row in universe.candidates))

    def test_free_form_question_and_optional_anchors(self):
        request = build_free_form_request("Research pet health.", ())
        self.assertEqual(request.original_question, "Research pet health.")
        self.assertEqual(request.anchor_companies, ())
        self.assertEqual(request.request_origin, GENERAL_USER_ORIGIN)

    def test_anchor_delimiters_normalize_and_original_is_preserved(self):
        raw = "  TSCO\nZoetis,  FRPT\r\nTractor   Supply  "
        anchors = parse_anchor_companies(raw)
        self.assertEqual([a.supplied_value for a in anchors], ["TSCO", "Zoetis", "FRPT"])
        self.assertEqual(anchors[0].normalized_ticker, "TSCO")
        self.assertEqual(anchors[1].normalized_ticker, "ZOETIS")
        request = build_free_form_request("Question", anchors)
        response = MockResearchConversationProvider().interpret(request)
        draft = create_draft("Question", raw, anchors, request, response)
        self.assertEqual(draft.original_anchor_input, raw)

    def test_free_form_provider_payload_has_anchors_but_no_benchmark_material(self):
        provider = OpenAIResearchConversationProvider(client=MagicMock())
        anchors = parse_anchor_companies("TSCO, Zoetis")
        payload = json.loads(provider._user_prompt(build_free_form_request("Research animals.", anchors)))
        self.assertEqual(payload["anchor_companies"], ["TSCO", "Zoetis"])
        self.assertNotIn("benchmark_qa_fixtures", payload)
        serialized = json.dumps(payload).casefold()
        self.assertNotIn("expected_candidates", serialized)
        self.assertNotIn("scoring_config", serialized)
        self.assertNotIn("authored source corpus", serialized)

    def test_benchmark_style_request_remains_unchanged_and_has_no_anchors(self):
        provider = OpenAIResearchConversationProvider(client=MagicMock())
        legacy = ResearchConversationRequest(original_question="Benchmark question")
        payload = json.loads(provider._user_prompt(legacy))
        self.assertEqual(legacy.anchor_companies, ())
        self.assertEqual(legacy.request_origin, "unspecified")
        self.assertNotIn("anchor_companies", payload)
        self.assertIn("benchmark_qa_fixtures", payload)

    def test_service_accepts_explicit_request_without_provider_call_in_setup(self):
        provider = MagicMock(wraps=MockResearchConversationProvider())
        request = build_free_form_request("Research robotics.", ())
        response = ResearchConversationService(provider).interpret_request(request)
        self.assertFalse(response.has_errors)
        provider.interpret.assert_called_once_with(request)

    def test_anchor_reconciliation_returned_omitted_unresolved_and_malformed(self):
        anchors = parse_anchor_companies("TSCO, Zoetis")
        candidates = ({"ticker": "TSCO", "company_name": "Tractor Supply"},)
        review = reconcile_anchors(anchors, candidates, [
            {"supplied_value": "Mystery Co", "disposition": "unresolved"},
            "malformed",
        ])
        self.assertEqual([row.disposition for row in review], ["included", "not_included"])
        self.assertIsNone(review[1].explanation)

    def test_anchor_parser_accepts_comma_newline_and_mixed_input(self):
        self.assertEqual([row.supplied_value for row in parse_anchor_companies("CRWD,PANW,ZS")], ["CRWD", "PANW", "ZS"])
        self.assertEqual([row.supplied_value for row in parse_anchor_companies("CRWD\nPANW\nZS")], ["CRWD", "PANW", "ZS"])
        self.assertEqual([row.supplied_value for row in parse_anchor_companies("CRWD, PANW\nZS")], ["CRWD", "PANW", "ZS"])

    def test_candidates_start_pending_and_only_approved_enter_draft(self):
        request = build_free_form_request("Research robotics.", ())
        response = MockResearchConversationProvider().interpret(request)
        draft = create_draft("Research robotics.", "", (), request, response)
        candidate = draft.candidates[0]
        self.assertNotIn(candidate_key(candidate), draft.approved_candidate_keys)
        draft.approve(candidate)
        self.assertIn(candidate_key(candidate), draft.approved_candidate_keys)
        self.assertEqual(len(draft.approved_candidate_keys), 1)
        self.assertGreater(len(draft.candidates), 1)  # unreviewed candidates remain valid pending rows

    def test_openai_call_only_occurs_when_interpret_is_invoked(self):
        client = MagicMock()
        provider = OpenAIResearchConversationProvider(client=client)
        request = build_free_form_request("Research animals.", ())
        self.assertFalse(client.responses.create.called)
        client.responses.create.return_value = SimpleNamespace(
            status="completed", output_text=json.dumps({"original_question": request.original_question, "candidate_securities": []})
        )
        provider.interpret(request)
        self.assertTrue(client.responses.create.called)


if __name__ == "__main__":
    unittest.main()
