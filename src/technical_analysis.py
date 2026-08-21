"""Stock-level Technical Analysis Model observations.

The Technical Analysis Model is intentionally independent of contract quality
logic. It records underlying-security condition for later research only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import isfinite, log, sqrt
from statistics import stdev
from typing import Any, Iterable


TAM_MODEL_NAME = "Technical Analysis Model"
TAM_MODEL_VERSION = "v0.1"
TECHNICAL_ANALYSIS_VERSION = "technical-analysis-v0.1"
TECHNICAL_SCORING_VERSION = "technical-setup-score-v0.1"
SMA_NEAR_THRESHOLD = 0.01


@dataclass(frozen=True, slots=True)
class TechnicalObservation:
    ticker: str
    scan_id: str | None
    technical_timestamp: str
    price: float | None
    sma_20: float | None
    sma_50: float | None
    sma_200: float | None
    price_vs_sma_20: float | None
    price_vs_sma_50: float | None
    price_vs_sma_200: float | None
    sma_20_vs_sma_50: float | None
    sma_50_vs_sma_200: float | None
    rsi_14: float | None
    macd_line: float | None
    macd_signal: float | None
    macd_histogram: float | None
    realized_volatility_20d: float | None
    trend_state: str
    momentum_state: str
    volatility_state: str
    technical_score: float | None
    technical_notes: str

    def to_repository_row(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "scan_id": self.scan_id,
            "technical_timestamp": self.technical_timestamp,
            "price": self.price,
            "sma_20": self.sma_20,
            "sma_50": self.sma_50,
            "sma_200": self.sma_200,
            "price_vs_sma_20": self.price_vs_sma_20,
            "price_vs_sma_50": self.price_vs_sma_50,
            "price_vs_sma_200": self.price_vs_sma_200,
            "sma_20_vs_sma_50": self.sma_20_vs_sma_50,
            "sma_50_vs_sma_200": self.sma_50_vs_sma_200,
            "rsi_14": self.rsi_14,
            "macd_line": self.macd_line,
            "macd_signal": self.macd_signal,
            "macd_histogram": self.macd_histogram,
            "realized_volatility_20d": self.realized_volatility_20d,
            "trend_state": self.trend_state,
            "momentum_state": self.momentum_state,
            "volatility_state": self.volatility_state,
            "technical_score": self.technical_score,
            "technical_notes": self.technical_notes,
        }


def technical_analysis_rows_for_symbols(
    client: Any,
    symbols: Iterable[str],
    *,
    scan_id: str | None,
    technical_timestamp: str,
    end_date: date,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Fetch history and return repository-ready TAM rows plus per-symbol errors."""
    rows: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    start_date = end_date - timedelta(days=320)
    for symbol in symbols:
        normalized = str(symbol).strip().upper()
        if not normalized:
            continue
        try:
            payload = client.get_price_history(
                normalized,
                start=start_date.isoformat(),
                end=end_date.isoformat(),
            )
            closes = closing_prices_from_history_payload(payload)
            quote_price = None
            try:
                quote_price = last_price_from_quote_payload(client.get_quote(normalized))
            except Exception:
                quote_price = None
            observation = characterize_technical_condition(
                normalized,
                closes,
                scan_id=scan_id,
                technical_timestamp=technical_timestamp,
                current_price=quote_price,
            )
            rows.append(observation.to_repository_row())
        except Exception as error:
            errors[normalized] = str(error)
    return rows, errors


def closing_prices_from_history_payload(payload: dict[str, Any]) -> list[float]:
    history = payload.get("history", {}) if isinstance(payload, dict) else {}
    days = history.get("day") if isinstance(history, dict) else None
    if isinstance(days, dict):
        days = [days]
    if not isinstance(days, list):
        return []
    closes: list[float] = []
    for day in days:
        if not isinstance(day, dict):
            continue
        close = _number_or_none(day.get("close"))
        if close is not None and close > 0:
            closes.append(close)
    return closes


def last_price_from_quote_payload(payload: dict[str, Any]) -> float | None:
    quotes = payload.get("quotes", {}) if isinstance(payload, dict) else {}
    quote = quotes.get("quote") if isinstance(quotes, dict) else None
    if isinstance(quote, list):
        quote = quote[0] if quote else None
    if not isinstance(quote, dict):
        return None
    price = _number_or_none(quote.get("last"))
    return price if price is not None and price > 0 else None


def characterize_technical_condition(
    ticker: str,
    closes: list[float],
    *,
    scan_id: str | None,
    technical_timestamp: str,
    current_price: float | None = None,
) -> TechnicalObservation:
    price = current_price if current_price is not None else closes[-1] if closes else None
    sma_20 = simple_moving_average(closes, 20)
    sma_50 = simple_moving_average(closes, 50)
    sma_200 = simple_moving_average(closes, 200)
    rsi_14 = relative_strength_index(closes, 14)
    macd_line, macd_signal, macd_histogram = macd(closes)
    realized_volatility_20d = realized_volatility(closes, 20)

    price_vs_sma_20 = relative_difference(price, sma_20)
    price_vs_sma_50 = relative_difference(price, sma_50)
    price_vs_sma_200 = relative_difference(price, sma_200)
    sma_20_vs_sma_50 = relative_difference(sma_20, sma_50)
    sma_50_vs_sma_200 = relative_difference(sma_50, sma_200)
    trend_state = classify_trend(price, sma_20, sma_50, sma_200)
    momentum_state = classify_momentum(rsi_14, macd_line, macd_signal, macd_histogram)
    volatility_state = classify_volatility(realized_volatility_20d)

    notes = "; ".join(
        note
        for note in (
            _relation_note("price vs 20 SMA", price_vs_sma_20),
            _relation_note("price vs 50 SMA", price_vs_sma_50),
            _relation_note("price vs 200 SMA", price_vs_sma_200),
            _relation_note("20/50 SMA", sma_20_vs_sma_50),
            _relation_note("50/200 SMA", sma_50_vs_sma_200),
        )
        if note
    )

    return TechnicalObservation(
        ticker=ticker.upper(),
        scan_id=scan_id,
        technical_timestamp=technical_timestamp,
        price=price,
        sma_20=sma_20,
        sma_50=sma_50,
        sma_200=sma_200,
        price_vs_sma_20=price_vs_sma_20,
        price_vs_sma_50=price_vs_sma_50,
        price_vs_sma_200=price_vs_sma_200,
        sma_20_vs_sma_50=sma_20_vs_sma_50,
        sma_50_vs_sma_200=sma_50_vs_sma_200,
        rsi_14=rsi_14,
        macd_line=macd_line,
        macd_signal=macd_signal,
        macd_histogram=macd_histogram,
        realized_volatility_20d=realized_volatility_20d,
        trend_state=trend_state,
        momentum_state=momentum_state,
        volatility_state=volatility_state,
        technical_score=None,
        technical_notes=notes or "Insufficient price history for full TAM characterization.",
    )


def simple_moving_average(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def relative_strength_index(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    seed = changes[:period]
    average_gain = sum(max(change, 0.0) for change in seed) / period
    average_loss = sum(abs(min(change, 0.0)) for change in seed) / period
    for change in changes[period:]:
        gain = max(change, 0.0)
        loss = abs(min(change, 0.0))
        average_gain = ((average_gain * (period - 1)) + gain) / period
        average_loss = ((average_loss * (period - 1)) + loss) / period
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))


def macd(values: list[float]) -> tuple[float | None, float | None, float | None]:
    if len(values) < 35:
        return None, None, None
    ema_12 = exponential_moving_average_series(values, 12)
    ema_26 = exponential_moving_average_series(values, 26)
    macd_values = [
        fast - slow
        for fast, slow in zip(ema_12, ema_26)
        if fast is not None and slow is not None
    ]
    signal_values = exponential_moving_average_series(macd_values, 9)
    signal = signal_values[-1] if signal_values else None
    line = macd_values[-1] if macd_values else None
    histogram = line - signal if line is not None and signal is not None else None
    return line, signal, histogram


def exponential_moving_average_series(
    values: list[float], period: int
) -> list[float | None]:
    if not values:
        return []
    result: list[float | None] = []
    multiplier = 2.0 / (period + 1)
    ema: float | None = None
    for index, value in enumerate(values):
        if index + 1 < period:
            result.append(None)
            continue
        if index + 1 == period:
            ema = sum(values[:period]) / period
        else:
            ema = (value - float(ema)) * multiplier + float(ema)
        result.append(ema)
    return result


def realized_volatility(values: list[float], period: int = 20) -> float | None:
    if len(values) <= period:
        return None
    returns = [
        log(values[index] / values[index - 1])
        for index in range(len(values) - period, len(values))
        if values[index - 1] > 0 and values[index] > 0
    ]
    if len(returns) < 2:
        return None
    return stdev(returns) * sqrt(252)


def relative_difference(value: float | None, reference: float | None) -> float | None:
    if value is None or reference is None or reference == 0:
        return None
    return (value - reference) / reference


def classify_trend(
    price: float | None,
    sma_20: float | None,
    sma_50: float | None,
    sma_200: float | None,
) -> str:
    if None in (price, sma_20, sma_50, sma_200):
        return "insufficient_history"
    if price > sma_20 > sma_50 > sma_200:
        return "bullish_alignment"
    if price < sma_20 < sma_50 < sma_200:
        return "bearish_alignment"
    if price > sma_50 and sma_50 > sma_200:
        return "constructive"
    if price < sma_50 and sma_50 < sma_200:
        return "deteriorating"
    return "mixed"


def classify_momentum(
    rsi_14: float | None,
    macd_line: float | None,
    macd_signal: float | None,
    macd_histogram: float | None,
) -> str:
    if rsi_14 is None or macd_line is None or macd_signal is None or macd_histogram is None:
        return "insufficient_history"
    if rsi_14 >= 70:
        return "overbought_positive" if macd_histogram > 0 else "overbought_mixed"
    if rsi_14 <= 30:
        return "oversold_negative" if macd_histogram < 0 else "oversold_mixed"
    if rsi_14 >= 55 and macd_line > macd_signal and macd_histogram > 0:
        return "positive"
    if rsi_14 <= 45 and macd_line < macd_signal and macd_histogram < 0:
        return "negative"
    return "neutral"


def classify_volatility(value: float | None) -> str:
    if value is None:
        return "unavailable"
    if value < 0.25:
        return "low"
    if value <= 0.50:
        return "moderate"
    return "high"


def price_vs_sma_state(relative_value: float | None) -> str:
    if relative_value is None:
        return "unavailable"
    if abs(relative_value) <= SMA_NEAR_THRESHOLD:
        return "near"
    return "above" if relative_value > 0 else "below"


def sma_alignment_state(relative_value: float | None) -> str:
    if relative_value is None:
        return "unavailable"
    return "bullish" if relative_value > 0 else "bearish"


def macd_display_state(
    macd_line: float | None,
    macd_signal: float | None,
    macd_histogram: float | None,
) -> str:
    if macd_line is None or macd_signal is None or macd_histogram is None:
        return "unavailable"
    if macd_line > macd_signal and macd_histogram > 0:
        return "bullish"
    if macd_line < macd_signal and macd_histogram < 0:
        return "bearish"
    return "neutral"


def rsi_regime(rsi_14: float | None) -> str:
    if rsi_14 is None:
        return "unavailable"
    if rsi_14 < 40:
        return "oversold"
    if rsi_14 <= 70:
        return "neutral"
    if rsi_14 <= 80:
        return "elevated"
    return "overbought"


def derived_technical_display_fields(row: dict[str, Any]) -> dict[str, str]:
    return {
        "price_vs_sma_20_state": price_vs_sma_state(
            _number_or_none(row.get("price_vs_sma_20"))
        ),
        "price_vs_sma_50_state": price_vs_sma_state(
            _number_or_none(row.get("price_vs_sma_50"))
        ),
        "price_vs_sma_200_state": price_vs_sma_state(
            _number_or_none(row.get("price_vs_sma_200"))
        ),
        "sma_20_50_state": sma_alignment_state(
            _number_or_none(row.get("sma_20_vs_sma_50"))
        ),
        "sma_50_200_state": sma_alignment_state(
            _number_or_none(row.get("sma_50_vs_sma_200"))
        ),
        "macd_state": macd_display_state(
            _number_or_none(row.get("macd_line")),
            _number_or_none(row.get("macd_signal")),
            _number_or_none(row.get("macd_histogram")),
        ),
        "rsi_regime": rsi_regime(_number_or_none(row.get("rsi_14"))),
    }


def technical_setup_score(row: dict[str, Any]) -> float | None:
    """Return an experimental descriptive TAM setup score from 0 to 100."""
    fields = derived_technical_display_fields(row)
    has_trend_data = any(
        fields[key] != "unavailable"
        for key in (
            "price_vs_sma_20_state",
            "price_vs_sma_50_state",
            "price_vs_sma_200_state",
            "sma_20_50_state",
            "sma_50_200_state",
        )
    )
    has_macd_data = any(
        _number_or_none(row.get(key)) is not None
        for key in ("macd_line", "macd_signal", "macd_histogram")
    )
    has_rsi_data = _number_or_none(row.get("rsi_14")) is not None
    volatility_state = str(row.get("volatility_state") or "").strip().lower()
    has_volatility_data = volatility_state not in {"", "unavailable", "insufficient_history"}
    if not any((has_trend_data, has_macd_data, has_rsi_data, has_volatility_data)):
        return None

    score = 0.0

    trend_checks = (
        fields["price_vs_sma_20_state"] == "above",
        fields["price_vs_sma_50_state"] == "above",
        fields["price_vs_sma_200_state"] == "above",
        fields["sma_20_50_state"] == "bullish",
        fields["sma_50_200_state"] == "bullish",
    )
    score += sum(8.0 for passed in trend_checks if passed)

    macd_line = _number_or_none(row.get("macd_line"))
    macd_signal = _number_or_none(row.get("macd_signal"))
    macd_histogram = _number_or_none(row.get("macd_histogram"))
    if macd_line is not None and macd_signal is not None and macd_line > macd_signal:
        score += 12.5
    if macd_histogram is not None and macd_histogram > 0:
        score += 12.5

    rsi = _number_or_none(row.get("rsi_14"))
    if rsi is not None:
        if 50 <= rsi <= 70:
            score += 20.0
        elif 40 <= rsi < 50 or 70 < rsi <= 80:
            score += 10.0
        else:
            score += 5.0

    if volatility_state in {"moderate", "normal", "neutral"}:
        score += 15.0
    elif volatility_state == "low":
        score += 10.0
    elif volatility_state == "high":
        score += 5.0

    return round(max(0.0, min(score, 100.0)), 1)


def technical_setup_grade(score: float | None) -> str:
    """Return the descriptive grade for an experimental TAM setup score."""
    if score is None:
        return "Unavailable"
    if score >= 80:
        return "Strong technical setup"
    if score >= 65:
        return "Constructive"
    if score >= 45:
        return "Neutral / mixed"
    if score >= 25:
        return "Weak"
    return "Poor"


def _relation_note(label: str, value: float | None) -> str | None:
    if value is None:
        return None
    direction = "above" if value >= 0 else "below"
    return f"{label}: {abs(value):.2%} {direction}"


def _number_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None
