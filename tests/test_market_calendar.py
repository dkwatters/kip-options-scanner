import unittest
from datetime import date

from src.market_calendar import us_equity_market_status


class MarketCalendarTest(unittest.TestCase):
    def test_weekend_is_closed(self):
        status = us_equity_market_status(date(2026, 7, 4))

        self.assertFalse(status.trading_day)
        self.assertEqual(status.reason, "weekend")

    def test_observed_independence_day_is_closed(self):
        status = us_equity_market_status(date(2026, 7, 3))

        self.assertFalse(status.trading_day)
        self.assertEqual(status.reason, "Independence Day")

    def test_regular_weekday_is_open(self):
        status = us_equity_market_status(date(2026, 7, 6))

        self.assertTrue(status.trading_day)
        self.assertEqual(status.reason, "regular trading day")


if __name__ == "__main__":
    unittest.main()
