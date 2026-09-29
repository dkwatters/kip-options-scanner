"""Deterministic synthetic developer evidence; no live prices or benchmark freeze."""
import argparse
from datetime import date, timedelta
from math import exp, sqrt
from pathlib import Path
from random import Random
from time import perf_counter
import json
from src.market_calendar import is_us_equity_trading_day
from src.garch_challenger import fit_garch
from src.garch_evaluation import forecast_scorecard
from src.signal_repository import SignalRepository
from src.research_repository import ResearchRepositoryTarget
from src.signal_outcomes import PriceObservation, evaluate_signal_horizons
from src.observation_event_repository import ObservationEventRepository
from src.scheduled_observation_engine import observe_signal_changes
from src.volatility_context import DailyBar, calculate_volatility_context
from src.signals import volatility_context_signal


def synthetic_history(seed=404, count=562):
    rng=Random(seed); variance=1.0; residual=0.0; close=100.0
    # Burn-in is solely fixture construction, never a production model feature.
    for _ in range(300):
        variance=.04+.08*residual**2+.88*variance
        residual=sqrt(variance)*rng.gauss(0,1)
    days=[]; day=date(2022,1,3)
    while len(days)<count:
        if is_us_equity_trading_day(day):
            variance=.04+.08*residual**2+.88*variance
            residual=sqrt(variance)*rng.gauss(0,1)
            close*=exp(residual/100)
            days.append({"date":day.isoformat(),"close":close,"high":close*1.01,"low":close*.99})
        day+=timedelta(days=1)
    return {"history":{"day":days}}


def seed_acceptance(database):
    repository=SignalRepository(ResearchRepositoryTarget("sqlite",sqlite_path=Path(database)))
    events=ObservationEventRepository(repository.target)
    latencies=[]
    for ticker,seed in (("SYNTH-A",404),("SYNTH-B",902)):
        payload=synthetic_history(seed)
        as_of=date.fromisoformat(payload["history"]["day"][501]["date"])
        start=perf_counter()
        result=fit_garch(ticker,as_of,payload,source=f"synthetic-developer-fixture:{seed}")
        latencies.append({"ticker":ticker,"seconds":perf_counter()-start,"status":result.status})
        if result.signal is None:
            raise RuntimeError(json.dumps(result.diagnostics))
        inserted=repository.save_signal(result.signal)
        observe_signal_changes((result.signal,),signal_repository=repository,event_repository=events)
        observations=[PriceObservation(date.fromisoformat(r["date"]),r["close"]) for r in payload["history"]["day"]]
        repository.save_outcomes(evaluate_signal_horizons(result.signal,observations,through_date=observations[-1].trading_date,
                                                          evaluated_at=observations[-1].trading_date.isoformat()))
        bars=[DailyBar(date.fromisoformat(r["date"]),r["high"],r["low"],r["close"]) for r in payload["history"]["day"][:501]]
        context=volatility_context_signal({"ticker":ticker,"technical_timestamp":as_of.isoformat(),
                                          "scan_id":f"synthetic-garch-acceptance:{seed}","_volatility_context":calculate_volatility_context(bars)})
        repository.save_signal(context)
        observe_signal_changes((context,),signal_repository=repository,event_repository=events)
    return {"source":"SYNTHETIC developer test data, not live market evidence", "runs":latencies,
            "scorecard":forecast_scorecard(repository.list_signals(),repository.list_outcomes())}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(seed_acceptance(args.database),indent=2))

if __name__=="__main__": main()
