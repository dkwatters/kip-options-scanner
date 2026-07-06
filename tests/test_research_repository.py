import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app import evaluated_contract_export_rows, option_chain_rows, rule_evaluation_export_rows
from src.evaluation_profile import evaluation_profile_export_fields
from src.research_repository import (
    PostgresResearchRepository,
    REPOSITORY_BACKEND_POSTGRES,
    REPOSITORY_BACKEND_SQLITE,
    archive_opportunity_scan,
    archive_technical_observations,
    initialize_research_repository,
    latest_scan_row_counts,
    research_repository_target_from_env,
    research_repository_status,
    technical_analysis_observations,
)
from src.study_protocol import RUN_MODE_MANUAL_UI, RUN_MODE_SCHEDULED


def current_et_timestamp(time_label="10:00:00 AM") -> str:
    today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    return f"{today} {time_label} EDT"


def option_payload(symbol, option_type, delta, bid=8.0, ask=8.4, volume=750, open_interest=1500):
    return {
        "options": {
            "option": {
                "symbol": symbol,
                "root_symbol": symbol[:3],
                "strike": 600,
                "expiration_date": "2026-07-17",
                "option_type": option_type,
                "bid": bid,
                "ask": ask,
                "volume": volume,
                "open_interest": open_interest,
                "greeks": {"delta": delta, "mid_iv": 0.22},
            }
        }
    }


class FakePostgresCursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement, params=None):
        self.connection.executed.append((statement, params))

    def executemany(self, statement, rows):
        self.connection.executed_many.append((statement, list(rows)))


class FakePostgresConnection:
    def __init__(self):
        self.executed = []
        self.executed_many = []
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def cursor(self):
        return FakePostgresCursor(self)

    def commit(self):
        self.commits += 1


class FakePsycopg:
    def __init__(self):
        self.connections = []

    def connect(self, database_url):
        connection = FakePostgresConnection()
        connection.database_url = database_url
        self.connections.append(connection)
        return connection


class ResearchRepositoryTest(unittest.TestCase):
    def test_archive_persists_scan_rows_and_links_by_scan_id(self):
        rows = []
        rows.extend(
            option_chain_rows(
                option_payload("SPY260717C00600000", "call", 0.58),
                expiration="2026-07-17",
                today=date(2026, 6, 30),
                underlying_price=590,
                ticker="SPY",
            )
        )
        rows.extend(
            option_chain_rows(
                option_payload("QQQ260717C00600000", "call", 0.42),
                expiration="2026-07-17",
                today=date(2026, 6, 30),
                underlying_price=590,
                ticker="QQQ",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "opportunity_scans.sqlite"
            scan_timestamp = current_et_timestamp()
            contract_rows = evaluated_contract_export_rows(
                rows,
                "scan-1",
                scan_timestamp,
                "Test Universe",
                ["SPY", "QQQ"],
            )
            rule_rows = rule_evaluation_export_rows(rows, "scan-1")
            counts = archive_opportunity_scan(
                scan_id="scan-1",
                scan_timestamp=scan_timestamp,
                universe_name="Test Universe",
                option_type="Calls",
                dte_min=10,
                dte_max=45,
                evaluation_profile=evaluation_profile_export_fields(),
                evaluated_contract_rows=rows,
                contract_export_rows=contract_rows,
                rule_export_rows=rule_rows,
                study_protocol={
                    "study_id": "SP-001",
                    "study_name": "Intraday Technology Growth AI Calls",
                    "study_version": "v0.1",
                    "study_purpose": "Test purpose",
                    "scheduled_time_label": "10:00 ET",
                    "run_mode": RUN_MODE_SCHEDULED,
                },
                database_path=database_path,
            )

            self.assertEqual(
                counts,
                {
                    "opportunity_scans": 1,
                    "evaluated_contracts": 2,
                    "rule_evaluations": 8,
                    "security_characterization": 2,
                    "technical_characterization": 0,
                },
            )
            self.assertEqual(latest_scan_row_counts(database_path)["scan_id"], "scan-1")
            status = research_repository_status(database_path, study_id="SP-001")
            self.assertEqual(status.total_scans, 1)
            self.assertEqual(status.latest_scan_timestamp, scan_timestamp)
            self.assertEqual(status.latest_study_id, "SP-001")

            with closing(sqlite3.connect(database_path)) as connection:
                linked_counts = {
                    table: connection.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE scan_id = 'scan-1'"
                    ).fetchone()[0]
                    for table in (
                        "opportunity_scans",
                        "evaluated_contracts",
                        "rule_evaluations",
                        "security_characterization",
                        "technical_characterization",
                    )
                }
                self.assertEqual(linked_counts, counts)
                ticker = connection.execute(
                    """
                    SELECT ticker
                    FROM rule_evaluations
                    WHERE contract_symbol = 'SPY260717C00600000'
                    LIMIT 1
                    """
                ).fetchone()[0]
                self.assertEqual(ticker, "SPY")
                study_row = connection.execute(
                    """
                    SELECT study_id, study_name, study_version, study_purpose,
                           scheduled_time_label, run_mode
                    FROM opportunity_scans
                    WHERE scan_id = 'scan-1'
                    """
                ).fetchone()
                self.assertEqual(
                    study_row,
                    (
                        "SP-001",
                        "Intraday Technology Growth AI Calls",
                        "v0.1",
                        "Test purpose",
                        "10:00 ET",
                        RUN_MODE_SCHEDULED,
                    ),
                )
            self.assertEqual(status.today_completed_schedule_times, ("10:00",))

    def test_protocol_progress_excludes_manual_and_wrong_study_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "opportunity_scans.sqlite"
            for scan_id, study_id, run_mode, scheduled_time_label in (
                ("manual-scan", "SP-001", RUN_MODE_MANUAL_UI, "10:00"),
                ("wrong-study-scan", "SP-OTHER", RUN_MODE_SCHEDULED, "12:00"),
                ("scheduled-scan", "SP-001", RUN_MODE_SCHEDULED, "14:00 ET"),
            ):
                archive_opportunity_scan(
                    scan_id=scan_id,
                    scan_timestamp=current_et_timestamp(),
                    universe_name="Test Universe",
                    option_type="Calls",
                    dte_min=10,
                    dte_max=45,
                    evaluation_profile=evaluation_profile_export_fields(),
                    evaluated_contract_rows=[],
                    contract_export_rows=[],
                    rule_export_rows=[],
                    study_protocol={
                        "study_id": study_id,
                        "study_name": "Intraday Technology Growth AI Calls",
                        "study_version": "v0.1",
                        "study_purpose": "Test purpose",
                        "scheduled_time_label": scheduled_time_label,
                        "run_mode": run_mode,
                    },
                    database_path=database_path,
                )

            status = research_repository_status(database_path, study_id="SP-001")

            self.assertEqual(status.total_scans, 3)
            self.assertEqual(status.today_completed_schedule_times, ("14:00",))
            self.assertEqual(
                [row["run_mode"] for row in status.today_observations],
                [RUN_MODE_SCHEDULED, RUN_MODE_SCHEDULED, RUN_MODE_MANUAL_UI],
            )

    def test_run_mode_legacy_values_are_normalized_without_other_metadata_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "opportunity_scans.sqlite"
            initialize_research_repository(database_path)
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute(
                    """
                    INSERT INTO opportunity_scans (
                        scan_id, scan_timestamp, universe_name, run_mode, study_id
                    )
                    VALUES ('legacy-manual', '2026-07-01 10:00:00 AM EDT',
                            'Legacy Universe', 'manual', 'SP-001')
                    """
                )
                connection.execute(
                    """
                    INSERT INTO opportunity_scans (
                        scan_id, scan_timestamp, universe_name, run_mode, study_id
                    )
                    VALUES ('legacy-app', '2026-07-01 10:01:00 AM EDT',
                            'App Universe', 'app-triggered', 'SP-001')
                    """
                )
                connection.execute(
                    """
                    INSERT INTO opportunity_scans (
                        scan_id, scan_timestamp, universe_name, run_mode, study_id
                    )
                    VALUES ('missing-mode', '2026-07-01 10:02:00 AM EDT',
                            'Missing Mode Universe', NULL, 'SP-001')
                    """
                )
                connection.commit()

            initialize_research_repository(database_path)

            with closing(sqlite3.connect(database_path)) as connection:
                rows = connection.execute(
                    """
                    SELECT scan_id, universe_name, run_mode, study_id
                    FROM opportunity_scans
                    ORDER BY scan_id
                    """
                ).fetchall()

            self.assertEqual(
                rows,
                [
                    ("legacy-app", "App Universe", RUN_MODE_MANUAL_UI, "SP-001"),
                    ("legacy-manual", "Legacy Universe", RUN_MODE_MANUAL_UI, "SP-001"),
                    (
                        "missing-mode",
                        "Missing Mode Universe",
                        RUN_MODE_MANUAL_UI,
                        "SP-001",
                    ),
                ],
            )

    def test_archive_normalizes_legacy_run_mode_for_future_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "opportunity_scans.sqlite"
            archive_opportunity_scan(
                scan_id="legacy-future",
                scan_timestamp="2026-07-01 10:00:00 AM EDT",
                universe_name="Test Universe",
                option_type="Calls",
                dte_min=10,
                dte_max=45,
                evaluation_profile=evaluation_profile_export_fields(),
                evaluated_contract_rows=[],
                contract_export_rows=[],
                rule_export_rows=[],
                study_protocol={"run_mode": "app-triggered"},
                database_path=database_path,
            )

            with closing(sqlite3.connect(database_path)) as connection:
                run_modes = connection.execute(
                    "SELECT DISTINCT run_mode FROM opportunity_scans"
                ).fetchall()

            self.assertEqual(run_modes, [(RUN_MODE_MANUAL_UI,)])

    def test_startup_migrates_older_sqlite_schema_missing_study_protocol_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "opportunity_scans.sqlite"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE opportunity_scans (
                        scan_id TEXT PRIMARY KEY,
                        scan_timestamp TEXT,
                        universe_name TEXT,
                        evaluation_profile_name TEXT,
                        evaluation_profile_version TEXT,
                        contract_quality_model_name TEXT,
                        contract_quality_model_version TEXT,
                        option_type TEXT,
                        dte_min INTEGER,
                        dte_max INTEGER,
                        contracts_evaluated INTEGER,
                        passing_count INTEGER,
                        true_near_miss_count INTEGER,
                        rejected_count INTEGER,
                        average_quality_score REAL,
                        median_quality_score REAL,
                        highest_quality_score REAL,
                        lowest_quality_score REAL
                    );
                    CREATE TABLE technical_characterization (
                        scan_id TEXT,
                        ticker TEXT,
                        technical_timestamp TEXT,
                        price REAL,
                        sma_20 REAL,
                        sma_50 REAL,
                        sma_200 REAL,
                        price_vs_sma_20 REAL,
                        price_vs_sma_50 REAL,
                        price_vs_sma_200 REAL,
                        sma_20_vs_sma_50 REAL,
                        sma_50_vs_sma_200 REAL,
                        rsi_14 REAL,
                        macd_line REAL,
                        macd_signal REAL,
                        macd_histogram REAL,
                        realized_volatility_20d REAL,
                        trend_state TEXT,
                        momentum_state TEXT,
                        volatility_state TEXT,
                        technical_score REAL,
                        technical_notes TEXT
                    );
                    INSERT INTO opportunity_scans (
                        scan_id, scan_timestamp, universe_name
                    )
                    VALUES ('legacy-scan', '2026-07-01 10:00:00 AM EDT',
                            'Legacy Universe');
                    """
                )
                connection.commit()

            first_status = research_repository_status(database_path, study_id="SP-001")
            second_status = research_repository_status(database_path, study_id="SP-001")

            self.assertEqual(first_status.total_scans, 1)
            self.assertEqual(first_status.latest_scan_id, "legacy-scan")
            self.assertEqual(first_status.latest_study_id, None)
            self.assertEqual(first_status.latest_run_mode, RUN_MODE_MANUAL_UI)
            self.assertEqual(second_status.total_scans, 1)

            with closing(sqlite3.connect(database_path)) as connection:
                opportunity_columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(opportunity_scans)")
                }
                technical_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(technical_characterization)")
                }
                study_index = connection.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'index'
                      AND name = 'idx_technical_characterization_study'
                    """
                ).fetchone()

            expected_columns = {
                "study_id",
                "study_name",
                "study_version",
                "study_purpose",
                "scheduled_time_label",
                "run_mode",
            }
            self.assertTrue(expected_columns.issubset(opportunity_columns))
            self.assertTrue(expected_columns.issubset(technical_columns))
            self.assertEqual(study_index, ("idx_technical_characterization_study",))

    def test_technical_rows_persist_without_changing_contract_quality_results(self):
        rows = option_chain_rows(
            option_payload("SPY260717C00600000", "call", 0.58),
            expiration="2026-07-17",
            today=date(2026, 6, 30),
            underlying_price=590,
            ticker="SPY",
        )
        original_quality_score = rows[0]["Quality Score"]
        scan_timestamp = current_et_timestamp()
        contract_rows = evaluated_contract_export_rows(
            rows,
            "scan-with-tam",
            scan_timestamp,
            "Test Universe",
            ["SPY"],
        )
        rule_rows = rule_evaluation_export_rows(rows, "scan-with-tam")
        technical_rows = [
            {
                "scan_id": "scan-with-tam",
                "ticker": "SPY",
                "technical_timestamp": scan_timestamp,
                "price": 590,
                "sma_20": 580,
                "sma_50": 570,
                "sma_200": 540,
                "price_vs_sma_20": 0.0172,
                "price_vs_sma_50": 0.0351,
                "price_vs_sma_200": 0.0926,
                "sma_20_vs_sma_50": 0.0175,
                "sma_50_vs_sma_200": 0.0556,
                "rsi_14": 61.5,
                "macd_line": 2.4,
                "macd_signal": 1.9,
                "macd_histogram": 0.5,
                "realized_volatility_20d": 0.22,
                "trend_state": "bullish_alignment",
                "momentum_state": "positive",
                "volatility_state": "low",
                "technical_score": None,
                "technical_notes": "test TAM row",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "opportunity_scans.sqlite"
            counts = archive_opportunity_scan(
                scan_id="scan-with-tam",
                scan_timestamp=scan_timestamp,
                universe_name="Test Universe",
                option_type="Calls",
                dte_min=10,
                dte_max=45,
                evaluation_profile=evaluation_profile_export_fields(),
                evaluated_contract_rows=rows,
                contract_export_rows=contract_rows,
                rule_export_rows=rule_rows,
                technical_rows=technical_rows,
                database_path=database_path,
            )

            with closing(sqlite3.connect(database_path)) as connection:
                persisted_quality_score = connection.execute(
                    """
                    SELECT quality_score
                    FROM evaluated_contracts
                    WHERE scan_id = 'scan-with-tam'
                    """
                ).fetchone()[0]
                technical_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM technical_characterization
                    WHERE scan_id = 'scan-with-tam'
                    """
                ).fetchone()[0]

        self.assertEqual(counts["technical_characterization"], 1)
        self.assertEqual(technical_count, 1)
        self.assertEqual(persisted_quality_score, original_quality_score)

    def test_technical_analysis_observations_filter_latest_scan_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "opportunity_scans.sqlite"
            initialize_research_repository(database_path)
            with closing(sqlite3.connect(database_path)) as connection:
                connection.executemany(
                    """
                    INSERT INTO technical_characterization (
                        scan_id, ticker, technical_timestamp, price, sma_20,
                        sma_50, sma_200, rsi_14, macd_line, macd_signal,
                        macd_histogram, trend_state, momentum_state,
                        volatility_state, technical_score, technical_notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            "scan-old",
                            "MSFT",
                            "2026-07-06 09:30:00 AM EDT",
                            500,
                            495,
                            490,
                            450,
                            52,
                            1.1,
                            1.0,
                            0.1,
                            "neutral_mixed",
                            "flat",
                            "normal",
                            None,
                            None,
                        ),
                        (
                            "scan-latest",
                            "AAPL",
                            "2026-07-06 10:00:00 AM EDT",
                            210,
                            205,
                            200,
                            190,
                            64,
                            1.4,
                            1.1,
                            0.3,
                            "bullish_alignment",
                            "positive",
                            "low",
                            78,
                            "qa row",
                        ),
                    ],
                )
                connection.commit()

            latest = technical_analysis_observations(database_path=database_path)
            filtered = technical_analysis_observations(
                database_path=database_path,
                tickers=["aapl"],
                trend_states=["bullish_alignment"],
                latest_scan_only=False,
            )

        self.assertEqual(latest["selected_scan_id"], "scan-latest")
        self.assertEqual([row["ticker"] for row in latest["rows"]], ["AAPL"])
        self.assertEqual(filtered["available_tickers"], ("AAPL", "MSFT"))
        self.assertEqual(len(filtered["rows"]), 1)
        self.assertEqual(filtered["rows"][0]["technical_score"], 78)

    def test_archive_technical_observations_persists_tam_only_metadata(self):
        technical_rows = [
            {
                "scan_id": "tam-scan-1",
                "ticker": "SPY",
                "technical_timestamp": "2026-07-06 04:30:00 PM EDT",
                "price": 590,
                "sma_20": 580,
                "sma_50": 570,
                "sma_200": 540,
                "trend_state": "bullish_alignment",
                "momentum_state": "positive",
                "volatility_state": "low",
                "technical_score": None,
                "technical_notes": "test TAM-only row",
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "opportunity_scans.sqlite"
            counts = archive_technical_observations(
                scan_id="tam-scan-1",
                technical_rows=technical_rows,
                study_protocol={
                    "study_id": "TAM-001",
                    "study_name": "Daily Technical Characterization",
                    "study_version": "v0.1",
                    "study_purpose": "Collect daily stock-level technical observations.",
                    "scheduled_time_label": "16:30 ET",
                    "run_mode": RUN_MODE_SCHEDULED,
                },
                database_path=database_path,
            )
            observations = technical_analysis_observations(
                database_path=database_path,
                tickers=["SPY"],
                study_ids=["TAM-001"],
                run_modes=[RUN_MODE_SCHEDULED],
                scheduled_time_labels=["16:30 ET"],
                technical_timestamps=["2026-07-06 04:30:00 PM EDT"],
                latest_scan_only=False,
            )
            with closing(sqlite3.connect(database_path)) as connection:
                opportunity_count = connection.execute(
                    "SELECT COUNT(*) FROM opportunity_scans"
                ).fetchone()[0]
                contract_count = connection.execute(
                    "SELECT COUNT(*) FROM evaluated_contracts"
                ).fetchone()[0]

        self.assertEqual(
            counts,
            {
                "opportunity_scans": 0,
                "evaluated_contracts": 0,
                "rule_evaluations": 0,
                "security_characterization": 0,
                "technical_characterization": 1,
            },
        )
        self.assertEqual(opportunity_count, 0)
        self.assertEqual(contract_count, 0)
        self.assertEqual(len(observations["rows"]), 1)
        self.assertEqual(observations["rows"][0]["study_id"], "TAM-001")
        self.assertEqual(observations["rows"][0]["run_mode"], RUN_MODE_SCHEDULED)
        self.assertEqual(observations["rows"][0]["scheduled_time_label"], "16:30 ET")

    def test_repository_target_defaults_to_sqlite(self):
        target = research_repository_target_from_env({})

        self.assertEqual(target.backend, REPOSITORY_BACKEND_SQLITE)
        self.assertEqual(target.display_location, "data\\research\\opportunity_scans.sqlite")

    def test_repository_target_uses_configured_sqlite_path(self):
        target = research_repository_target_from_env(
            {
                "RESEARCH_REPOSITORY_BACKEND": "sqlite",
                "RESEARCH_SQLITE_PATH": "tmp/research.sqlite",
            }
        )

        self.assertEqual(target.backend, REPOSITORY_BACKEND_SQLITE)
        self.assertEqual(str(target.sqlite_path), "tmp\\research.sqlite")

    def test_repository_target_validates_postgres_database_url(self):
        target = research_repository_target_from_env(
            {
                "RESEARCH_REPOSITORY_BACKEND": "postgres",
                "DATABASE_URL": "postgresql://user:pass@example.com:5432/research",
            }
        )

        self.assertEqual(target.backend, REPOSITORY_BACKEND_POSTGRES)
        self.assertEqual(
            target.display_location,
            "postgresql://user:pass@example.com:5432/research",
        )

    def test_repository_target_requires_database_url_for_postgres(self):
        with self.assertRaises(ValueError):
            research_repository_target_from_env({"RESEARCH_REPOSITORY_BACKEND": "postgres"})

    def test_postgres_repository_requires_database_url(self):
        with self.assertRaises(ValueError):
            PostgresResearchRepository("")

    def test_postgres_archive_uses_schema_and_equivalent_table_writes(self):
        rows = option_chain_rows(
            option_payload("SPY260717C00600000", "call", 0.58),
            expiration="2026-07-17",
            today=date(2026, 6, 30),
            underlying_price=590,
            ticker="SPY",
        )
        scan_timestamp = current_et_timestamp()
        contract_rows = evaluated_contract_export_rows(
            rows,
            "pg-scan-1",
            scan_timestamp,
            "Test Universe",
            ["SPY"],
        )
        rule_rows = rule_evaluation_export_rows(rows, "pg-scan-1")
        fake_psycopg = FakePsycopg()

        original_psycopg = sys.modules.get("psycopg")
        sys.modules["psycopg"] = fake_psycopg
        try:
            repository = PostgresResearchRepository(
                "postgresql://user:pass@example.com:5432/research"
            )
            counts = repository.archive_opportunity_scan(
                scan_id="pg-scan-1",
                scan_timestamp=scan_timestamp,
                universe_name="Test Universe",
                option_type="Calls",
                dte_min=10,
                dte_max=45,
                evaluation_profile=evaluation_profile_export_fields(),
                evaluated_contract_rows=rows,
                contract_export_rows=contract_rows,
                rule_export_rows=rule_rows,
                study_protocol={
                    "study_id": "SP-001",
                    "study_name": "Intraday Technology Growth AI Calls",
                    "study_version": "v0.1",
                    "study_purpose": "Test purpose",
                    "scheduled_time_label": "10:00 ET",
                    "run_mode": RUN_MODE_SCHEDULED,
                },
            )
        finally:
            if original_psycopg is None:
                sys.modules.pop("psycopg", None)
            else:
                sys.modules["psycopg"] = original_psycopg

        self.assertEqual(
            counts,
            {
                "opportunity_scans": 1,
                "evaluated_contracts": 1,
                "rule_evaluations": 4,
                "security_characterization": 1,
                "technical_characterization": 0,
            },
        )
        all_statements = "\n".join(
            statement
            for connection in fake_psycopg.connections
            for statement, _params in connection.executed
        )
        self.assertIn("CREATE TABLE IF NOT EXISTS opportunity_scans", all_statements)
        self.assertIn("CREATE TABLE IF NOT EXISTS evaluated_contracts", all_statements)
        self.assertIn("CREATE TABLE IF NOT EXISTS rule_evaluations", all_statements)
        self.assertIn("CREATE TABLE IF NOT EXISTS security_characterization", all_statements)
        self.assertIn("CREATE TABLE IF NOT EXISTS technical_characterization", all_statements)
        self.assertIn("ON CONFLICT (scan_id) DO UPDATE", all_statements)
        executemany_lengths = [
            len(rows)
            for connection in fake_psycopg.connections
            for _statement, rows in connection.executed_many
        ]
        self.assertEqual(executemany_lengths, [1, 4, 1, 0])


if __name__ == "__main__":
    unittest.main()
