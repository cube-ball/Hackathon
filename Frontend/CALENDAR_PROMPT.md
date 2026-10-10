# Prompt: Google-Calendar-style frontend

> **Status: DONE.** The calendar UI is now built (`ui/week_calendar.py`, `ui/calendar_html.py`,
> `ui/sidebar.py`, updated `app.py`, `ui/chat.py`, `ui/tasks.py`). It uses a built-in HTML time grid,
> so no extra package is needed. Keep this prompt only as a reference for further changes.

Who uses this: the frontend person.
Where: Claude Code or Codex, started inside `~/Hackathon` (the repo root), on a new branch.
First run in Terminal: `cd ~/Hackathon && git checkout main && git pull && git checkout -b frontend/calendar`
Do this only after the `backend/planner` pull request is merged into `main` (the prompt needs it).
Then paste everything between the lines below.

---

You are working on StudyFlow, a Streamlit app in the `Frontend/` folder of this repo. A student talks to a
personal study-coach chatbot and gets a strict weekly study timetable. The backend is already finished in
`backend/` and is reached ONLY through `Frontend/backend_bridge.py`. Do not edit anything in `backend/` or
`backend_bridge.py`, and do not write any scheduling logic in the frontend.

Goal: redesign the UI so it looks and feels like Google Calendar's week view, with the coach chat beside it.

Backend functions available (import from `backend_bridge`):
- `initial_state()` -> full state for the fictional demo student (profile, tasks, commitments, sessions,
  warnings, preferences). Use it on first load instead of the empty state in app.py.
- `bot_intro(state)` -> markdown greeting from the coach. Make it the first assistant chat message.
- `week_events(state)` -> list of events already in FullCalendar format:
  `{"id","title","start","end","backgroundColor","borderColor","textColor","extendedProps"}`.
  `extendedProps` has: `source` ("commitment" or "session"), `kind` (lecture/lab/tutorial/commute/work/
  personal/study), `kind_label`, `module`, `location`, `status` (sessions: planned/completed/missed),
  `task_id`, `deadline`, `reason`, `locked`.
- `legend(state)` -> list of `(label, hex_colour)` for a colour key.
- All changes still go through the existing `dispatch(action)` in app.py, which calls
  `services/planner.py -> perform_action`. Actions: `chat`, `save_task`, `add_commitment`,
  `session_status`, and the new `{"type": "reset_demo"}`.
- `state["profile"]` has `name`, `programme`, `university`, `bot_name`, `modules` (code, title, colour),
  `commute`, `sleep`, `job`, `goals`, `fictional`.

Build this:
1. Calendar: use the `streamlit-calendar` package (`from streamlit_calendar import calendar`; add
   `streamlit-calendar` to `Frontend/requirements.txt`). Pass `events=week_events(state)` and options:
   `initialView: "timeGridWeek"`, `firstDay: 1` (Monday), `slotMinTime: "07:00:00"`,
   `slotMaxTime: "23:30:00"`, `allDaySlot: False`, `nowIndicator: True`, `editable: False`,
   `selectable: False`, 24-hour times (`eventTimeFormat` and `slotLabelFormat` with `hour12: False`),
   `headerToolbar: {"left": "prev,next today", "center": "title", "right": "timeGridDay,timeGridWeek,dayGridMonth"}`,
   height about 760. Give it `key=f"calendar_{st.session_state.revision}"` so it redraws after every update.
   Use `custom_css` for a Google Calendar look: white background, light grey grid lines, rounded event
   chips with small bold titles, Google-style blue today circle, sans-serif font.
2. Event details: when the calendar returns `callback == "eventClick"`, store the clicked event id in
   `st.session_state` and show a details card under the calendar: title, day and time, kind, module,
   location, and for study sessions the deadline and the reason. For a study session with status
   `planned`, show "Mark completed" and "Mark missed" buttons that dispatch
   `{"type": "session_status", "session_id": <id>, "status": "completed" | "missed"}`.
3. Layout (`layout="wide"`): left column (about 1/3) is the coach. Header with the bot name and
   "Personal coach for <student first name>", a small profile card (programme, university, modules as
   coloured chips from `legend(state)`), then the chat (keep `ui/chat.py`'s form, change the placeholder
   to "Ask <bot_name>…", e.g. "I'm wrecked Tuesday" / "What's on tomorrow?"). Right column (2/3) is the
   calendar. Below the calendar: warnings, then tabs "Deadlines" (tasks sorted by deadline with module
   colour dot, priority badge, minutes left, reason; keep the add/edit task form) and "Fixed
   commitments" (keep the existing form). Add a sidebar button "Reset demo week" that dispatches
   `{"type": "reset_demo"}`.
4. Show a small caption "Demo student: fictional data" whenever `state["profile"]["fictional"]` is true.
5. If `streamlit-calendar` fails to install or render, fall back to a hand-made week grid: an HTML/CSS
   time grid (07:00-23:30, Monday-Sunday columns, events absolutely positioned by start/end time, using
   the event colours) rendered with `st.components.v1.html`. Keep click-to-select via a selectbox of the
   week's events in that case.

Rules:
- Keep `DEMO_MODE = False` in config.py. Keep `services/planner.py` as the only path to the backend.
- Don't put any API keys in the frontend. Don't commit `.venv/`.
- Keep the existing snake_case field names.

When finished:
- Run `cd Frontend && .venv/bin/python -m pip install -r requirements.txt && .venv/bin/python -m streamlit run app.py`
  and check: the week shows lectures, labs, commutes, shifts and lighter-coloured study blocks; prev/next
  and Day/Week/Month work; clicking a study block shows details and marking it completed reduces the task's
  minutes; sending a chat message updates the calendar; "Reset demo week" restores everything.
- Show me `git status`, make sure no .env or .venv files are included, then commit with a clear message
  and push the branch `frontend/calendar`, and give me the pull-request link.

---
