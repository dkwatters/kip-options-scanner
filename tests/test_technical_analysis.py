import unittest

from src.technical_analysis import (
    characterize_technical_condition,
    closing_prices_from_history_payload,
    derived_technical_display_fields,
    last_price_from_quote_payload,
    macd_display_state,
    price_vs_sma_state,
    realized_volatility,
    relative_strength_index,
    rsi_regime,
    sma_alignment_state,
    simple_moving_average,
    technical_setup_grade,
    technical_setup_score,
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

    def test_derived_display_states_are_calculated(self):
        row = {
            "price_vs_sma_20": 0.02,
            "price_vs_sma_50": -0.03,
            "price_vs_sma_200": 0.005,
            "sma_20_vs_sma_50": 0.04,
            "sma_50_vs_sma_200": -0.02,
            "macd_line": 1.2,
            "macd_signal": 0.9,
            "macd_histogram": 0.3,
            "rsi_14": 72,
        }

        self.assertEqual(price_vs_sma_state(0.02), "above")
        self.assertEqual(price_vs_sma_state(-0.02), "below")
        self.assertEqual(price_vs_sma_state(0.005), "near")
        self.assertEqual(price_vs_sma_state(None), "unavailable")
        self.assertEqual(sma_alignment_state(0.01), "bullish")
        self.assertEqual(sma_alignment_state(-0.01), "bearish")
        self.assertEqual(sma_alignment_state(None), "unavailable")
        self.assertEqual(macd_display_state(1.2, 0.9, 0.3), "bullish")
        self.assertEqual(macd_display_state(0.9, 1.2, -0.3), "bearish")
        self.assertEqual(macd_display_state(1.2, 0.9, -0.1), "neutral")
        self.assertEqual(macd_display_state(None, 0.9, 0.3), "unavailable")
        self.assertEqual(rsi_regime(35), "oversold")
        self.assertEqual(rsi_regime(55), "neutral")
        self.assertEqual(rsi_regime(75), "elevated")
        self.assertEqual(rsi_regime(85), "overbought")
        self.assertEqual(rsi_regime(None), "unavailable")

        self.assertEqual(
            derived_technical_display_fields(row),
            {
                "price_vs_sma_20_state": "above",
                "price_vs_sma_50_state": "below",
                "price_vs_sma_200_state": "near",
                "sma_20_50_state": "bullish",
                "sma_50_200_state": "bearish",
                "macd_state": "bullish",
                "rsi_regime": "elevated",
            },
        )

    def test_technical_setup_score_uses_observational_rubric(self):
        full_setup = {
            "price_vs_sma_20": 0.03,
            "price_vs_sma_50": 0.06,
            "price_vs_sma_200": 0.12,
            "sma_20_vs_sma_50": 0.04,
            "sma_50_vs_sma_200": 0.08,
            "macd_line": 1.5,
            "macd_signal": 1.0,
            "macd_histogram": 0.5,
            "rsi_14": 62,
            "volatility_state": "moderate",
        }
        partial_setup = {
            "price_vs_sma_20": 0.03,
            "price_vs_sma_50": -0.06,
            "price_vs_sma_200": None,
            "sma_20_vs_sma_50": -0.04,
            "sma_50_vs_sma_200": 0.08,
            "macd_line": 0.8,
            "macd_signal": 1.0,
            "macd_histogram": -0.2,
            "rsi_14": 75,
            "volatility_state": "high",
        }
        unavailable_setup = {}

        self.assertEqual(technical_setup_score(full_setup), 100.0)
        self.assertEqual(technical_setup_score(partial_setup), 31.0)
        self.assertIsNone(technical_setup_score(unavailable_setup))

    def test_technical_setup_grade_uses_requested_bands(self):
        self.assertEqual(technical_setup_grade(100), "Strong technical setup")
        self.assertEqual(technical_setup_grade(80), "Strong technical setup")
        self.assertEqual(technical_setup_grade(79), "Constructive")
        self.assertEqual(technical_setup_grade(65), "Constructive")
        self.assertEqual(technical_setup_grade(64), "Neutral / mixed")
        self.assertEqual(technical_setup_grade(45), "Neutral / mixed")
        self.assertEqual(technical_setup_grade(44), "Weak")
        self.assertEqual(technical_setup_grade(25), "Weak")
        self.assertEqual(technical_setup_grade(24), "Poor")
        self.assertEqual(technical_setup_grade(0), "Poor")
        self.assertEqual(technical_setup_grade(None), "Unavailable")

    def test_technical_setup_score_handles_insufficient_history(self):
        insufficient = {
            "price_vs_sma_20": None,
            "price_vs_sma_50": None,
            "price_vs_sma_200": None,
            "sma_20_vs_sma_50": None,
            "sma_50_vs_sma_200": None,
            "macd_line": None,
            "macd_signal": None,
            "macd_histogram": None,
            "rsi_14": None,
            "volatility_state": "unavailable",
        }

        self.assertIsNone(technical_setup_score(insufficient))
        self.assertEqual(technical_setup_grade(technical_setup_score(insufficient)), "Unavailable")

    def test_technical_setup_score_handles_macd_rsi_edges(self):
        row = {
            "price_vs_sma_20": -0.02,
            "price_vs_sma_50": -0.03,
            "price_vs_sma_200": -0.04,
            "sma_20_vs_sma_50": -0.01,
            "sma_50_vs_sma_200": -0.02,
            "macd_line": 1.0,
            "macd_signal": 1.0,
            "macd_histogram": 0.0,
            "rsi_14": 50,
            "volatility_state": "moderate",
        }
        overbought_row = dict(row, rsi_14=80, volatility_state="high")
        normal_volatility_row = dict(row, volatility_state="normal")
        low_rsi_row = dict(row, rsi_14=39, volatility_state="")

        self.assertEqual(technical_setup_score(row), 35.0)
        self.assertEqual(technical_setup_score(overbought_row), 15.0)
        self.assertEqual(technical_setup_score(normal_volatility_row), 35.0)
        self.assertEqual(technical_setup_score(low_rsi_row), 5.0)


if __name__ == "__main__":
    unittest.main()
