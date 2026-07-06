import unittest

from src.technical_analysis import (
    characterize_technical_condition,
    closing_prices_from_history_payload,
    last_price_from_quote_payload,
    realized_volatility,
    relative_strength_index,
    simple_moving_average,
)


class TechnicalAnalysisTest(unittest.TestCase):
    def test_closing_prices_from_tradier_history_payload(self):
        payload = {
            "history": {
                "day": [
                    {"date": "2026-01-02", "close": "100.5"},
                    {"date": "2026-01-03", "close": 101.25},
                    {"date": "2026-01-04", "close": None},
                ]
            }
        }

        self.assertEqual(closing_prices_from_history_payload(payload), [100.5, 101.25])

    def test_last_price_from_quote_payload(self):
        payload = {"quotes": {"quote": [{"symbol": "SPY", "last": "590.25"}]}}

        self.assertEqual(last_price_from_quote_payload(payload), 590.25)

    def test_sma_rsi_and_realized_volatility_are_calculated(self):
        closes = [100 + index for index in range(220)]

        self.assertEqual(simple_moving_average(closes, 20), sum(closes[-20:]) / 20)
        self.assertEqual(relative_strength_index(closes, 14), 100.0)
        self.assertIsNotNone(realized_volatility(closes, 20))

    def test_characterization_outputs_stock_level_states(self):
        closes = [100 + index for index in range(220)]

        row = characterize_technical_condition(
            "spy",
            closes,
            scan_id="scan-1",
            technical_timestamp="2026-07-06 10:00:00 AM EDT",
            current_price=320.5,
        ).to_repository_row()

        self.assertEqual(row["ticker"], "SPY")
        self.assertEqual(row["scan_id"], "scan-1")
        self.assertEqual(row["price"], 320.5)
        self.assertEqual(row["trend_state"], "bullish_alignment")
        self.assertIn(row["momentum_state"], {"overbought_positive", "overbought_mixed"})
        self.assertIsNone(row["technical_score"])
        self.assertIn("price vs 20 SMA", row["technical_notes"])


if __name__ == "__main__":
    unittest.main()
