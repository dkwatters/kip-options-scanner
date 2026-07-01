import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path

from app import evaluated_contract_export_rows, option_chain_rows, rule_evaluation_export_rows
from src.evaluation_profile import evaluation_profile_export_fields
from src.research_repository import (
    archive_opportunity_scan,
    latest_scan_row_counts,
    research_repository_status,
)


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
            contract_rows = evaluated_contract_export_rows(
                rows,
                "scan-1",
                "2026-07-01 10:00:00 AM EDT",
                "Test Universe",
                ["SPY", "QQQ"],
            )
            rule_rows = rule_evaluation_export_rows(rows, "scan-1")
            counts = archive_opportunity_scan(
                scan_id="scan-1",
                scan_timestamp="2026-07-01 10:00:00 AM EDT",
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
                    "run_mode": "manual",
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
                },
            )
            self.assertEqual(latest_scan_row_counts(database_path)["scan_id"], "scan-1")
            status = research_repository_status(database_path)
            self.assertEqual(status.total_scans, 1)
            self.assertEqual(status.latest_scan_timestamp, "2026-07-01 10:00:00 AM EDT")
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
                        "manual",
                    ),
                )


if __name__ == "__main__":
    unittest.main()
