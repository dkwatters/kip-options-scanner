import unittest
from datetime import date

from app import (
    evaluated_contract_export_rows,
    option_chain_rows,
    validate_evaluated_contract_tickers,
)


def option_payload(root_symbol="SPY"):
    return {
        "options": {
            "option": {
                "symbol": "SPY260717C00600000",
                "root_symbol": root_symbol,
                "strike": 600,
                "expiration_date": "2026-07-17",
                "option_type": "call",
                "bid": 8.0,
                "ask": 8.4,
                "volume": 750,
                "open_interest": 1500,
                "greeks": {"delta": 0.58, "mid_iv": 0.22},
            }
        }
    }


class EvaluatedContractExportTest(unittest.TestCase):
    def test_chain_rows_and_export_include_underlying_ticker(self):
        rows = option_chain_rows(
            option_payload(),
            expiration="2026-07-17",
            today=date(2026, 6, 30),
            underlying_price=590,
            ticker="SPY",
        )

        self.assertEqual(rows[0]["Ticker"], "SPY")
        self.assertEqual(rows[0]["Underlying Symbol"], "SPY")

        export_rows = evaluated_contract_export_rows(
            rows,
            scan_id="scan-1",
            scan_timestamp="2026-06-30T12:00:00Z",
            universe_name="Default",
        )

        self.assertEqual(export_rows[0]["ticker"], "SPY")
        self.assertEqual(export_rows[0]["contract_symbol"], "SPY260717C00600000")

    def test_validation_rejects_blank_ticker(self):
        with self.assertRaisesRegex(ValueError, "blank ticker"):
            validate_evaluated_contract_tickers(
                [{"Ticker": "-", "Underlying Symbol": "SPY", "Symbol": "SPY260717C00600000"}]
            )

    def test_validation_allows_adjusted_occ_root_symbol(self):
        validate_evaluated_contract_tickers(
            [
                {
                    "Ticker": "PANW",
                    "Underlying Symbol": "PANW1",
                    "Symbol": "PANW1260717C00250000",
                }
            ],
            active_universe_symbols=["PANW"],
        )

    def test_validation_rejects_ticker_outside_active_universe(self):
        with self.assertRaisesRegex(ValueError, "not in the active universe"):
            validate_evaluated_contract_tickers(
                [
                    {
                        "Ticker": "QQQ",
                        "Underlying Symbol": "SPY",
                        "Symbol": "QQQ260717C00600000",
                    }
                ],
                active_universe_symbols=["SPY"],
            )


if __name__ == "__main__":
    unittest.main()
