"""Run with: python -m streamlit run app.py"""
import streamlit as st
from config import DEMO_MODE
from services.demo_data import initial_state
from services.planner import perform_action
from ui.chat import render_chat
from ui.schedule import render_schedule
from ui.tasks import render_tasks
from ui.commitments import render_commitments

st.set_page_config(page_title="StudyFlow", page_icon="📅", layout="wide")
if "plan" not in st.session_state:
    if DEMO_MODE:
        st.session_state.plan = initial_state()
        st.session_state.messages = []
    else:
        # Connected mode: start from the backend's demo student (or the saved plan)
        # and open the chat with a greeting from the personal coach.
        from backend_bridge import bot_intro, initial_state as backend_initial_state
        st.session_state.plan = backend_initial_state()
        st.session_state.messages = [{"role": "assistant", "content": bot_intro(st.session_state.plan)}]
    st.session_state.revision = 0


def dispatch(action):
    """Only replace displayed data after a successful service response."""
    try:
        with st.spinner("Updating your plan…"):
            result = perform_action(action, st.session_state.plan)
    except Exception:
        st.error("The planner could not complete that request. Your plan is unchanged. Try again or ask your backend teammate to check the service.")
        return
    if action["type"] == "chat":
        st.session_state.messages.append({"role": "user", "content": action["message"]})
    st.session_state.messages.append({"role": "assistant", "content": result["reply"]})
    st.session_state.plan = result["state"]
    st.session_state.revision += 1
    st.rerun()

st.title("StudyFlow")
st.caption("Plan your work around your life.")
if DEMO_MODE:
    st.warning("FRONTEND DEMO — fictional data, no AI or automatic scheduling. Changes last for this browser session only.")
else:
    st.caption("Connected mode · save/load persistence must be supplied by your backend.")
left, right = st.columns([1, 2], gap="large")
with left:
    render_chat(st.session_state.messages, dispatch)
with right:
    render_schedule(st.session_state.plan, dispatch)
    for warning in st.session_state.plan["warnings"]:
        st.warning(warning)
    tasks_tab, commitments_tab = st.tabs(["Tasks", "Fixed commitments"])
    with tasks_tab:
        render_tasks(st.session_state.plan, dispatch, st.session_state.revision)
    with commitments_tab:
        render_commitments(st.session_state.plan, dispatch)
