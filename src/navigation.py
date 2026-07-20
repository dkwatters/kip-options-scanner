"""Streamlit-safe navigation handoffs for the app's widget-backed sidebar."""

from __future__ import annotations

import streamlit as st


SELECTED_PAGE_KEY = "selected_page"
PENDING_SELECTED_PAGE_KEY = "pending_selected_page"


def apply_pending_navigation() -> str | None:
    """Apply a requested page before the selected-page widget is instantiated."""
    pending_page = st.session_state.pop(PENDING_SELECTED_PAGE_KEY, None)
    if pending_page is not None:
        st.session_state[SELECTED_PAGE_KEY] = pending_page
    return pending_page


def request_navigation(page_name: str) -> None:
    """Queue a page change for the next run without mutating widget-owned state."""
    st.session_state[PENDING_SELECTED_PAGE_KEY] = page_name
    st.rerun()
