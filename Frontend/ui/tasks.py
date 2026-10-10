from datetime import date, datetime, time, timedelta
import streamlit as st


PRIORITY_COLOURS = {"Overdue": "#d93025", "High": "#d93025", "Medium": "#f29900", "Low": "#188038", "Done": "#5f6368"}


def render_tasks(state, dispatch, revision):
    colours = {m["code"]: m.get("colour", "#1a73e8") for m in (state.get("profile") or {}).get("modules", [])}
    if not state["tasks"]:
        st.caption("No deadlines yet. Tell the coach about one, or add it below.")
    for task in sorted(state["tasks"], key=lambda t: t["deadline"]):
        due = datetime.fromisoformat(task["deadline"])
        dot = colours.get(task.get("module"), "#1a73e8")
        badge = PRIORITY_COLOURS.get(task.get("priority"), "#5f6368")
        hours = task["remaining_minutes"] / 60
        st.markdown(
            f"<div class='task'><span class='dot' style='background:{dot}'></span>"
            f"<div><b>{task['title']}</b> <span class='badge' style='background:{badge}'>{task.get('priority') or '–'}</span>"
            f"<br><span class='sub'>Due {due:%a %d %b, %H:%M} · {hours:.1f} h left · {task.get('reason', '')}</span></div></div>",
            unsafe_allow_html=True)
    with st.expander("Add or edit a task"):
        choices = {t["id"]: t for t in state["tasks"]}
        chosen = st.selectbox("Task", ["new"] + list(choices), format_func=lambda x: "Add new task" if x == "new" else choices[x]["title"])
        current = choices.get(chosen, {})
        deadline = datetime.fromisoformat(current["deadline"]) if current else datetime.combine(date.today()+timedelta(days=3), time(17))
        # Revision key prevents old form values lingering after backend updates.
        with st.form(f"task_{chosen}_{revision}"):
            title = st.text_input("Task title", value=current.get("title", ""))
            due_date = st.date_input("Deadline date", value=deadline.date())
            due_time = st.time_input("Deadline time", value=deadline.time())
            minutes = st.number_input("Minutes of work remaining", min_value=0, max_value=10000, value=current.get("remaining_minutes", 60), step=15)
            save = st.form_submit_button("Save task")
        if save:
            if not title.strip():
                st.error("Enter a task title.")
            else:
                task = {"title": title.strip(), "deadline": datetime.combine(due_date, due_time).isoformat(), "remaining_minutes": int(minutes)}
                if chosen != "new":
                    task["id"] = chosen
                dispatch({"type": "save_task", "task": task})
