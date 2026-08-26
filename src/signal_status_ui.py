"""Shared Streamlit presentation for derived-Signal persistence status."""
from __future__ import annotations

import streamlit as st


def render_signal_persistence_failure(detail: str) -> None:
    st.warning(
        "Analysis archived, but derived Signals were not persisted. Details: "
        + detail
    )
