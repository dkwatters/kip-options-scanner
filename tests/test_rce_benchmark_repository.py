import copy
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.rce_benchmark_repository import (
    BenchmarkValidationError,
    DuplicateBenchmarkError,
    import_fixture_directory,
    import_fixtures,
    load_fixture,
    load_fixture_directory,
)
from src.rce_benchmark_corpus import inventory_pdfs


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "rce_benchmarks"
FIXTURE_PATH = FIXTURE_DIR / "nuclear-power-ai-data-centers.json"


class RCEBenchmarkRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = load_fixture(FIXTURE_PATH)

    def test_valid_fixture_parsing(self):
        self.assertEqual(self.fixture["schema_version"], "1.0")
        self.assertEqual(
            self.fixture["benchmark"]["research_question"],
            "Which companies and reference entities matter when researching nuclear power supply for AI data centers?",
        )
        self.assertTrue(self.fixture["categories"])
        self.assertTrue(self.fixture["sources"])

    def test_duplicate_benchmark_version_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "benchmarks.sqlite"
            import_fixtures([self.fixture], database_path=database, apply=True)
            with self.assertRaises(DuplicateBenchmarkError):
                import_fixtures([self.fixture], database_path=database, apply=True)

    def test_transaction_rolls_back_all_fixture_writes(self):
        duplicate = copy.deepcopy(self.fixture)
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "benchmarks.sqlite"
            with self.assertRaises(DuplicateBenchmarkError):
                import_fixtures([self.fixture, duplicate], database_path=database, apply=True)
            with closing(sqlite3.connect(database)) as connection:
                count = connection.execute("SELECT COUNT(*) FROM rce_benchmark").fetchone()[0]
                category_count = connection.execute(
                    "SELECT COUNT(*) FROM rce_benchmark_category"
                ).fetchone()[0]
            self.assertEqual((count, category_count), (0, 0))

    def test_invalid_expectation_value(self):
        invalid = copy.deepcopy(self.fixture)
        invalid["securities"][0]["expectation"] = "probably_include"
        with self.assertRaisesRegex(BenchmarkValidationError, "expectation is invalid"):
            import_fixtures([invalid], database_path=Path("unused.sqlite"), apply=False)

    def test_private_international_and_fund_classification_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            report = import_fixtures(
                [self.fixture], database_path=Path(directory) / "benchmarks.sqlite", apply=False
            )
        classifications = "\n".join(report.special_references)
        self.assertIn("international_reference", classifications)
        self.assertIn("private_reference", classifications)
        self.assertIn("fund_reference", classifications)

    def test_dry_run_performs_no_row_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "benchmarks.sqlite"
            report = import_fixtures([self.fixture], database_path=database, apply=False)
        self.assertTrue(report.dry_run)
        self.assertFalse(database.exists())

    def test_source_provenance_retained(self):
        source = self.fixture["sources"][0]
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "benchmarks.sqlite"
            import_fixtures([self.fixture], database_path=database, apply=True)
            with closing(sqlite3.connect(database)) as connection:
                stored = connection.execute(
                    "SELECT source_document, source_section, source_notes, source_hash FROM rce_benchmark_source"
                ).fetchone()
        self.assertEqual(stored, (
            source["source_document"], source["source_section"],
            source["source_notes"], source["source_hash"],
        ))

    def test_duplicate_tickers_are_reported(self):
        duplicate_ticker = copy.deepcopy(self.fixture)
        duplicate_ticker["benchmark"]["benchmark_id"] = "nuclear-copy"
        duplicate_ticker["benchmark"]["version"] = "v0.2"
        with tempfile.TemporaryDirectory() as directory:
            report = import_fixtures(
                [self.fixture, duplicate_ticker],
                database_path=Path(directory) / "benchmarks.sqlite",
                apply=False,
            )
        self.assertIn("CEG", report.duplicate_tickers)

    def test_private_reference_with_stable_identifier_is_not_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            report = import_fixtures(
                [self.fixture], database_path=Path(directory) / "benchmarks.sqlite", apply=False
            )
        self.assertFalse(report.missing_security_identifiers)

    def test_private_reference_without_stable_identifier_is_reported(self):
        invalid = copy.deepcopy(self.fixture)
        private = next(
            row for row in invalid["securities"] if row["expectation"] == "private_reference"
        )
        private["ticker"] = None
        private["reference_identifier"] = None
        with tempfile.TemporaryDirectory() as directory:
            report = import_fixtures(
                [invalid], database_path=Path(directory) / "benchmarks.sqlite", apply=False
            )
        self.assertTrue(report.missing_security_identifiers)

    def test_public_security_without_ticker_is_reported(self):
        invalid = copy.deepcopy(self.fixture)
        invalid["securities"][0]["ticker"] = None
        with tempfile.TemporaryDirectory() as directory:
            report = import_fixtures(
                [invalid], database_path=Path(directory) / "benchmarks.sqlite", apply=False
            )
        self.assertTrue(report.missing_security_identifiers)

    def test_duplicate_source_document_detection(self):
        duplicate = copy.deepcopy(self.fixture)
        duplicate["benchmark"]["benchmark_id"] = "different-definition"
        with tempfile.TemporaryDirectory() as directory:
            fixture_dir = Path(directory)
            (fixture_dir / "one.json").write_text(json.dumps(self.fixture), encoding="utf-8")
            (fixture_dir / "two.json").write_text(json.dumps(duplicate), encoding="utf-8")
            with self.assertRaisesRegex(BenchmarkValidationError, "Duplicate source document"):
                load_fixture_directory(fixture_dir)

    def test_exactly_seventeen_unique_canonical_fixtures_parse(self):
        fixtures = load_fixture_directory(FIXTURE_DIR)
        self.assertEqual(len(fixtures), 17)
        identities = {(d["benchmark"]["benchmark_id"], d["benchmark"]["version"]) for d in fixtures}
        self.assertEqual(len(identities), 17)

    def test_apply_writes_all_four_entity_types(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "benchmarks.sqlite"
            report = import_fixture_directory(FIXTURE_DIR, database_path=database, apply=True)
            with closing(sqlite3.connect(database)) as connection:
                counts = {
                    table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in (
                        "rce_benchmark", "rce_benchmark_category",
                        "rce_benchmark_security", "rce_benchmark_source",
                    )
                }
        self.assertEqual(report.benchmarks, 17)
        self.assertEqual(counts["rce_benchmark"], 17)
        self.assertGreater(counts["rce_benchmark_category"], 17)
        self.assertGreater(counts["rce_benchmark_security"], 17)
        self.assertEqual(counts["rce_benchmark_source"], 17)

    def test_inventory_generation_hashes_and_canonical_selection(self):
        records, duplicates = inventory_pdfs(Path("docs/research/benchmarks"))
        self.assertEqual(len(records), 17)
        self.assertFalse(duplicates)
        self.assertTrue(all(r.canonical_source for r in records))
        self.assertTrue(all(len(r.sha256) == 64 for r in records))
        self.assertTrue(all(r.fixture_filename.endswith(".json") for r in records))

    def test_duplicate_pdf_detection(self):
        source = Path("docs/research/benchmarks/nuclear data center companies.pdf")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / source.name).write_bytes(source.read_bytes())
            (target / "copy.pdf").write_bytes(source.read_bytes())
            records, duplicates = inventory_pdfs(target)
        self.assertEqual(len(records), 2)
        self.assertEqual(duplicates[0]["status"], "exact")
        self.assertEqual(sum(r.canonical_source for r in records), 1)

    def test_five_new_domains_and_review_flags(self):
        fixtures = load_fixture_directory(FIXTURE_DIR)
        ids = {d["benchmark"]["benchmark_id"] for d in fixtures}
        self.assertTrue({"critical-infrastructure-cybersecurity", "fusion-energy",
                         "glp1-obesity-drug-supply-chain", "traditional-banking", "fintech"} <= ids)
        self.assertTrue(any("HUMAN REVIEW" in (s.get("notes") or "")
                            for d in fixtures for s in d["securities"]))

    def test_cross_benchmark_overlap_and_reference_types(self):
        fixtures = load_fixture_directory(FIXTURE_DIR)
        owners = {}
        expectations = set()
        for document in fixtures:
            for row in document["securities"]:
                expectations.add(row["expectation"])
                if row.get("ticker"):
                    owners.setdefault(row["ticker"], set()).add(document["benchmark"]["benchmark_id"])
        self.assertTrue({"traditional-banking", "fintech"} <= owners["AXP"])
        self.assertTrue({"traditional-banking", "fintech"} <= owners["COF"])
        self.assertTrue({"crypto-adjacent-companies", "fintech"} <= owners["HOOD"])
        self.assertTrue({"crypto-adjacent-companies", "fintech"} <= owners["PYPL"])
        self.assertTrue({"private_reference", "international_reference", "fund_reference"} <= expectations)


if __name__ == "__main__":
    unittest.main()
