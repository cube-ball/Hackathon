from datetime import date, datetime, timedelta
import streamlit as st


def render_schedule(state, dispatch):
    st.subheader("Your weekly plan")
    st.caption("Times are local to Europe/Dublin. This starter uses a weekly agenda, not a drag-and-drop time grid.")
    items = state["commitments"] + state["sessions"]
    earliest = min((datetime.fromisoformat(x["start"]).date() for x in items), default=date.today())
    selected = st.date_input("Week containing", value=earliest)
    monday = selected - timedelta(days=selected.weekday())
    # Four columns, then three: more readable than seven narrow columns.
    for offset, count in ((0, 4), (4, 3)):
        for index, column in enumerate(st.columns(count)):
            day = monday + timedelta(days=offset + index)
            with column:
                st.markdown(f"**{day:%a %d %b}**")
                events = sorted([x for x in items if datetime.fromisoformat(x["start"]).date() <= day <= datetime.fromisoformat(x["end"]).date()], key=lambda x: x["start"])
                if not events:
                    st.caption("No planned events")
                for item in events:
                    start, end = datetime.fromisoformat(item["start"]), datetime.fromisoformat(item["end"])
                    with st.container(border=True):
                        st.caption(f"{start:%a %H:%M} – {end:%a %H:%M}")
                        st.write(item["title"])
                        st.caption(item.get("status", "Fixed commitment"))
    planned = [s for s in state["sessions"] if s["status"] == "planned"]
    if planned:
        with st.expander("Update a study session"):
            by_id = {s["id"]: s for s in planned}
            chosen = st.selectbox("Session", list(by_id), format_func=lambda sid: f"{by_id[sid]['title']} · {by_id[sid]['start']}")
            done, missed = st.columns(2)
            if done.button("Mark completed"):
                dispatch({"type": "session_status", "session_id": chosen, "status": "completed"})
            if missed.button("Mark missed"):
                dispatch({"type": "session_status", "session_id": chosen, "status": "missed"})
