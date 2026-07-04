"""U.S. equity market calendar helpers for scheduled research observations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class MarketCalendarStatus:
    trading_day: bool
    reason: str
    early_close: bool = False


def us_equity_market_status(day: date) -> MarketCalendarStatus:
    """Return whether the regular U.S. equity market is expected to be open."""
    holiday = us_equity_market_holiday_name(day)
    if holiday:
        return MarketCalendarStatus(False, holiday)

    if day.weekday() >= 5:
        return MarketCalendarStatus(False, "weekend")

    return MarketCalendarStatus(True, "regular trading day", is_us_equity_early_close(day))


def is_us_equity_trading_day(day: date) -> bool:
    return us_equity_market_status(day).trading_day


def is_us_equity_early_close(day: date) -> bool:
    """Return known recurring early-close candidates.

    This is intentionally conservative readiness work. It identifies common
    recurring early-close days so the scheduler can surface them later, but it
    does not yet adjust scan times.
    """
    if day.weekday() >= 5:
        return False
    if day == _observed_fixed_holiday(day.year, 7, 4) - timedelta(days=1):
        return True
    if day == _fourth_weekday(day.year, 11, 3) + timedelta(days=1):
        return True
    if day == _observed_fixed_holiday(day.year, 12, 25) - timedelta(days=1):
        return True
    return False


def us_equity_market_holiday_name(day: date) -> str | None:
    """Return the regular full-day U.S. equity market holiday name, if any."""
    holidays = {
        _observed_fixed_holiday(day.year, 1, 1): "New Year's Day",
        _nth_weekday(day.year, 1, 0, 3): "Martin Luther King Jr. Day",
        _nth_weekday(day.year, 2, 0, 3): "Washington's Birthday",
        _good_friday(day.year): "Good Friday",
        _last_weekday(day.year, 5, 0): "Memorial Day",
        _observed_fixed_holiday(day.year, 6, 19): "Juneteenth National Independence Day",
        _observed_fixed_holiday(day.year, 7, 4): "Independence Day",
        _nth_weekday(day.year, 9, 0, 1): "Labor Day",
        _fourth_weekday(day.year, 11, 3): "Thanksgiving Day",
        _observed_fixed_holiday(day.year, 12, 25): "Christmas Day",
    }
    return holidays.get(day)


def _observed_fixed_holiday(year: int, month: int, day: int) -> date:
    holiday = date(year, month, day)
    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    current = date(year, month, 1)
    offset = (weekday - current.weekday()) % 7
    return current + timedelta(days=offset + (occurrence - 1) * 7)


def _fourth_weekday(year: int, month: int, weekday: int) -> date:
    return _nth_weekday(year, month, weekday, 4)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def _good_friday(year: int) -> date:
    return _easter_sunday(year) - timedelta(days=2)


def _easter_sunday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)
