import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import pytest

from src.rce_benchmark_explorer_service import (
    CERTIFIED_REVIEW_STATE_LABEL,
    COMPLETENESS_LIMITATION,
    DEFAULT_RUN_LABEL,
    AuthoredSourceCandidate,
    RCECorpusCandidate,
    RCEBenchmarkExplorerService,
    _group,
    compare_corpora,
)

BASELINE = Path("data/research/rce_benchmark_baseline_v0.1.1.json")
CONFIG = Path("config/rce_benchmark_scoring_v0.1.json")
DATABASE = Path("data/research/rce_benchmarks.sqlite")
FIXTURES = Path("tests/fixtures/rce_benchmarks")
PAGE = Path("src/rce_benchmark_explorer_page.py")
CHANGED_FILES = [Path("app.py"), PAGE, Path("src/rce_benchmark_explorer_service.py"), Path(__file__)]
AUTHORITATIVE_HASHES = {
    BASELINE: "4b9ed31f29350fcd91ed10d710a4e5ac9a82af38181ed900c34bd9caa959965d",
    CONFIG: "62efa8516e0aaf64839204ffca38a7928f641dfd4e90d7e01549cd3cac165d1e",
    DATABASE: "48ea2c839dee93a995d9cfb21869f015d7a5b63b18a7ee2e4591b04a7da235c8",
}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def fixture_digest():
    checksum = hashlib.sha256()
    for path in sorted(FIXTURES.glob("*.json")):
        checksum.update(path.name.encode("utf-8"))
        checksum.update(b"\0")
        checksum.update(path.read_bytes())
    return checksum.hexdigest()

class RCEBenchmarkExplorerServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = RCEBenchmarkExplorerService()

    @staticmethod
    def authored(name, ticker=None, section="Authored category"):
        return AuthoredSourceCandidate("test", "Test", "v1", "source.pdf", "1", section,
                                      name, ticker, "primary", None, False, 1)

    @staticmethod
    def returned(name, ticker=None, category="RCE category", rank=1):
        return RCECorpusCandidate(name, ticker, rank, category, "valid", True, True)

    def test_ticker_first_matching_reconciles_block_and_ignores_category(self):
        rows = compare_corpora((self.authored("Block", " SQ "),),
                               (self.returned("Block, Inc.", "sq", "Payments"),))
        self.assertEqual(rows[0].comparison_outcome, "agreement")
        self.assertFalse(rows[0].category_match)
        self.assertIn("ticker", rows[0].explanation)

    def test_conflicting_tickers_with_same_name_require_identity_review(self):
        rows = compare_corpora((self.authored("Example Holdings", "AAA"),),
                               (self.returned("Example Holdings", "BBB"),))
        self.assertEqual({row.comparison_outcome for row in rows}, {"identity_review", "authored_only"})

    def test_missing_ticker_uses_unambiguous_name_fallback(self):
        rows = compare_corpora((self.authored("Example, Inc."),),
                               (self.returned("Example Inc", None),))
        self.assertEqual(rows[0].comparison_outcome, "agreement")
        self.assertIn("name fallback", rows[0].explanation)

    def test_ambiguous_identifier_requires_review(self):
        authored = (self.authored("Alpha", "DUPE"), self.authored("Beta", "DUPE"))
        rows = compare_corpora(authored, (self.returned("Unknown", "DUPE"),))
        self.assertIn("identity_review", {row.comparison_outcome for row in rows})

    def test_distinct_listing_contexts_are_not_merged(self):
        rows = compare_corpora((self.authored("Dual Listed", "NYSE:ABC"),),
                               (self.returned("Dual Listed", "NASDAQ:ABC"),))
        self.assertIn("identity_review", {row.comparison_outcome for row in rows})

    def test_primary_comparison_tables_are_concise_accessible_and_company_colored(self):
        source = PAGE.read_text(encoding="utf-8")
        comparison = source[source.index("def _render_corpus_comparison"):source.index("def render_benchmark_explorer")]
        for forbidden in ('"RCE presence"', '"Authored presence"', '"Original category"',
                          '"Returned category"', '"Status"'):
            self.assertNotIn(forbidden, comparison)
        self.assertIn('subset=["Company"]', source)
        self.assertIn("Green — appears in both corpora", comparison)
        self.assertIn("Red — appears only in this corpus", comparison)
        self.assertIn("Yellow — identity requires review", comparison)
        self.assertIn('st.expander("Candidate comparison details"', comparison)
        self.assertIn('"Authored category"', comparison)
        self.assertIn('"RCE category"', comparison)

    def test_loads_all_seventeen_certified_domains(self):
        summary = self.service.run_summary()
        self.assertTrue(summary.available)
        self.assertEqual(summary.run_label, DEFAULT_RUN_LABEL)
        self.assertEqual(summary.domain_count, 17)
        self.assertEqual(summary.successful_domain_count, 17)
        self.assertEqual(len({row.benchmark_id for row in summary.domains}), 17)

    def test_selects_one_benchmark_with_expected_and_actual_research(self):
        detail = self.service.get_benchmark("ai-data-center-networking-cabling")
        self.assertIsNotNone(detail)
        self.assertEqual(detail.provider, "openai")
        self.assertEqual(detail.model, "gpt-4.1-mini")
        self.assertTrue(detail.reviewed.expected_candidates)
        self.assertTrue(detail.candidates)

    def test_complete_author_reviewed_corpus_is_loaded_without_summarizing(self):
        corpus = self.service.reviewed_corpus()
        fixture_documents = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(FIXTURES.glob("*.json"))]
        self.assertEqual(corpus.benchmark_count, len(fixture_documents))
        self.assertEqual(corpus.category_count, sum(len(row["categories"]) for row in fixture_documents))
        self.assertEqual(corpus.constituent_count, sum(len(row["securities"]) for row in fixture_documents))
        self.assertEqual((corpus.benchmark_count, corpus.category_count, corpus.constituent_count), (17, 77, 107))
        self.assertEqual(
            {row["benchmark_id"] for row in corpus.constituents},
            {row["benchmark"]["benchmark_id"] for row in fixture_documents},
        )

    def test_detail_retains_all_constituents_before_presentational_grouping(self):
        for domain in self.service.list_domains():
            detail = self.service.get_benchmark(domain.benchmark_id)
            self.assertEqual(
                detail.reviewed.constituents,
                detail.reviewed.expected_candidates + detail.reviewed.exclusions,
            )

    def test_page_uses_selected_authored_source_corpus_before_comparison(self):
        page_source = PAGE.read_text(encoding="utf-8")
        rendered_source = page_source[page_source.index("def render_benchmark_explorer"):]
        selection_position = rendered_source.index('st.subheader("Choose a benchmark")')
        comparison_position = rendered_source.index('_render_inline_curator_workflow(service, comparison, analyze_company)')
        self.assertLess(selection_position, comparison_position)
        self.assertNotIn('_render_reviewed_corpus(service.reviewed_corpus())', page_source)
        self.assertIn("Authored Source Corpus vs RCE Candidate Corpus", page_source)

    def test_one_domain_reconciles_to_certified_score(self):
        detail = self.service.get_benchmark("ai-data-center-networking-cabling")
        self.assertAlmostEqual(detail.overall_score, 0.626462, places=6)
        self.assertAlmostEqual(sum(row.weighted_contribution for row in detail.metrics), detail.overall_score, places=5)

    def test_metrics_reconcile_with_certified_scoring_configuration(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        for domain in self.service.list_domains():
            detail = self.service.get_benchmark(domain.benchmark_id)
            self.assertEqual(detail.scoring_configuration_version, config["config_version"])
            by_name = {row.metric_name: row for row in detail.metrics}
            for name, weight in config["overall_weights"].items():
                self.assertEqual(by_name[name].configured_weight, weight)
                self.assertAlmostEqual(by_name[name].weighted_contribution, by_name[name].raw_value * weight)
            self.assertAlmostEqual(sum(row.weighted_contribution for row in detail.metrics), detail.overall_score, places=5)
            self.assertEqual(len(detail.metrics), 10)

    def test_candidate_grouping(self):
        details = [self.service.get_benchmark(row.benchmark_id) for row in self.service.list_domains()]
        groups = {group for detail in details for group in (
            "expected_returned" if detail.candidates_in_group("expected_returned") else None,
            "expected_missing" if detail.candidates_in_group("expected_missing") else None,
            "unexpected" if detail.candidates_in_group("unexpected") else None,
            "must_exclude" if detail.candidates_in_group("must_exclude") else None,
        ) if group}
        self.assertTrue({"expected_returned", "expected_missing", "unexpected"} <= groups)
        for detail in details:
            for candidate in detail.candidates_in_group("must_exclude"):
                self.assertTrue(candidate.returned)
                self.assertEqual(candidate.expected_classification, "must_exclude")
        synthetic = self.service._candidate({
            "company_name": "Excluded Co", "returned": True,
            "expected_classification": "must_exclude", "comparison_outcome": "must_exclude_returned",
        })
        self.assertEqual(_group(synthetic), "must_exclude")

    def test_review_queue_counts_reconcile(self):
        summary = self.service.run_summary()
        queue = self.service.review_queue()
        self.assertEqual(len(queue), summary.unresolved_review_count)
        self.assertTrue(queue)
        self.assertTrue(all(row.reviewer_status in (None, "needs_verification") for row in queue))

    def test_review_counts_are_labeled_as_certified_snapshot(self):
        summary = self.service.run_summary()
        self.assertEqual(summary.review_state_label, CERTIFIED_REVIEW_STATE_LABEL)
        self.assertIn("Certified-snapshot", PAGE.read_text(encoding="utf-8"))
        self.assertIn("not a live review queue", PAGE.read_text(encoding="utf-8"))

    def test_execution_status_wording_is_not_pass_fail(self):
        self.assertTrue(all(row.execution_status == "success" for row in self.service.list_domains()))
        page_source = PAGE.read_text(encoding="utf-8")
        self.assertIn("Execution Status", page_source)
        self.assertNotIn('"Pass"', page_source)
        self.assertNotIn('"Fail"', page_source)

    def test_curator_workbench_has_question_led_section_order(self):
        page_source = PAGE.read_text(encoding="utf-8")
        page_source = page_source[page_source.index("def render_benchmark_explorer"):]
        headings = (
            'st.subheader("Choose a benchmark")',
            'st.markdown(f"### {detail.benchmark_name}")',
            '_render_inline_curator_workflow(service, comparison, analyze_company)',
            'st.expander("RCE evaluation details", expanded=False',
            'st.markdown("**Developer diagnostics**")',
        )
        positions = [page_source.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))

    def test_primary_curator_view_uses_compact_table_legends(self):
        page_source = PAGE.read_text(encoding="utf-8")
        workflow = page_source[page_source.index("def _render_curator_panel"):
                               page_source.index("def render_benchmark_explorer")]
        self.assertNotIn('st.subheader("Benchmark health")', page_source)
        self.assertNotIn("**Legend:**", workflow)
        self.assertNotIn("st.metric(", workflow)
        self.assertIn(":green[■] Both corpora", workflow)
        self.assertIn(":red[■] This corpus only", workflow)
        self.assertIn(":yellow[■] Identity requires review", workflow)
        self.assertIn(":material/check_box: Included in Benchmark of Record", workflow)
        self.assertIn('row.comparison_outcome == "identity_review"', workflow)

    def test_investigation_actions_are_read_only_placeholders(self):
        page_source = PAGE.read_text(encoding="utf-8")
        for label in ("Compare", "Launch analysis", "Consider for benchmark"):
            self.assertIn(f'"{label}"', page_source)
        self.assertGreaterEqual(page_source.count("disabled=True"), 3)
        self.assertNotIn("st.data_editor", page_source)

    def test_reference_diagnostics_and_metric_details_are_collapsed(self):
        page_source = PAGE.read_text(encoding="utf-8")
        self.assertIn('st.expander("RCE evaluation details", expanded=False', page_source)
        evaluation = page_source[page_source.index('st.expander("RCE evaluation details", expanded=False'):]
        self.assertIn('st.markdown("**Developer diagnostics**")', evaluation)
        self.assertNotIn('st.expander("Developer diagnostics"', page_source)
        self.assertIn("st.progress", page_source)

    def test_rationale_and_evidence_wording_is_limited_to_recorded_indicators(self):
        page_source = PAGE.read_text(encoding="utf-8")
        self.assertIn("Rationale field present", page_source)
        self.assertIn("Structured evidence field present", page_source)
        self.assertIn("certified evaluator may record completeness indicators", COMPLETENESS_LIMITATION)
        self.assertNotIn('"Available" if row.rationale_present', page_source)

    def test_changed_files_have_no_visible_mojibake(self):
        corrupt_fragments = tuple(chr(codepoint) for codepoint in (0x00E2, 0x00C2, 0x00C3)) + (
            chr(0x00F0) + chr(0x0178),
        )
        for path in CHANGED_FILES:
            text = path.read_text(encoding="utf-8")
            self.assertFalse(any(fragment in text for fragment in corrupt_fragments), path)

    def test_representative_fixture_fields_map_across_two_domains(self):
        networking = self.service.get_benchmark("ai-data-center-networking-cabling").reviewed
        glp1 = self.service.get_benchmark("glp1-obesity-drug-supply-chain").reviewed
        self.assertEqual(networking.description, "QA reference for research-map coverage in ai data-center networking and cabling.")
        self.assertIn("canonical repository PDF", networking.review_notes)
        self.assertEqual(networking.expected_candidates[0]["expectation"], "must_include")
        self.assertEqual(networking.expected_candidates[0]["category_name"], "Networking silicon")
        self.assertEqual(networking.expected_candidates[0]["importance"], 5)
        self.assertEqual(networking.expected_candidates[0]["role_summary"], "Reference entity for networking silicon.")
        self.assertIn("page 1", networking.expected_candidates[0]["evidence_summary"])
        self.assertIn("benchmark rubric", networking.expected_candidates[0]["notes"])
        self.assertEqual(glp1.expected_candidates[0]["company_name"], "Novo Nordisk")
        self.assertEqual(glp1.expected_candidates[0]["role_summary"], "Semaglutide market leader")
        self.assertTrue(glp1.caveats)
        self.assertEqual(glp1.sources[0]["source_document"], "glp1 supply chain companies.pdf")
        self.assertEqual(glp1.sources[0]["source_page"], "1-3")
        self.assertTrue(glp1.sources[0]["source_hash"])

    def test_missing_baseline_is_graceful(self):
        service = RCEBenchmarkExplorerService(baseline_path="missing-certified-baseline.json")
        summary = service.run_summary()
        self.assertFalse(summary.available)
        self.assertEqual(summary.domain_count, 0)
        self.assertIn("missing", summary.error_message.casefold())
        self.assertIsNone(service.get_benchmark("anything"))

    def test_missing_database_falls_back_to_baseline_review_queue(self):
        service = RCEBenchmarkExplorerService(database_path="missing-benchmark.sqlite")
        self.assertEqual(len(service.review_queue()), service.run_summary().unresolved_review_count)
        self.assertFalse(Path("missing-benchmark.sqlite").exists())

    @pytest.mark.authoritative_rce_evidence
    def test_reads_are_immutable_and_leave_authoritative_files_unchanged(self):
        protected = [BASELINE, CONFIG, DATABASE, *sorted(FIXTURES.glob("*.json"))]
        before = {path: digest(path) for path in protected}
        summary = self.service.run_summary()
        detail = self.service.get_benchmark(summary.domains[0].benchmark_id)
        self.service.review_queue()
        with self.assertRaises((AttributeError, TypeError)):
            detail.reviewed.expected_candidates[0]["company_name"] = "changed"
        self.assertEqual(before, {path: digest(path) for path in protected})

    @pytest.mark.authoritative_rce_evidence
    def test_authoritative_hashes_and_database_row_counts(self):
        self.assertEqual({path: digest(path) for path in AUTHORITATIVE_HASHES}, AUTHORITATIVE_HASHES)
        self.assertEqual(fixture_digest(), "ea10ad04366efd780447a868cd579ff35fc07b896c83740c6655383567cd350f")
        connection = sqlite3.connect(f"file:{DATABASE.resolve()}?mode=ro", uri=True)
        try:
            expected_counts = {
                "rce_benchmark": 17,
                "rce_benchmark_candidate_result": 756,
                "rce_benchmark_category": 77,
                "rce_benchmark_category_result": 157,
                "rce_benchmark_human_review": 0,
                "rce_benchmark_metric": 350,
                "rce_benchmark_review_audit": 0,
                "rce_benchmark_run": 35,
                "rce_benchmark_security": 107,
                "rce_benchmark_source": 17,
            }
            actual = {
                table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                for table in expected_counts
            }
        finally:
            connection.close()
        self.assertEqual(actual, expected_counts)

    def test_null_cost_and_missing_fixture_are_graceful(self):
        runs = json.loads(BASELINE.read_text(encoding="utf-8"))
        runs[0]["estimated_cost"] = None
        with tempfile.TemporaryDirectory() as directory:
            baseline = Path(directory) / "baseline.json"
            baseline.write_text(json.dumps(runs), encoding="utf-8")
            service = RCEBenchmarkExplorerService(baseline_path=baseline, fixture_dir=Path(directory) / "fixtures")
            detail = service.get_benchmark(runs[0]["benchmark_id"])
        self.assertIsNone(detail.reviewed)

    def test_category_comparison_uses_recorded_evaluator_fields(self):
        detail = self.service.get_benchmark("ai-data-center-networking-cabling")
        self.assertTrue(detail.categories)
        self.assertTrue(all(isinstance(row.returned, bool) for row in detail.categories))
        candidate = detail.candidates_in_group("expected_returned")[0]
        self.assertEqual(candidate.category_match, candidate.expected_category == candidate.returned_category)

    def test_credo_has_honest_authored_only_company_investigation(self):
        investigation = self.service.company_investigation(
            "ai-data-center-networking-cabling", "ticker:CRDO",
            originating_side="Authored Source Corpus",
        )
        self.assertEqual(investigation.company_name, "Credo Technology")
        self.assertEqual(investigation.ticker_or_identifier, "CRDO")
        self.assertEqual(investigation.comparison_status, "Authored source only")
        self.assertTrue(investigation.appears_in_authored_corpus)
        self.assertFalse(investigation.appears_in_rce_corpus)
        self.assertEqual(investigation.source_evidence[0].source_page, "2")
        self.assertIsNone(investigation.rce_candidate)
        self.assertEqual(
            investigation.explanation,
            "Not returned in the stored RCE candidate corpus. "
            "The current artifact does not establish why it was omitted.",
        )

    def test_agreement_and_rce_discovery_investigation_models(self):
        agreement = self.service.company_investigation(
            "ai-data-center-networking-cabling", "ticker:ANET",
            originating_side="RCE Candidate Corpus",
        )
        discovery = self.service.company_investigation(
            "ai-data-center-networking-cabling", "name:ambarellainc",
            originating_side="RCE Candidate Corpus",
        )
        self.assertEqual(agreement.comparison_status, "Appears in both corpora")
        self.assertEqual(agreement.matching_method, "ticker/identifier")
        self.assertIsNotNone(agreement.rce_candidate)
        self.assertEqual(discovery.comparison_status, "RCE discovery")
        self.assertFalse(discovery.appears_in_authored_corpus)
        self.assertTrue(discovery.appears_in_rce_corpus)
        self.assertIsNotNone(discovery.rce_candidate)

    def test_inline_company_selection_and_narrative_metadata_are_presented(self):
        source = PAGE.read_text(encoding="utf-8")
        workflow = source[source.index("def _render_inline_curator_workflow"):]
        self.assertNotIn('"Company to investigate"', workflow)
        self.assertIn('on_select="rerun"', source)
        self.assertIn('f"#### Why is {investigation.company_name} here?"', source)
        self.assertIn('f"#### Why did RCE surface {investigation.company_name}?"', source)
        self.assertNotIn("Present in authored source corpus", workflow)
        self.assertNotIn("Matching method", workflow)

    def test_analyze_company_reuses_existing_sam_entry_and_retains_benchmark_state(self):
        page_source = PAGE.read_text(encoding="utf-8")
        app_source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn('"Analyze Company"', page_source)
        self.assertIn('request_navigation("Company Analysis")', app_source)
        self.assertIn("benchmark_pending_sam_ticker = canonical", app_source)
        self.assertIn('st.session_state.tam_tickers = [pending_ticker]', app_source)
        self.assertIn('key="benchmark_curator_domain"', page_source)
        self.assertIn("has no stored SAM observation", app_source)

    def test_similar_company_and_benchmark_mutation_actions_remain_disabled(self):
        source = PAGE.read_text(encoding="utf-8")
        position = source.index('"Compare Similar Companies"')
        self.assertIn("disabled=True", source[position:position + 180])
        for label in (
            "Consider for Benchmark", "Create benchmark proposal",
            "Approve benchmark change", "Reject benchmark change",
        ):
            self.assertNotIn(f'"{label}"', source)

    def test_agreements_automatically_enter_benchmark_of_record_without_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            service = RCEBenchmarkExplorerService(
                curator_approval_path=Path(directory) / "approvals.json",
            )
            members = service.benchmark_of_record("ai-data-center-networking-cabling")
        by_ticker = {row.ticker_or_identifier: row for row in members}
        self.assertEqual(by_ticker["ANET"].inclusion_source, "Agreement")
        self.assertNotIn("CRDO", by_ticker)

    def test_authored_only_and_rce_discovery_can_be_approved_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            approval_path = Path(directory) / "approvals.json"
            service = RCEBenchmarkExplorerService(curator_approval_path=approval_path)
            self.assertTrue(service.approve_for_benchmark_of_record(
                "ai-data-center-networking-cabling", "ticker:CRDO",
            ))
            self.assertFalse(service.approve_for_benchmark_of_record(
                "ai-data-center-networking-cabling", "ticker:CRDO",
            ))
            self.assertTrue(service.approve_for_benchmark_of_record(
                "ai-data-center-networking-cabling", "name:ambarellainc",
            ))
            members = service.benchmark_of_record("ai-data-center-networking-cabling")
            document = json.loads(approval_path.read_text(encoding="utf-8"))
        by_ticker = {row.ticker_or_identifier: row for row in members}
        self.assertEqual(by_ticker["CRDO"].inclusion_source, "Curator approval")
        self.assertEqual(by_ticker["AMBA"].inclusion_source, "Curator approval")
        self.assertEqual(len(document["approvals"]), 2)

    def test_agreement_cannot_be_manually_approved(self):
        with tempfile.TemporaryDirectory() as directory:
            service = RCEBenchmarkExplorerService(
                curator_approval_path=Path(directory) / "approvals.json",
            )
            with self.assertRaises(ValueError):
                service.approve_for_benchmark_of_record(
                    "ai-data-center-networking-cabling", "ticker:ANET",
                )

    def test_sprint_three_ui_has_two_click_confirmation_and_read_only_bor(self):
        source = PAGE.read_text(encoding="utf-8")
        self.assertIn('@st.dialog("Add to Benchmark of Record?"', source)
        self.assertIn('"Add to Benchmark of Record"', source)
        self.assertIn('"Confirm addition"', source)
        self.assertIn("Included automatically in the Benchmark of Record by corpus agreement.", source)
        self.assertIn('st.expander("View Benchmark of Record", expanded=False', source)
        self.assertIn('"Inclusion origin": member.inclusion_source', source)
        self.assertNotIn("st.data_editor", source)

    def test_sprint_four_curator_rows_and_progress_update_after_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            service = RCEBenchmarkExplorerService(
                curator_approval_path=Path(directory) / "approvals.json",
            )
            before = service.curator_progress("ai-data-center-networking-cabling")
            rows = service.curator_rows("ai-data-center-networking-cabling", "authored")
            agreement = next(row for row in rows if row.ticker == "ANET")
            pending = next(row for row in rows if row.ticker == "GLW")
            self.assertTrue(agreement.included)
            self.assertFalse(pending.included)
            service.approve_for_benchmark_of_record(
                "ai-data-center-networking-cabling", pending.matching_key,
            )
            after = service.curator_progress("ai-data-center-networking-cabling")
            refreshed = {row.ticker: row for row in service.curator_rows(
                "ai-data-center-networking-cabling", "authored",
            )}
        self.assertTrue(refreshed["GLW"].included)
        self.assertEqual(after.curator_additions, before.curator_additions + 1)
        self.assertEqual(after.pending_authored_only, before.pending_authored_only - 1)
        self.assertEqual(after.total_members, before.total_members + 1)

    def test_sprint_four_primary_tables_have_exact_columns_and_actions(self):
        source = PAGE.read_text(encoding="utf-8")
        workflow = source[source.index("def _render_inline_curator_detail"):]
        self.assertIn('{"Included": row.included, "Company": row.company_name,', workflow)
        self.assertIn('"Ticker": _display(row.ticker)', workflow)
        self.assertIn('({"Rank": row.rank} if side == "rce" else {})', workflow)
        self.assertIn('"Add to Benchmark of Record"', workflow)
        self.assertIn('"Analyze Company"', workflow)
        self.assertIn('"View Provenance"', source)
        self.assertNotIn('"Source page":', workflow)
        self.assertNotIn('"Status":', workflow)

if __name__ == "__main__":
    unittest.main()
