"""handle_action(action, state) for the Streamlit frontend (see Frontend/BACKEND_CONTRACT.md).

Every action returns {"reply": str, "state": full_state}. Inputs from the UI and
from the AI are validated here; scheduler.replan() does all placement.
"""
import copy
from datetime import date, timedelta

from . import ai, billing, calendar_view, config, demo_student, scheduler, store
from . import timeutil as tu

MAX_TITLE = 120
MAX_MINUTES = 10000
PRIORITIES = {"High", "Medium", "Low"}


# ---------- validation helpers ----------

def _title(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A title is required")
    return value.strip()[:MAX_TITLE]


def _minutes(value, low=0, high=MAX_MINUTES):
    if isinstance(value, bool):
        raise ValueError("Minutes must be a whole number")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if not isinstance(value, int) or not (low <= value <= high):
        raise ValueError(f"Minutes must be a whole number between {low} and {high}")
    return value


def _when(value):
    """Validate and normalise a date-time to the frontend's local ISO format."""
    return tu.fmt(tu.parse(value))


def _normalise(state):
    state = copy.deepcopy(state) if isinstance(state, dict) else {}
    for key in ("tasks", "commitments", "sessions", "warnings"):
        if not isinstance(state.get(key), list):
            state[key] = []
    if not isinstance(state.get("preferences"), dict):
        state["preferences"] = {}
    return state


def _find(items, item_id, label):
    for item in items:
        if item.get("id") == item_id:
            return item
    raise ValueError(f"Unknown {label}: {item_id}")


# ---------- edits (shared by forms and AI) ----------

def _save_task(state, data):
    title = _title(data.get("title"))
    deadline = _when(data.get("deadline"))
    minutes = _minutes(data.get("remaining_minutes"))
    if data.get("id"):
        task = _find(state["tasks"], data["id"], "task")
    else:
        task = {"id": scheduler.new_id("t"), "priority": "", "reason": ""}
        state["tasks"].append(task)
    task.update(title=title, deadline=deadline, remaining_minutes=minutes)
    module = data.get("module")
    if isinstance(module, str) and module.strip():
        codes = {m["code"] for m in (state.get("profile") or {}).get("modules", [])}
        if not codes or module.strip().upper() in codes:
            task["module"] = module.strip().upper()
    if "priority" in data and data.get("priority") in PRIORITIES | {None}:
        if data["priority"]:
            task["user_priority"] = data["priority"]
        else:
            task.pop("user_priority", None)
    return task


def _update_task(state, data):
    task = _find(state["tasks"], data.get("task_id"), "task")
    merged = {"id": task["id"], "title": data.get("title") or task["title"],
              "deadline": data.get("deadline") or task["deadline"],
              "remaining_minutes": data["remaining_minutes"] if data.get("remaining_minutes") is not None
              else task["remaining_minutes"], "module": data.get("module") or task.get("module")}
    if "priority" in data:
        merged["priority"] = data["priority"]
    return _save_task(state, merged)


def _add_commitment(state, data):
    title = _title(data.get("title"))
    start, end = tu.parse(data.get("start")), tu.parse(data.get("end"))
    if end <= start:
        raise ValueError("A commitment must end after it starts")
    if end - start > timedelta(days=7):
        raise ValueError("A single commitment can't be longer than 7 days")
    item = {"id": scheduler.new_id("c"), "title": title, "start": tu.fmt(start), "end": tu.fmt(end)}
    state["commitments"].append(item)
    return item


def _apply_ai_action(state, act):
    kind = act.get("kind")
    if kind == "add_task":
        task = _save_task(state, {k: act.get(k) for k in ("title", "deadline", "remaining_minutes", "priority",
                                                          "module") if k in act})
        return f"added task '{task['title']}'"
    if kind == "update_task":
        task = _update_task(state, act)
        return f"updated '{task['title']}'"
    if kind == "delete_task":
        task = _find(state["tasks"], act.get("task_id"), "task")
        state["tasks"].remove(task)
        return f"removed task '{task['title']}'"
    if kind == "add_commitment":
        item = _add_commitment(state, act)
        return f"blocked '{item['title']}' {tu.describe(tu.parse(item['start']))}"
    if kind == "remove_commitment":
        item = _find(state["commitments"], act.get("commitment_id"), "commitment")
        state["commitments"].remove(item)
        return f"removed '{item['title']}'"
    if kind == "light_day":
        day = date.fromisoformat(str(act.get("date")))
        cap = _minutes(act.get("max_minutes", 60), 0, 600)
        prefs = state["preferences"]
        prefs.setdefault("light_days", {})[day.isoformat()] = cap
        return f"lighter {day:%a %d %b} (max {cap} min study)"
    if kind == "set_preferences":
        prefs, changed = state["preferences"], []
        for key in ("day_start", "day_end"):
            if act.get(key):
                tu.parse_hhmm(act[key])
                prefs[key] = act[key].strip()
                changed.append(f"{key.replace('_', ' ')} {prefs[key]}")
        if act.get("max_daily_minutes") is not None:
            prefs["max_daily_minutes"] = _minutes(act["max_daily_minutes"], 30, 720)
            changed.append(f"max {prefs['max_daily_minutes']} min/day")
        if act.get("session_minutes") is not None:
            prefs["session_minutes"] = _minutes(act["session_minutes"], 15, 240)
            changed.append(f"{prefs['session_minutes']} min sessions")
        if not changed:
            raise ValueError("No preference values given")
        return "set " + ", ".join(changed)
    raise ValueError(f"Unsupported action '{kind}'")


# ---------- reply helpers ----------

def _future_planned(state, now):
    return [s for s in state["sessions"] if s["status"] == "planned" and tu.parse(s["start"]) >= now]


def _summary(before, after, now):
    old = {(s["task_id"], s["start"], s["end"]) for s in _future_planned(before, now)}
    upcoming = _future_planned(after, now)
    new = {(s["task_id"], s["start"], s["end"]) for s in upcoming}
    total = sum(tu.minutes_between(tu.parse(s["start"]), tu.parse(s["end"])) for s in upcoming)
    if not upcoming:
        text = "No study sessions are planned right now."
    else:
        text = f"{len(upcoming)} study sessions planned ({total / 60:.1f} h)."
        if old and new != old:
            text += f" {len(new - old)} new or moved."
        first = upcoming[0]
        text += (f" Next: {first['title']}, {tu.describe(tu.parse(first['start']))}"
                 f"–{tu.local(tu.parse(first['end'])):%H:%M}.")
    if after["warnings"]:
        text += f" ⚠️ {len(after['warnings'])} warning(s) below."
    return text


def _upgrade_reply(prefix):
    try:
        _, url = billing.create_checkout(config.USER_ID)
        link = f"[Buy the Semester Pass (€9, test mode)]({url})"
    except billing.BillingError as err:
        link = f"(Payments aren't set up on this laptop yet: {err})"
    return (f"{prefix} {link}\n\nUse test card 4242 4242 4242 4242, any future date and any CVC. "
            "After paying, come back here and send your message again.")


def _save(state):
    try:
        store.save_plan(config.USER_ID, state)
    except Exception:          # persistence is best-effort; never block the UI
        pass


# ---------- public API ----------

def handle_action(action, state, now=None):
    if not isinstance(action, dict):
        raise ValueError("Action must be an object")
    now = now or tu.now()
    before = _normalise(state)
    work = copy.deepcopy(before)
    kind = action.get("type")

    if kind == "save_task":
        task = _save_task(work, action.get("task") or {})
        work = scheduler.replan(work, now)
        reply = f"Saved '{task['title']}'. " + _summary(before, work, now)

    elif kind == "add_commitment":
        item = _add_commitment(work, action.get("commitment") or {})
        work = scheduler.replan(work, now)
        reply = f"Blocked out '{item['title']}'. " + _summary(before, work, now)

    elif kind == "session_status":
        session = _find(work["sessions"], action.get("session_id"), "session")
        status = action.get("status")
        if status not in ("completed", "missed"):
            raise ValueError("Status must be completed or missed")
        if session["status"] != "planned":
            raise ValueError("Session already processed")      # never double-count
        session["status"] = status
        if status == "completed":
            done = tu.minutes_between(tu.parse(session["start"]), tu.parse(session["end"]))
            task = _find(work["tasks"], session["task_id"], "task")
            task["remaining_minutes"] = max(0, task["remaining_minutes"] - done)
            lead = f"Nice work: {done} min done on '{task['title']}'."
        else:
            lead = "No problem, that time goes back into the plan."
        work = scheduler.replan(work, now)
        reply = f"{lead} " + _summary(before, work, now)

    elif kind == "chat":
        return _chat(action, before, now)

    elif kind == "reset_demo":
        work = demo_student.initial_state(now)
        reply = bot_intro(work, now)

    else:
        raise ValueError(f"Unknown action type: {kind}")

    _save(work)
    return {"reply": reply, "state": work}


def _chat(action, before, now):
    message = action.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Message is empty")
    message = message.strip()[:2000]
    user = store.get_user(config.USER_ID)
    remaining = store.updates_remaining(user)

    if message.lower() in {"upgrade", "buy", "pay", "semester pass"}:
        if user["tier"] == "pro":
            return {"reply": "You already have the Semester Pass: unlimited updates.", "state": before}
        return {"reply": _upgrade_reply("Here's your checkout link:"), "state": before}
    if remaining == 0:
        return {"reply": _upgrade_reply(f"You've used your {config.FREE_UPDATES} free AI updates."),
                "state": before}

    try:
        parsed = ai.interpret(message, before, now)
    except ai.AIUnavailable as err:
        return {"reply": f"The AI isn't available right now ({err}). Your plan is unchanged; "
                         "you can still use the task and commitment forms.", "state": before}

    actions = parsed["actions"]
    questions = [a.get("question") for a in actions if isinstance(a, dict) and a.get("kind") == "clarify"]
    if questions and isinstance(questions[0], str):
        return {"reply": questions[0], "state": before}

    work = copy.deepcopy(before)
    done, skipped = [], []
    for act in actions:
        if not isinstance(act, dict):
            continue
        trial = copy.deepcopy(work)
        try:
            done.append(_apply_ai_action(trial, act))
            work = trial
        except (ValueError, TypeError, KeyError) as err:
            skipped.append(f"{act.get('kind', '?')}: {err}")

    reply = parsed["reply"] or "Got it."
    if not done:
        if skipped:
            reply += "\n\nI couldn't apply that: " + "; ".join(skipped) + ". Could you rephrase?"
        return {"reply": reply, "state": before}

    work = scheduler.replan(work, now)
    store.count_update(config.USER_ID)
    store.log_update(config.USER_ID, message, actions)
    left = store.updates_remaining(store.get_user(config.USER_ID))
    reply += "\n\n✅ " + "; ".join(done) + ".\n\n" + _summary(before, work, now)
    if skipped:
        reply += "\n\nSkipped: " + "; ".join(skipped) + "."
    if left is not None:
        reply += f"\n\n{left} free AI update(s) left." + (" Type **upgrade** for unlimited." if left <= 1 else "")
    _save(work)
    return {"reply": reply, "state": work}


def initial_state(now=None):
    """Starting state for the app: the saved plan if there is one, else the demo student."""
    saved = load_state()
    if saved and saved.get("profile"):
        return scheduler.replan(_normalise(saved), now or tu.now())
    return demo_student.initial_state(now)


def bot_intro(state, now=None):
    """First chat message from the personal coach."""
    now = now or tu.now()
    p = state.get("profile") or {}
    first = (p.get("name") or "there").split()[0]
    bot = p.get("bot_name", "your planner")
    end = now + timedelta(days=7)
    week = [s for s in state.get("sessions", []) if s["status"] == "planned" and now <= tu.parse(s["start"]) < end]
    hours = sum(tu.minutes_between(tu.parse(s["start"]), tu.parse(s["end"])) for s in week) / 60
    soon = sorted(state.get("tasks", []), key=lambda t: t["deadline"])
    text = f"Hi {first}, I'm {bot}, your study coach. "
    text += f"I've planned {len(week)} study sessions ({hours:.1f} h) around your lectures, labs, commute and shifts this week."
    if soon:
        t = soon[0]
        text += f" First deadline: **{t['title']}**, due {tu.local(tu.parse(t['deadline'])):%a %d %b %H:%M}."
    if state.get("warnings"):
        text += f" ⚠️ {len(state['warnings'])} thing(s) don't fit yet; see the warnings."
    text += ("\n\nTell me what changes, e.g. *\"I'm wrecked Tuesday\"*, *\"lab report is due Thursday now\"* "
             "or *\"what's on tomorrow?\"*")
    return text


def week_events(state, week_start=None):
    """Google-Calendar-style events (FullCalendar format) for the frontend."""
    return calendar_view.week_events(state, week_start)


def legend(state):
    return calendar_view.legend(state)


def load_state():
    """Saved plan for the demo student, or None. Call once when the app starts."""
    try:
        return store.load_plan(config.USER_ID)
    except Exception:
        return None


def account_status():
    user = store.get_user(config.USER_ID)
    return {"tier": user["tier"], "updates_remaining": store.updates_remaining(user)}
