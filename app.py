from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from src.scanner import ScannerNotImplementedError, run_scan
from src.universe import UniverseError, load_universe

ROOT=Path(__file__).resolve().parent
def main():
 load_dotenv(ROOT / ".env"); st.set_page_config(page_title="Kip Options Scanner",layout="wide"); st.title("Kip Options Scanner"); st.caption("Phase 1A · Research tool only · No trading or order placement")
 with st.sidebar:
  path=st.text_input("Universe CSV",value=str(ROOT / "data" / "universe_default.csv")); st.info("Scanning is intentionally unavailable in Phase 1A.")
 try: universe=load_universe(path)
 except UniverseError as error: st.error("Unable to load universe: " + str(error)); universe=[]
 st.subheader("Universe")
 if universe: st.dataframe([x.to_display_dict() for x in universe],hide_index=True,use_container_width=True)
 else: st.warning("No enabled symbols are available.")
 if st.button("Run scan",disabled=not universe):
  try: run_scan(universe)
  except ScannerNotImplementedError as error: st.info(str(error))
 st.subheader("Results"); st.caption("Results will appear here when scanning is implemented in a later phase.")
if __name__ == "__main__": main()
