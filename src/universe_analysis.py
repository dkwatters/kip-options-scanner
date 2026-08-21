"""Deterministic presentation model for an exact Research Universe analysis run.

This module interprets existing TAM observations for comparison and explanation.
It does not change TAM calculations, stored scores, membership, or execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from src.technical_analysis import (
    derived_technical_display_fields,
    technical_setup_grade,
    technical_setup_score,
)


UNIVERSE_ANALYSIS_PRESENTATION_VERSION = "universe-analysis-presentation-v0.1"
EXTENSION_THRESHOLDS_VERSION = "universe-analysis-extension-thresholds-v0.1"


@dataclass(frozen=True, slots=True)
class ExtensionThresholds:
    """Experimental presentation-only distances; not scoring or trading rules."""

    moderate_20: float = 0.04
    elevated_20: float = 0.08
    moderate_50: float = 0.08
    elevated_50: float = 0.15
    moderate_200: float = 0.15
    elevated_200: float = 0.30
    below_long_term: float = -0.01


PRESENTATION_EXTENSION_THRESHOLDS = ExtensionThresholds()


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def readable_state(value: Any) -> str:
    text = str(value or "unavailable").replace("_", " ").strip()
    return text.capitalize()


def technical_profile(score: float | None) -> str:
    grade = technical_setup_grade(score)
    return {
        "Strong technical setup": "Strong",
        "Neutral / mixed": "Mixed",
        "Poor": "Weak",
    }.get(grade, grade)


def extension_profile(
    row: dict[str, Any], thresholds: ExtensionThresholds = PRESENTATION_EXTENSION_THRESHOLDS,
) -> str:
    distances = {
        20: _number(row.get("price_vs_sma_20")),
        50: _number(row.get("price_vs_sma_50")),
        200: _number(row.get("price_vs_sma_200")),
    }
    if all(value is None for value in distances.values()):
        return "Unavailable"
    if distances[200] is not None and distances[200] < thresholds.below_long_term:
        return "Below long-term trend"
    elevated = (
        (distances[20] is not None and distances[20] >= thresholds.elevated_20)
        or (distances[50] is not None and distances[50] >= thresholds.elevated_50)
        or (distances[200] is not None and distances[200] >= thresholds.elevated_200)
    )
    if elevated:
        return "Elevated"
    moderate = (
        (distances[20] is not None and distances[20] >= thresholds.moderate_20)
        or (distances[50] is not None and distances[50] >= thresholds.moderate_50)
        or (distances[200] is not None and distances[200] >= thresholds.moderate_200)
    )
    return "Moderately extended" if moderate else "Near trend"


def key_signal(row: dict[str, Any]) -> str:
    trend = str(row.get("trend_state") or "")
    momentum = str(row.get("momentum_state") or "")
    extension = extension_profile(row)
    if extension == "Elevated" and "bullish" in trend:
        return "Bullish alignment; extension elevated"
    if "bullish" in trend and momentum in {"positive", "overbought_positive"}:
        return "Bullish trend with positive momentum"
    if "bearish" in trend or momentum == "negative":
        return "Weak trend or momentum"
    return f"{readable_state(trend)} trend; {readable_state(momentum)} momentum"


def ranked_analysis_rows(
    rows: Iterable[dict[str, Any]], company_names: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Rank the exact analyzed population by the existing descriptive score."""
    names = company_names or {}
    enriched = []
    for raw in rows:
        row = dict(raw)
        ticker = str(row.get("ticker") or "").upper()
        score = technical_setup_score(row)
        row.update(derived_technical_display_fields(row))
        row.update({
            "ticker": ticker,
            "company_name": names.get(ticker, ticker),
            "technical_profile": technical_profile(score),
            "technical_profile_score": score,
            "trend_label": readable_state(row.get("trend_state")),
            "momentum_label": readable_state(row.get("momentum_state")),
            "extension_label": extension_profile(row),
            "volatility_label": readable_state(row.get("volatility_state")),
            "key_signal": key_signal(row),
            "status_label": "Analyzed",
        })
        enriched.append(row)
    enriched.sort(key=lambda row: (
        -(row["technical_profile_score"] if row["technical_profile_score"] is not None else -1),
        row["ticker"],
    ))
    for rank, row in enumerate(enriched, 1):
        row["rank"] = rank
    return enriched


def filter_analysis_rows(
    rows: Iterable[dict[str, Any]], *, search: str = "", profiles: Iterable[str] = (),
    trends: Iterable[str] = (), momentum: Iterable[str] = (), volatility: Iterable[str] = (),
) -> list[dict[str, Any]]:
    query = search.strip().casefold()
    profile_set, trend_set = set(profiles), set(trends)
    momentum_set, volatility_set = set(momentum), set(volatility)
    return [row for row in rows if (
        (not query or query in row["ticker"].casefold() or query in row["company_name"].casefold())
        and (not profile_set or row["technical_profile"] in profile_set)
        and (not trend_set or row["trend_label"] in trend_set)
        and (not momentum_set or row["momentum_label"] in momentum_set)
        and (not volatility_set or row["volatility_label"] in volatility_set)
    )]


def analysis_summary(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return summary counts that reconcile exactly to the analyzed population."""
    population = list(rows)
    profile_labels = ("Strong", "Constructive", "Mixed", "Weak")
    profiles = {
        label: sum(row.get("technical_profile") == label for row in population)
        for label in profile_labels
    }
    unknown_profiles = sorted({
        str(row.get("technical_profile") or "Unavailable")
        for row in population
        if row.get("technical_profile") not in profile_labels
    })
    if sum(profiles.values()) != len(population):
        raise ValueError(
            "Technical profile counts do not reconcile to analyzed members: "
            + ", ".join(unknown_profiles)
        )
    rsi = [_number(row.get("rsi_14")) for row in population]
    available_rsi = [value for value in rsi if value is not None]
    return {
        "analyzed": len(population),
        "profiles": profiles,
        "bullish_trends": sum(row.get("trend_label") == "Bullish alignment" for row in population),
        "above_200_day_sma": sum(row.get("price_vs_sma_200_state") == "above" for row in population),
        "bullish_macd": sum(row.get("macd_state") == "bullish" for row in population),
        "high_volatility": sum(row.get("volatility_label") == "High" for row in population),
        "average_rsi": sum(available_rsi) / len(available_rsi) if available_rsi else None,
    }


def analysis_explanation(row: dict[str, Any]) -> dict[str, Any]:
    """Explain one profile exclusively from stored deterministic observations."""
    positives: list[str] = []
    watchouts: list[str] = []
    states = derived_technical_display_fields(row)
    above_periods = [period for period in (20, 50, 200) if states[f"price_vs_sma_{period}_state"] == "above"]
    if above_periods:
        positives.append("Price is above the " + ", ".join(str(period) for period in above_periods) + "-day moving average" + ("s" if len(above_periods) > 1 else "") + ".")
    if str(row.get("trend_state")) == "bullish_alignment":
        positives.append("The moving averages are in bullish alignment.")
    if states["macd_state"] == "bullish":
        positives.append("MACD is positive relative to its signal line.")
    if str(row.get("momentum_state")) in {"positive", "overbought_positive"}:
        positives.append("Current momentum indicators are positive.")
    extension = extension_profile(row)
    if extension in {"Elevated", "Moderately extended"}:
        for period in (20, 50, 200):
            distance = _number(row.get(f"price_vs_sma_{period}"))
            if distance is not None and distance > 0:
                watchouts.append(f"Price is {distance:.1%} above the {period}-day SMA.")
        watchouts.append("Trend strength does not automatically imply favorable fresh-entry timing.")
    rsi = _number(row.get("rsi_14"))
    if rsi is not None and states["rsi_regime"] in {"elevated", "overbought"}:
        watchouts.append(f"RSI is {rsi:.1f} ({states['rsi_regime']}).")
    trend = readable_state(row.get("trend_state"))
    momentum = readable_state(row.get("momentum_state"))
    summary = f"{row.get('ticker')} shows {trend.casefold()} trend characteristics and {momentum.casefold()} momentum."
    if extension in {"Elevated", "Moderately extended"}:
        summary += f" Price is {extension.casefold()} relative to recent trend baselines."
        if str(row.get("trend_state")) == "bullish_alignment":
            summary += " This can coexist with bullish moving-average alignment."
    return {"summary": summary, "positives": tuple(positives), "watchouts": tuple(watchouts)}
