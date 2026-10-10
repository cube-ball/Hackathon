"""Connects the Streamlit UI to the backend package in ../backend.

The frontend calls handle_action(action, state); see BACKEND_CONTRACT.md.
"""
import os
import sys
from pathlib import Path

# On Streamlit Community Cloud, keys live in the app's Secrets settings.
# Copy top-level secrets into environment variables before the backend reads them.
try:
    import streamlit as st
    for _key, _value in st.secrets.items():
        if isinstance(_value, str):
            os.environ.setdefault(_key, _value)
except Exception:  # no secrets file locally is fine: keys come from the terminal or backend/.env
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.bridge import (  # noqa: E402,F401
    account_status, bot_intro, handle_action, initial_state, legend, load_state, week_events)
