# StudyFlow backend

Implements `handle_action(action, state)` from `Frontend/BACKEND_CONTRACT.md`.
The Streamlit app loads it through `Frontend/backend_bridge.py`.

| File | What it does |
| --- | --- |
| `bridge.py` | `handle_action`: validates every action, applies it, replans, writes the reply |
| `scheduler.py` | Places study sessions: no past, no clashes, before deadlines, daily caps; warns about work that doesn't fit |
| `ai.py` | OpenRouter call that turns a chat message into structured edits (the AI never places sessions) |
| `billing.py` | Stripe Checkout link + webhook signature check (test mode only) |
| `store.py` | SQLite: tier, free-update count, orders, saved plan, chat log |
| `app.py` | Flask server that receives the Stripe webhook |
| `timeutil.py` | Europe/Dublin time handling, incl. clock changes |
| `demo_student.py` | Fictional Stage 3 UCD E&E student "Aoife Byrne": 6 modules, sample timetable, commute, shifts, 6 deadlines, strict study rules |
| `calendar_view.py` | Turns the plan into Google-Calendar-style events (FullCalendar format for `streamlit-calendar`) |

## What the frontend can call (via `Frontend/backend_bridge.py`)

| Function | Returns |
| --- | --- |
| `handle_action(action, state)` | `{"reply", "state"}`. Actions: `chat`, `save_task`, `add_commitment`, `session_status`, `reset_demo` |
| `initial_state()` | Saved plan, or the demo student with a fully scheduled week |
| `bot_intro(state)` | The coach's (Sparky's) greeting for the chat |
| `week_events(state, week_start=None)` | Calendar events with colours and details in `extendedProps` |
| `legend(state)` | `(label, colour)` pairs for a colour key |

Strict demo rules: study 08:00-22:00, 45-minute sessions with 15-minute breaks, max 4 h study a day,
lunch 13:00-14:00 and dinner 18:00-18:45 protected. The coach persona and the student's modules are sent
to the AI with every chat message. `Frontend/CALENDAR_PROMPT.md` is the prompt for the calendar UI.

## Run it (Mac)

```bash
cp backend/.env.example backend/.env      # then fill in the keys
cd Frontend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Free tier: 3 AI chat updates. Type **upgrade** in the chat for the Stripe checkout link.

### Payments (only needed to demo Stripe)

```bash
# terminal 2, from the repo root
python3 -m pip install -r backend/requirements.txt
python3 -m backend.app                    # webhook server on port 5050
# terminal 3
stripe listen --forward-to localhost:5050/api/stripe/webhook
```
Copy the `whsec_...` that `stripe listen` prints into `backend/.env`, restart `python3 -m backend.app`.
Pay with test card 4242 4242 4242 4242. The webhook switches the student to Pro.

## Tests

```bash
python3 -m unittest discover -s backend/tests -t .
```
