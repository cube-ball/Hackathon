from datetime import date, datetime, time
import streamlit as st


def render_commitments(state, dispatch):
    st.caption("Add classes, shifts, commute or sleep as dated blocks. Recurring rules belong in the backend later.")
    for item in state["commitments"]:
        st.write(f"**{item['title']}**")
        st.caption(f"{item['start']} → {item['end']}")
    with st.expander("Add unavailable time"):
        with st.form("commitment_form"):
            title = st.text_input("Commitment name")
            start_date = st.date_input("Start date", value=date.today())
            start_time = st.time_input("Start time", value=time(9))
            end_date = st.date_input("End date", value=date.today())
            end_time = st.time_input("End time", value=time(10))
            save = st.form_submit_button("Block time")
        if save:
            start = datetime.combine(start_date, start_time)
            end = datetime.combine(end_date, end_time)
            if not title.strip():
                st.error("Enter a commitment name.")
            elif end <= start:
                st.error("End must be after start. For overnight sleep, choose the next day as the end date.")
            else:
                dispatch({"type": "add_commitment", "commitment": {"title": title.strip(), "start": start.isoformat(), "end": end.isoformat()}})
