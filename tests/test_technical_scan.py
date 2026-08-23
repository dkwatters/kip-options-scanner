import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.study_protocol import RUN_MODE_RESEARCH_SCRIPT, RUN_MODE_SCHEDULED
from technical_scan import run_tam_technical_scan


class FakeTamClient:
    def __init__(self):
        self.history_symbols = []
        self.quote_symbols = []
        self.option_chain_calls = []

    def get_price_history(self, symbol, start=None, end=None):
        self.history_symbols.append(symbol)
        end_day = date.fromisoformat(end)
        closes = [
            {
                "date": (end_day - timedelta(days=219 - index)).isoformat(),
                "close": 100 + index,
            }
            for index in range(220)
        ]
        return {"history": {"day": closes}}

    def get_quote(self, symbol):
        self.quote_symbols.append(symbol)
        return {"quotes": {"quote": {"last": 320.5}}}

    def get_option_expirations(self, symbol):
        raise AssertionError("TAM-only scan must not fetch option expirations")

    def get_option_chain(self, symbol, expiration):
        self.option_chain_calls.append((symbol, expiration))
        raise AssertionError("TAM-only scan must not fetch option chains")


class TechnicalScanTest(unittest.TestCase):
    def test_tam_only_scan_persists_technical_rows_without_options(self):
        client = FakeTamClient()
        with tempfile.TemporaryDirectory() as directory:
            database_path = str(Path(directory) / "tam.sqlite")
            env = {
                "RESEARCH_REPOSITORY_BACKEND": "sqlite",
                "RESEARCH_SQLITE_PATH": database_path,
            }
            with patch.dict(os.environ, env, clear=False):
                result = run_tam_technical_scan(
                    run_mode=RUN_MODE_RESEARCH_SCRIPT,
                    client=client,
                    scan_timestamp=datetime(
                        2026, 7, 6, 16, 30, tzinfo=ZoneInfo("America/New_York")
                    ),
                )

        self.assertFalse(result["skipped"])
        self.assertEqual(result["row_counts"]["opportunity_scans"], 0)
        self.assertEqual(result["row_counts"]["evaluated_contracts"], 0)
        self.assertGreater(result["row_counts"]["technical_characterization"], 0)
        self.assertEqual(result["technical_error_count"], 0)
        self.assertEqual(client.option_chain_calls, [])
        self.assertEqual(client.quote_symbols, [])

    def test_scheduled_tam_scan_skips_closed_market_before_client_calls(self):
        client = FakeTamClient()
        result = run_tam_technical_scan(
            run_mode=RUN_MODE_SCHEDULED,
            scheduled_time_label="16:30 ET",
            client=client,
            scan_timestamp=datetime(
                2026, 7, 4, 16, 30, tzinfo=ZoneInfo("America/New_York")
            ),
        )

        self.assertTrue(result["skipped"])
        self.assertIn("closed", result["skip_reason"])
        self.assertEqual(client.history_symbols, [])
        self.assertEqual(client.quote_symbols, [])


if __name__ == "__main__":
    unittest.main()
