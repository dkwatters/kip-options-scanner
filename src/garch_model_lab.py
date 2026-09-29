"""Explicit GARCH research controls and paired forecast evidence."""
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import streamlit as st
from src.garch_evaluation import forecast_scorecard
from src.garch_service import run_garch_research, evaluate_garch_history
from src.tradier_client import TradierClient
from src.technical_observation_service import safe_diagnostic_detail


def render_garch_controls(repository):
    with st.expander("GARCH Challenger research run"):
        st.caption("Experimental, non-directional research. Runs only on request; existing daily forecasts are never refitted. Failed fits create no Signal.")
        with st.form("garch_research_run"):
            ticker = st.text_input("GARCH security", value="NVDA")
            as_of = st.date_input("GARCH analysis date", value=datetime.now(ZoneInfo("America/New_York")).date(),
                                  max_value=datetime.now(ZoneInfo("America/New_York")).date())
            submitted = st.form_submit_button("Generate GARCH forecast")
        if submitted:
            try:
                with st.spinner("Fetching completed history and fitting GARCH"):
                    result = run_garch_research(ticker, as_of, client=TradierClient(), repository=repository)
                st.session_state.garch_last_run = {"status": result.status, **result.diagnostics}
                if result.signal is not None:
                    st.rerun()
            except Exception as error:
                st.session_state.garch_last_run = {"status": "persistence_or_provider_failure", "error": safe_diagnostic_detail(error)}
        if "garch_last_run" in st.session_state:
            diagnostics = st.session_state.garch_last_run
            if diagnostics["status"] not in ("valid", "retry"):
                st.warning("No new usable GARCH forecast: " + diagnostics["status"])
            else:
                st.success("GARCH forecast available in the Volatility family.")
            st.json(diagnostics)


def render_garch_evidence(signals, outcomes, repository):
    st.subheader("GARCH Challenger")
    st.caption("Experimental zero-mean GARCH(1,1). Annualized volatility is shown as a decimal. RV20 is the frozen persistence comparator; lower error does not establish trading value.")
    rows=[]
    for signal in signals:
        row={"Security":signal.ticker,"As of":signal.as_of,"Direction":"N/A","Conviction":0,
             "Training start":signal.metadata.get("training_start"),"Training end":signal.metadata.get("training_end"),
             "Returns":signal.metadata.get("observation_count"),"Status":signal.metadata.get("status"),
             "Data quality":signal.metadata.get("data_quality"),"Source":signal.metadata.get("source"),
             "Signal ID":signal.signal_id}
        row.update({name:signal.components.get(name) for name in
                    ("current_conditional_volatility","forecast_volatility_5d","forecast_volatility_20d",
                     "forecast_volatility_60d","omega","alpha","beta","persistence","realized_volatility_20d")})
        rows.append(row)
    st.dataframe(pd.DataFrame(rows),hide_index=True)
    score=forecast_scorecard(signals,outcomes)
    st.subheader("Paired forecast errors")
    st.caption("Same actuals and same paired sample for both models. Negative MAE difference favors GARCH. Small samples are preliminary; overlapping windows are not independent trials.")
    st.caption("Coverage is evaluated pairs divided by persisted GARCH Signals. Failed fits are excluded, so this is not coverage of all attempted forecasts or evidence of superiority across all market conditions.")
    st.dataframe(pd.DataFrame([{"Horizon":h,**metrics} for h,metrics in score["horizons"].items()]),hide_index=True)
    if score["errors"]:
        st.dataframe(pd.DataFrame(score["errors"]),hide_index=True)
    else:
        st.info("No mature paired forecast errors yet. Future Outcomes must contain every required completed session.")
    st.subheader("Volatility Outcome ledger")
    if outcomes:
        st.dataframe(pd.DataFrame([{"Signal ID":o.signal_id,"Horizon":o.horizon_trading_days,"Status":o.status.value,
                                    "Start":o.start_date,"End":o.end_date,"Actual volatility":o.components.get("realized_volatility"),
                                    "Error":o.error} for o in outcomes]),hide_index=True)
    with st.expander("Refresh GARCH Outcomes from provider history"):
        choices={s.signal_id:s for s in signals}
        chosen=st.multiselect("Forecasts to evaluate",list(choices),format_func=lambda key:f"{choices[key].ticker} | {choices[key].as_of}")
        if st.button("Evaluate completed volatility Outcomes",disabled=not chosen):
            try:
                evaluate_garch_history([choices[key] for key in chosen],client=TradierClient(),repository=repository)
                st.rerun()
            except Exception as error:
                st.error("Outcome refresh failed: " + safe_diagnostic_detail(error))
    with st.expander("Raw GARCH fitting diagnostics"):
        st.json([{"signal_id":s.signal_id,"components":dict(s.components),"metadata":dict(s.metadata)} for s in signals])
    st.subheader("Recent Observation Events")
    st.info("No GARCH transition rules are defined. Numeric forecast changes do not create Observation Events.")
