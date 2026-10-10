# StudyFlow frontend: start here

A runnable Python/Streamlit frontend starter. It is not a complete AI scheduler.
Demo mode uses fictional data and performs local edits. It does not call OpenRouter,
understand chat, generate plans, or automatically replan. This does not by itself
meet the hackathon AI criterion. It uses an agenda rather than a time-grid calendar.

## 1. Put the files in your shared project

Extract the ZIP. Copy the whole `student_frontend` folder into your cloned
Hackathon repository. Do not overwrite your teammate's files. Open that repository
in VS Code. All terminal commands below start INSIDE `student_frontend`.

## 2. Create an environment on Windows

Open Terminal > New Terminal in VS Code, then:

```powershell
cd student_frontend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

If `python` is not recognised but `py` works, use `py -m venv .venv` for the
creation step. The explicit environment path avoids PowerShell activation-policy
problems. In VS Code select `.venv` through Python: Select Interpreter.
Open the address printed by Streamlit. Keep the terminal running; Ctrl+C stops it.
Save a changed Python file and allow Streamlit to rerun it.

Mac/Linux equivalent:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

## 3. Learn the files in this order

| File | Your responsibility |
| --- | --- |
| app.py | Page layout, session state, dispatching actions and showing errors |
| ui/chat.py | Message input, validation and conversation display |
| ui/schedule.py | Seven-day agenda and completed/missed session controls |
| ui/tasks.py | Task list and add/edit form |
| ui/commitments.py | Unavailable-time display and form, including overnight blocks |
| services/demo_data.py | Fictional sample data; learn the shared field names |
| services/planner.py | The one connection point between interface and backend |
| config.py | Demo-mode switch |
| requirements.txt | Packages installed by every teammate |
| .gitignore | Excludes local environments, database files and secrets |
| ui/__init__.py and services/__init__.py | Empty files marking Python packages |

Read app.py first. `st.columns` divides the page. Each UI file draws one section.
Streamlit reruns the script on interaction. `st.session_state` keeps this browser
session's plan and chat between reruns. It is NOT durable database storage: a new
browser session/reload may reset it. Do not present it as a saved account.

## 4. Test the frontend before connecting AI

1. Confirm the fictional week and clear demo label appear.
2. Add a task through Tasks > Add or edit a task.
3. Correct its deadline and remaining time. Stale planned sessions are removed.
4. Add a work shift. A clashing demo study session is removed, not magically moved.
5. Mark a study session missed; verify unfinished work is flagged as unscheduled.
6. Submit an empty message and an end time before the start: helpful errors appear.
7. Send a chat message: it must explicitly say AI is not connected.

## 5. Agree the backend function now

See BACKEND_CONTRACT.md. Give it to your backend teammate before they implement
something incompatible. Keep this starter's snake_case field names consistently.
They differ from the earlier illustrative camelCase chat examples.
Your teammate supplies `backend_bridge.py` beside app.py, exporting:

```python
def handle_action(action: dict, state: dict) -> dict:
    # Validate input; call AI where needed; schedule; return complete new state.
    ...
```

Change DEMO_MODE to False in config.py only after that function exists.
No separate FastAPI server is required. If a server already exists, implement an
adapter in backend_bridge.py instead of rewriting the teammate's backend.
No AI or Stripe keys should be pasted into UI source. Keep secrets out of Git.

## 6. What your teammate implements

- OpenRouter request, structured extraction, clarification and priorities.
- Scheduling, deadlines, overlaps, sleep/commute protection and overload detection.
- Replanning missed sessions, while never reopening completed work.
- Persistent load/save if needed. Add load_state() at app initialisation and save
  accepted state server-side. Demo session state is not the final database.
- Any Stripe checkout and verified entitlement flow (optional bonus).

## 7. Styling and scope

Use Streamlit defaults first. This starter does not need JavaScript, Node or React.
It intentionally avoids external calendar packages and fragile custom CSS.
The agenda groups dated blocks by day. Overnight blocks appear on both dates.
It isn't positioned proportionally by hour and has no drag/drop.
Keep recurring timetable imports, resources, uploads and logins for later.

## 8. Share through GitHub Desktop

Commit only your new frontend folder. Check Changes for secrets, databases and
.venv before committing. Push your branch and coordinate merging with your team.
GitHub shares code, not your running app or Python environment. Each teammate
installs requirements and runs the app locally.

Official references:
- https://docs.streamlit.io/develop/concepts/architecture/forms
- https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state
- https://docs.streamlit.io/develop/api-reference/execution-flow/st.rerun
