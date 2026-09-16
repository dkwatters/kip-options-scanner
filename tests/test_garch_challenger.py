from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from math import sqrt
from pathlib import Path
from types import SimpleNamespace
import pytest
from streamlit.testing.v1 import AppTest

from scripts.seed_garch_acceptance import synthetic_history, seed_acceptance
from src import garch_challenger as model
from src.garch_evaluation import forecast_scorecard
from src.garch_service import run_garch_research, evaluate_garch_history
from src.market_calendar import is_us_equity_trading_day
from src.observation_event_repository import ObservationEventRepository
from src.research_repository import ResearchRepositoryTarget
from src.signal_repository import SignalRepository
from src.signal_outcomes import PriceObservation, SignalOutcome, OutcomeFamily, OutcomeStatus, evaluate_signal_horizons
from src.signals import SignalDirection, SignalFamily
from src.technical_analysis import most_recent_completed_trading_session


@pytest.fixture(scope="module")
def history():
    return synthetic_history()


@pytest.fixture(scope="module")
def as_of(history):
    return date.fromisoformat(history["history"]["day"][501]["date"])


@pytest.fixture(scope="module")
def fitted(history, as_of):
    result=model.fit_garch("TEST",as_of,history,source="synthetic-test")
    assert result.status == "valid", result.diagnostics
    return result.signal


def fake_fit(**changes):
    fit=SimpleNamespace(convergence_flag=0,optimization_result=SimpleNamespace(message="success",nit=4),
                        params={"omega":.04,"alpha[1]":.08,"beta[1]":.88},conditional_volatility=[1.0],
                        forecast=lambda **kwargs:SimpleNamespace(variance=SimpleNamespace(values=[[1.0]*61])))
    for key,value in changes.items(): setattr(fit,key,value)
    return fit


def test_canonical_actual_library_fit_and_reproducibility(history,as_of,fitted):
    again=model.fit_garch("TEST",as_of,history,source="synthetic-test").signal
    assert fitted == again
    assert fitted.components["forecast_volatility_5d"] == pytest.approx(.16200353,rel=.005)
    assert fitted.components["persistence"] == pytest.approx(fitted.components["alpha"]+fitted.components["beta"])
    assert fitted.metadata["observation_count"] == 500
    assert fitted.metadata["library_version"] == "8.0.0"
    assert fitted.metadata["convergence_flag"] == 0
    assert fitted.signal_family is SignalFamily.VOLATILITY
    assert fitted.direction is SignalDirection.NOT_APPLICABLE
    assert fitted.conviction == 0 and fitted.confidence is None


@pytest.mark.parametrize("count,status",[(251,"insufficient_history"),(252,"valid"),(500,"valid")])
def test_training_minimum(history,as_of,monkeypatch,count,status):
    payload={"history":{"day":history["history"]["day"][500-count:501]}}
    monkeypatch.setattr(model,"_fit",lambda r:fake_fit())
    result=model.fit_garch("TEST",as_of,payload)
    assert result.status == status
    assert (result.signal is None) == (status != "valid")


@pytest.mark.parametrize("h",[5,20,60])
def test_forecast_aggregation_uses_steps_two_through_h_plus_one(h):
    result=model.aggregate_forecasts(range(1,62))
    assert result[f"forecast_volatility_{h}d"] == pytest.approx(sqrt(252*(h+3)/2)/100)


@pytest.mark.parametrize("day,cutoff",[("2024-07-04","2024-07-03"),("2024-07-05","2024-07-03"),
                                      ("2024-07-07","2024-07-05"),("2024-07-08","2024-07-05")])
def test_holiday_weekend_completed_cutoff(day,cutoff):
    day=date.fromisoformat(day)
    assert most_recent_completed_trading_session(day).isoformat() == cutoff
    payload={"history":{"day":[{"date":cutoff,"close":100},{"date":day.isoformat(),"close":999999}]}}
    assert model.completed_closes(payload,day) == [(date.fromisoformat(cutoff),100)]


def test_replay_excludes_same_day_and_all_future(history,as_of,fitted):
    payload=deepcopy(history)
    for row in payload["history"]["day"][501:]: row["close"]=float("nan")
    replay=model.fit_garch("TEST",as_of,payload,source="synthetic-test")
    assert replay.signal == fitted
    assert date.fromisoformat(fitted.metadata["training_end"]) < as_of


@pytest.mark.parametrize("mutation",["gap","duplicate","invalid","stale"])
def test_bad_completed_history_fails_without_forecast(history,as_of,mutation):
    payload=deepcopy(history); rows=payload["history"]["day"]
    if mutation=="gap": del rows[300]
    if mutation=="duplicate": rows.append(dict(rows[300]))
    if mutation=="invalid": rows[300]["close"]=float("nan")
    if mutation=="stale": del rows[500]
    result=model.fit_garch("TEST",as_of,payload)
    assert result.status == "provider_history_failure" and result.signal is None


@pytest.mark.parametrize("parameters,status",[
    ({"omega":-1,"alpha[1]":.1,"beta[1]":.8},"invalid_parameters"),
    ({"omega":.1,"alpha[1]":-.1,"beta[1]":.8},"invalid_parameters"),
    ({"omega":.1,"alpha[1]":.2,"beta[1]":.8},"nonstationary_or_near_boundary"),
    ({"omega":.1,"alpha[1]":.1,"beta[1]":.895},"nonstationary_or_near_boundary"),
    ({"omega":float("nan"),"alpha[1]":.1,"beta[1]":.8},"invalid_parameters")])
def test_parameter_rejection(history,as_of,monkeypatch,parameters,status):
    monkeypatch.setattr(model,"_fit",lambda r:fake_fit(params=parameters))
    result=model.fit_garch("TEST",as_of,history)
    assert result.status==status and result.signal is None
    assert "fitted_parameters" in result.diagnostics


@pytest.mark.parametrize("kind,status",[("raise","optimizer_failure"),("convergence","non_convergence"),("forecast","numerical_failure")])
def test_failure_diagnostics(history,as_of,monkeypatch,kind,status):
    def fit(r):
        if kind=="raise": raise RuntimeError("optimizer failed")
        if kind=="convergence": return fake_fit(convergence_flag=9)
        return fake_fit(conditional_volatility=[float("nan")])
    monkeypatch.setattr(model,"_fit",fit)
    result=model.fit_garch("TEST",as_of,history)
    assert result.status==status and result.signal is None


def test_constant_returns_do_not_fabricate_forecast(history,as_of):
    payload=deepcopy(history)
    for row in payload["history"]["day"]: row["close"]=100
    result=model.fit_garch("TEST",as_of,payload)
    assert result.status=="numerical_failure" and result.signal is None


def test_missing_dependency_is_an_explicit_failure(history, as_of, monkeypatch):
    from importlib.metadata import PackageNotFoundError

    def missing(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr(model, "version", missing)
    result = model.fit_garch("TEST", as_of, history)
    assert result.status == "dependency_failure" and result.signal is None


def test_extreme_positive_prices_cannot_escape_failure_policy(history, as_of, monkeypatch):
    payload = deepcopy(history)
    payload["history"]["day"][300]["close"] = 1e-300
    payload["history"]["day"][301]["close"] = 1e300
    monkeypatch.setattr(model, "_fit", lambda returns: fake_fit(convergence_flag=9))
    result = model.fit_garch("TEST", as_of, payload)
    assert result.status == "non_convergence" and result.signal is None


def test_outcome_refresh_caps_future_dates_and_preserves_forecast(tmp_path, history, fitted):
    calls = []
    repository = SignalRepository(ResearchRepositoryTarget("sqlite", sqlite_path=tmp_path/"refresh.sqlite"))
    repository.save_signal(fitted)
    client = SimpleNamespace(get_price_history=lambda *a, **k: (calls.append(k) or history))
    outcomes = evaluate_garch_history([fitted], client=client, repository=repository, through_date=date(2099, 1, 1))
    from datetime import datetime
    from zoneinfo import ZoneInfo
    expected = most_recent_completed_trading_session(datetime.now(ZoneInfo("America/New_York")).date())
    assert calls[0]["end"] == expected.isoformat()
    assert len(outcomes) == 3
    assert all(o.status is OutcomeStatus.EVALUATED for o in outcomes)
    assert repository.list_signals() == (fitted,)


def test_explicit_provider_depth_retry_and_observation_boundary(tmp_path,history,as_of):
    calls=[]
    client=SimpleNamespace(get_price_history=lambda *a,**k:(calls.append(k) or history))
    repository=SignalRepository(ResearchRepositoryTarget("sqlite",sqlite_path=tmp_path/"research.sqlite"))
    first=run_garch_research("TEST",as_of,client=client,repository=repository)
    retry=run_garch_research("TEST",as_of,client=client,repository=repository)
    assert first.signal == retry.signal and retry.status == "retry"
    assert len(calls)==1
    assert calls[0]["start"]==(as_of-timedelta(days=800)).isoformat()
    assert calls[0]["end"]==most_recent_completed_trading_session(as_of).isoformat()
    events=ObservationEventRepository(repository.target)
    assert events.get_comparison(first.signal.signal_id)[1]
    assert events.list_events()==()
    later=date.fromisoformat(history["history"]["day"][502]["date"])
    next_result=run_garch_research("TEST",later,client=client,repository=repository)
    assert next_result.signal is not None
    assert events.list_events()==()


def test_provider_failure(tmp_path,as_of):
    def fail(*args,**kwargs): raise RuntimeError("history unavailable")
    repository=SignalRepository(ResearchRepositoryTarget("sqlite",sqlite_path=tmp_path/"research.sqlite"))
    result=run_garch_research("TEST",as_of,client=SimpleNamespace(get_price_history=fail),repository=repository)
    assert result.status=="provider_history_failure" and repository.list_signals()==()


def test_outcomes_use_verified_future_sessions(history,as_of,fitted):
    observations=[PriceObservation(date.fromisoformat(r["date"]),r["close"]) for r in history["history"]["day"]]
    mature=evaluate_signal_horizons(fitted,observations,through_date=observations[-1].trading_date)
    assert all(o.status is OutcomeStatus.EVALUATED and o.outcome_family is OutcomeFamily.VOLATILITY for o in mature)
    assert [o.components["return_observation_count"] for o in mature]==[5,20,60]
    assert all(o.start_date==as_of.isoformat() for o in mature)
    immature=evaluate_signal_horizons(fitted,observations,through_date=as_of)
    assert all(o.status is OutcomeStatus.NOT_YET_ELIGIBLE for o in immature)
    missing=evaluate_signal_horizons(fitted,[o for i,o in enumerate(observations) if i!=503],through_date=observations[-1].trading_date)
    assert all(o.status is OutcomeStatus.MISSING_DATA for o in missing)


@pytest.mark.parametrize("actual,better",[(.2,True),(.3,False)])
def test_evaluator_honestly_reports_wins_and_losses(fitted,actual,better):
    signal=replace(fitted,components={**fitted.components,"forecast_volatility_5d":.2,"realized_volatility_20d":.3})
    outcome=SignalOutcome(signal.signal_id,5,OutcomeStatus.EVALUATED,outcome_family=OutcomeFamily.VOLATILITY,
                          components={"realized_volatility":actual})
    score=forecast_scorecard([signal],[outcome]); h=score["horizons"][5]
    assert h["mae"]==pytest.approx(abs(.2-actual))
    assert h["rmse"]==pytest.approx(abs(.2-actual))
    assert h["bias"]==pytest.approx(.2-actual)
    assert h["baseline_mae"]==pytest.approx(abs(.3-actual))
    assert h["baseline_rmse"]==pytest.approx(abs(.3-actual))
    assert (h["mae_difference"]<0)==better
    assert h["sample_count"]==1 and h["coverage"]==1
    assert "preliminary" in h["sample_label"]
    assert score["horizons"][20]["sample_count"]==0


def test_metrics_pair_coverage_and_model_version_filter(fitted):
    unobserved=replace(fitted,signal_id="second")
    excluded=replace(fitted,signal_id="other",model_version="future-version")
    actual=SignalOutcome(fitted.signal_id,5,OutcomeStatus.EVALUATED,outcome_family=OutcomeFamily.VOLATILITY,components={"realized_volatility":.2})
    score=forecast_scorecard([fitted,unobserved,excluded],[actual,replace(actual,signal_id="other")])
    assert score["horizons"][5]["sample_count"]==1
    assert score["horizons"][5]["coverage"]==.5


def test_synthetic_acceptance_coexistence_and_retry(tmp_path):
    database=tmp_path/"acceptance.sqlite"
    seed_acceptance(database)
    seed_acceptance(database)
    repository=SignalRepository(ResearchRepositoryTarget("sqlite",sqlite_path=database))
    assert len(repository.list_signals())==4 and len(repository.list_outcomes())==6
    assert {s.model_id for s in repository.list_signals()}=={"garch-volatility","volatility-context"}
    assert ObservationEventRepository(repository.target).list_events()==()


def test_model_lab_garch_rendering_and_filtering(tmp_path,monkeypatch):
    database=tmp_path/"ui.sqlite"; seed_acceptance(database)
    monkeypatch.setenv("RESEARCH_REPOSITORY_BACKEND","sqlite")
    monkeypatch.setenv("RESEARCH_SQLITE_PATH",str(database)); monkeypatch.setenv("RCE_PROVIDER","mock")
    app=AppTest.from_file(Path(__file__).parents[1]/"app.py",default_timeout=30).run()
    next(w for w in app.sidebar.radio if w.label=="Navigation").set_value("Model Lab"); app.run()
    assert not app.exception
    frames=[f.value for f in app.dataframe]
    assert any("forecast_volatility_60d" in f.columns for f in frames)
    assert any("mae" in f.columns and "sample_count" in f.columns for f in frames)
    selector=next(w for w in app.selectbox if w.label=="Model and version")
    selector.set_value(("volatility-context","volatility-context-v0.1")); app.run()
    assert not app.exception
    assert not any("forecast_volatility_60d" in f.value.columns for f in app.dataframe)
