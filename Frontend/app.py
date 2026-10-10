"""Run with: python -m streamlit run app.py"""
import streamlit as st
from config import DEMO_MODE
from services.demo_data import initial_state
from services.planner import perform_action
from ui.chat import render_chat
from ui.commitments import render_commitments
from ui.sidebar import render_sidebar
from ui.tasks import render_tasks
from ui.week_calendar import render_calendar

st.set_page_config(page_title="StudyFlow", page_icon="📅", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stButton button {font-family: Roboto, "Google Sans", Arial, sans-serif;}
.block-container {padding-top: 1.6rem; max-width: 1500px;}
.brand {display:flex; align-items:center; gap:10px; font-size:22px; color:#3c4043; margin-bottom:4px;}
.brand b {font-weight:500;}
.cal-title {font-size:20px; color:#3c4043; white-space:nowrap;}
.coach {display:flex; align-items:center; gap:10px; margin-bottom:8px;}
.coach .avatar {width:38px; height:38px; border-radius:50%; background:#1a73e8; color:#fff;
                display:flex; align-items:center; justify-content:center; font-size:20px;}
.coach span {color:#70757a; font-size:13px;}
.chip {display:flex; align-items:center; gap:8px; font-size:12.5px; margin:4px 0; color:#3c4043;}
.chip span {width:12px; height:12px; border-radius:3px; flex:none; display:inline-block;}
.task {display:flex; gap:10px; align-items:flex-start; padding:8px 0; border-bottom:1px solid #f1f3f4;}
.task .dot {width:10px; height:10px; border-radius:50%; margin-top:6px; flex:none;}
.task .badge {color:#fff; font-size:11px; padding:1px 8px; border-radius:10px; margin-left:6px;}
.task .sub {color:#70757a; font-size:12.5px;}
</style>
""", unsafe_allow_html=True)

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
    if action["type"] == "reset_demo":
        st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": result["reply"]})
    st.session_state.plan = result["state"]
    st.session_state.revision += 1
    st.rerun()


plan = st.session_state.plan
profile = plan.get("profile") or {}
first_name = (profile.get("name") or "").split(" ")[0] or None

render_sidebar(plan, dispatch)

st.markdown("<div class='brand'>📅 <b>StudyFlow</b><span style='color:#70757a;font-size:15px'>"
            "&nbsp;· plan your work around your life</span></div>", unsafe_allow_html=True)
if DEMO_MODE:
    st.warning("FRONTEND DEMO — fictional data, no AI or automatic scheduling. Changes last for this browser session only.")

left, right = st.columns([1, 2.5], gap="large")
with left:
    render_chat(st.session_state.messages, dispatch, profile.get("bot_name", "Sparky"), first_name)
with right:
    render_calendar(plan, dispatch)
    for warning in plan["warnings"]:
        st.warning(warning)
    tasks_tab, commitments_tab = st.tabs(["📌 Deadlines", "🔒 Fixed commitments"])
    with tasks_tab:
        render_tasks(plan, dispatch, st.session_state.revision)
    with commitments_tab:
        render_commitments(plan, dispatch)
