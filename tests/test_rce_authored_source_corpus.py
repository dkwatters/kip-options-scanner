import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import pytest

from scripts.build_rce_authored_source_corpus import build
from src.rce_benchmark_explorer_service import (
    AuthoredSourceCandidate,
    RCEBenchmarkExplorerService,
    RCECorpusCandidate,
    compare_corpora,
)

ARTIFACT = Path("data/research/rce_authored_source_corpus_v0.1.json")
BASELINE = Path("data/research/rce_benchmark_baseline_v0.1.1.json")
FIXTURES = Path("tests/fixtures/rce_benchmarks")
PDFS = Path("docs/research/benchmarks")
CONFIG = Path("config/rce_benchmark_scoring_v0.1.json")
DATABASE = Path("data/research/rce_benchmarks.sqlite")
PAGE = Path("src/rce_benchmark_explorer_page.py")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authored(name, ticker, category="Category A"):
    return AuthoredSourceCandidate(
        "test", "Test", "v1", "test.pdf", "1", category, name, ticker,
        "primary company-table constituent", None, False, 1,
    )


def rce(name, ticker, category="Category A", rank=1):
    return RCECorpusCandidate(name, ticker, rank, category, "valid", True, True)


class AuthoredSourceCorpusTests(unittest.TestCase):
    def setUp(self):
        self.service = RCEBenchmarkExplorerService()

    def test_offline_build_reconciles_all_audited_totals(self):
        document = build()
        self.assertEqual(document["benchmark_count"], 17)
        self.assertEqual(document["primary_unique_company_count"], 377)
        self.assertEqual(document["primary_placement_count"], 381)
        stored = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        self.assertEqual(document, stored)
        record_types = {
            record["record_type"]
            for benchmark in stored["benchmarks"] for record in benchmark["records"]
        }
        self.assertTrue({
            "primary company-table constituent", "prose-only reference",
            "private-company reference", "fund or ETF",
            "categories-worth-adding example", "distressed/boundary case",
        } <= record_types)

    def test_known_repeated_placements_are_preserved(self):
        expected = {
            "ai-power-supply-chain": (39, 41),
            "retail-sector": (31, 32),
            "semiconductor-packaging": (24, 25),
        }
        document = json.loads(ARTIFACT.read_text(encoding="utf-8"))
        actual = {
            row["benchmark_id"]: (row["primary_unique_company_count"], row["primary_placement_count"])
            for row in document["benchmarks"] if row["benchmark_id"] in expected
        }
        self.assertEqual(actual, expected)
        self.assertTrue(any(
            record["duplicate_placement"]
            for benchmark in document["benchmarks"]
            for record in benchmark["records"]
        ))

    def test_selected_domains_use_source_corpus_not_fixture_projection(self):
        power = self.service.corpus_comparison("ai-power-supply-chain")
        networking = self.service.corpus_comparison("ai-data-center-networking-cabling")
        self.assertEqual((power.authored_unique_count, power.authored_placement_count), (39, 41))
        self.assertEqual((networking.authored_unique_count, networking.authored_placement_count), (17, 17))
        self.assertIn("GE Vernova", {row.company_name for row in power.authored_candidates})
        self.assertEqual(len(self.service.get_benchmark("ai-power-supply-chain").reviewed.constituents), 4)

    def test_rce_candidate_counts_reconcile_to_returned_certified_rows(self):
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        runs = {row["benchmark_id"]: row for row in baseline if row.get("run_label") == "baseline-v0.1-providerfix"}
        for benchmark_id, run in runs.items():
            expected = sum(bool(row.get("returned")) for row in run["evaluation"]["candidate_results"])
            self.assertEqual(len(self.service.rce_corpus_candidates(benchmark_id)), expected)
            self.assertEqual(self.service.corpus_comparison(benchmark_id).rce_candidate_count, expected)

    def test_deterministic_matching_outcomes(self):
        self.assertEqual(compare_corpora((authored("Acme", "ACME"),), (rce("Acme", "ACME"),))[0].comparison_outcome, "agreement")
        outcomes = {row.comparison_outcome for row in compare_corpora(
            (authored("Authored Co", "AUTH"),), (rce("Novel Co", "NEW"),)
        )}
        self.assertEqual(outcomes, {"authored_only", "rce_only"})
        category_difference = compare_corpora(
            (authored("Acme", "ACME", "Original"),), (rce("Acme", "ACME", "Returned"),)
        )[0]
        self.assertEqual(category_difference.comparison_outcome, "agreement")
        self.assertFalse(category_difference.category_match)
        ambiguous = compare_corpora(
            (authored("First", "DUP"), authored("Second", "DUP")),
            (rce("Unknown", "DUP"),),
        )
        self.assertIn("identity_review", {row.comparison_outcome for row in ambiguous})

    def test_status_colors_also_have_accessible_text(self):
        source = PAGE.read_text(encoding="utf-8")
        for text in (
            "Agreement - present in both corpora",
            "Authored only - not returned by RCE",
            "RCE discovery not present in the authored source corpus",
            "Identity review - ambiguous deterministic match",
        ):
            self.assertIn(text, source)
        self.assertIn("background-color", source)

    def test_missing_source_corpus_and_missing_run_are_graceful(self):
        missing_source = RCEBenchmarkExplorerService(source_corpus_path="missing-source-corpus.json")
        result = missing_source.corpus_comparison("ai-power-supply-chain")
        self.assertFalse(result.available)
        self.assertIn("source corpus", result.error_message.casefold())
        with tempfile.TemporaryDirectory() as directory:
            baseline = Path(directory) / "baseline.json"
            baseline.write_text("[]", encoding="utf-8")
            missing_run = RCEBenchmarkExplorerService(baseline_path=baseline)
            result = missing_run.corpus_comparison("ai-power-supply-chain")
        self.assertFalse(result.available)
        self.assertIn("rce result", result.error_message.casefold())

    @pytest.mark.authoritative_rce_evidence
    def test_read_only_comparison_leaves_authoritative_inputs_unchanged(self):
        protected = [
            BASELINE, CONFIG, DATABASE, ARTIFACT,
            *sorted(FIXTURES.glob("*.json")), *sorted(PDFS.glob("*.pdf")),
        ]
        before = {path: digest(path) for path in protected}
        for domain in self.service.list_domains():
            self.service.corpus_comparison(domain.benchmark_id)
        self.assertEqual(before, {path: digest(path) for path in protected})


if __name__ == "__main__":
    unittest.main()
