"""Connects the Streamlit UI to the backend package in ../backend.

The frontend calls handle_action(action, state); see BACKEND_CONTRACT.md.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.bridge import (  # noqa: E402,F401
    account_status, bot_intro, handle_action, initial_state, legend, load_state, week_events)
