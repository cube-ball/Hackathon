"""Sidebar: who the planner is for, module colours, plan status and demo controls."""
import streamlit as st

try:
    from backend_bridge import account_status
except ImportError:
    account_status = None


def render_sidebar(state, dispatch):
    profile = state.get("profile") or {}
    with st.sidebar:
        st.markdown("### 🎓 Student")
        if profile:
            st.markdown(f"**{profile.get('name', 'Student')}**  \n{profile.get('programme', '')}  \n"
                        f"{profile.get('university', '')}")
            if profile.get("fictional"):
                st.caption("Demo student: fictional data.")
            if profile.get("goals"):
                st.caption(f"Goal: {profile['goals']}")
            st.markdown("#### Modules")
            chips = "".join(
                f"<div class='chip'><span style='background:{m.get('colour', '#1a73e8')}'></span>"
                f"<b>{m['code']}</b>&nbsp;{m['title']}</div>" for m in profile.get("modules", []))
            st.markdown(chips, unsafe_allow_html=True)
            st.markdown(
                "<div class='chip'><span style='background:#9aa0a6'></span>Commute</div>"
                "<div class='chip'><span style='background:#616161'></span>Work</div>"
                "<div class='chip'><span style='background:#33b679'></span>Personal</div>"
                "<div class='chip'><span style='background:#e8f0fe;border:2px solid #1a73e8'></span>"
                "Study session (light = planned)</div>", unsafe_allow_html=True)
        else:
            st.caption("No student profile loaded.")

        st.markdown("#### Plan")
        status = None
        if account_status:
            try:
                status = account_status()
            except Exception:
                status = None
        if status:
            if status["tier"] == "pro":
                st.success("Semester Pass: unlimited AI updates")
            else:
                st.info(f"Free plan: {status['updates_remaining']} AI update(s) left")
                if st.button("⭐ Get Semester Pass (€9)", type="primary"):
                    dispatch({"type": "chat", "message": "upgrade"})
        st.divider()
        if st.button("↺ Reset demo week"):
            dispatch({"type": "reset_demo"})
