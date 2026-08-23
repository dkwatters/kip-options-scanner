from dataclasses import replace
from datetime import date

import pytest

from src.model_performance import model_performance_scorecard
from src.research_repository import REPOSITORY_BACKEND_SQLITE, ResearchRepositoryTarget
from src.signal_outcomes import OutcomeStatus, PriceObservation, evaluate_persisted_signal, evaluate_signal_horizons, evaluate_signal_outcome
from src.signal_repository import HistoricalSignalConflict, SignalRepository
from src.signals import Signal, SignalDirection, technical_setup_signal


def signal(**overrides):
    values = dict(signal_id="s1", ticker="nvda", as_of="2026-01-05T12:00:00+00:00", model_id="model", model_version="v1", direction=SignalDirection.BULLISH, conviction=.7, confidence=None, reasoning="deterministic evidence", created_at="2026-01-05T12:01:00+00:00")
    values.update(overrides); return Signal(**values)


def test_signal_validation_and_neutral_is_distinct_from_abstain():
    neutral = signal(direction=SignalDirection.NEUTRAL, conviction=0.0)
    abstain = signal(signal_id="s2", direction=SignalDirection.ABSTAIN, conviction=0.0)
    assert neutral.direction != abstain.direction
    with pytest.raises(ValueError, match="conviction"):
        signal(conviction=1.01)
    with pytest.raises(ValueError, match="Unsupported"):
        signal(direction="up")
    with pytest.raises(ValueError, match="zero conviction"):
        signal(direction=SignalDirection.ABSTAIN, conviction=.1)


def test_existing_technical_setup_score_produces_versioned_signal():
    row = {"ticker": "nvda", "technical_timestamp": "2026-01-05", "scan_id": "scan-1", "price_vs_sma_20": .1, "price_vs_sma_50": .1, "price_vs_sma_200": .1, "sma_20_vs_sma_50": .1, "sma_50_vs_sma_200": .1, "macd_line": 2, "macd_signal": 1, "macd_histogram": 1, "rsi_14": 60, "volatility_state": "moderate"}
    result = technical_setup_signal(row, created_at="2026-01-05T12:00:00+00:00")
    assert result.model_id == "technical-setup-score"
    assert result.model_version == "technical-setup-score-v0.1"
    assert result.direction is SignalDirection.BULLISH
    assert result.conviction == 1.0
    assert result.confidence is None
    assert result.evidence_refs == ("technical_characterization:scan-1:NVDA",)


def test_missing_technical_inputs_abstain_instead_of_neutral():
    result = technical_setup_signal({"ticker": "AAPL", "technical_timestamp": "2026-01-05"})
    assert result.direction is SignalDirection.ABSTAIN
    assert result.conviction == 0.0


def test_persistence_filters_versions_and_rejects_historical_mutation(tmp_path):
    repo = SignalRepository(ResearchRepositoryTarget(REPOSITORY_BACKEND_SQLITE, sqlite_path=tmp_path / "research.sqlite"))
    original = signal()
    assert repo.save_signal(original) is True
    assert repo.save_signal(original) is False
    repo.save_signal(signal(signal_id="s2", model_version="v2", as_of="2026-02-01"))
    assert repo.list_signals(ticker="nvda", model_id="model", model_version="v1", as_of_start="2026-01-01", as_of_end="2026-01-31") == (original,)
    with pytest.raises(HistoricalSignalConflict):
        repo.save_signal(replace(original, conviction=.8))


def prices(count=65):
    return [PriceObservation(date.fromordinal(date(2026, 1, 5).toordinal() + index), 100 + index) for index in range(count)]


def test_forward_outcome_uses_trading_observation_offsets_and_persists(tmp_path):
    source = signal()
    outcomes = evaluate_signal_horizons(source, prices(), evaluated_at="2026-04-10T00:00:00+00:00")
    assert [row.horizon_trading_days for row in outcomes] == [5, 20, 60]
    assert outcomes[0].start_date == "2026-01-05"
    assert outcomes[0].end_date == "2026-01-10"
    assert outcomes[0].absolute_return == pytest.approx(.05)
    assert outcomes[0].directional_correct is True
    repo = SignalRepository(ResearchRepositoryTarget(REPOSITORY_BACKEND_SQLITE, sqlite_path=tmp_path / "research.sqlite"))
    repo.save_signal(source); repo.save_outcomes(outcomes)
    assert repo.list_outcomes(signal_ids=[source.signal_id]) == outcomes


def test_missing_and_not_yet_eligible_market_data():
    assert evaluate_signal_outcome(signal(), [], 5).status is OutcomeStatus.MISSING_DATA
    pending = evaluate_signal_outcome(signal(), prices(3), 5, through_date=date(2026, 1, 7))
    assert pending.status is OutcomeStatus.NOT_YET_ELIGIBLE


def test_persisted_signal_evaluation_keeps_future_data_out_of_signal(tmp_path):
    repo = SignalRepository(ResearchRepositoryTarget(REPOSITORY_BACKEND_SQLITE, sqlite_path=tmp_path / "research.sqlite"))
    original = signal(); repo.save_signal(original)
    class Provider:
        def daily_closes(self, ticker, *, on_or_after):
            assert ticker == "NVDA" and on_or_after == date(2026, 1, 5)
            return prices()
    evaluated = evaluate_persisted_signal(repo, original.signal_id, Provider(), horizons=(5,))
    assert evaluated[0].status is OutcomeStatus.EVALUATED
    assert repo.list_signals() == (original,)


def test_performance_aggregation_exposes_counts_and_horizon_statistics():
    signals = [signal(), signal(signal_id="s2", direction=SignalDirection.BEARISH, conviction=-.4), signal(signal_id="s3", direction=SignalDirection.ABSTAIN, conviction=0)]
    outcomes = [evaluate_signal_outcome(signals[0], prices(), 5), evaluate_signal_outcome(signals[1], prices(), 5), evaluate_signal_outcome(signals[2], prices(), 5)]
    result = model_performance_scorecard(signals, outcomes, model_id="model", model_version="v1")
    assert result["signal_count"] == 3
    assert result["direction_counts"] == {"bullish": 1, "neutral": 0, "bearish": 1, "abstain": 1}
    assert result["horizons"][5]["evaluable_count"] == 3
    assert result["horizons"][5]["directional_sample_count"] == 2
    assert result["horizons"][5]["directional_hit_rate"] == .5
