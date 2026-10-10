"""Deterministic study-session scheduler.

The AI never places blocks: it only produces structured edits. This module does
all arithmetic and constraint checks:
  * no sessions in the past, after a deadline, or overlapping each other
  * no clashes with fixed commitments
  * completed sessions are never touched; missed sessions stay as history
  * work that cannot fit is reported in `warnings`, never silently dropped
"""
from datetime import timedelta
from uuid import uuid4

from . import timeutil as tu

DEFAULT_PREFERENCES = {
    "day_start": "09:00",        # earliest study time each day (local)
    "day_end": "21:00",          # latest study time each day (local)
    "max_daily_minutes": 240,    # study cap per day
    "session_minutes": 60,       # preferred session length
    "max_task_minutes_per_day": 120,
    "break_minutes": 15,         # gap kept between consecutive study sessions
    "light_days": {},            # {"2026-10-13": 60} -> lower cap that day
    "daily_blocked": [],         # [{"title": "Lunch", "start": "13:00", "end": "14:00"}] protected every day
}
SLOT = 15                        # scheduling granularity in minutes
MIN_SESSION = 30                 # shortest session we create (unless less work remains)
HORIZON_DAYS = 28                # never plan further ahead than this


def preferences(state):
    prefs = dict(DEFAULT_PREFERENCES)
    prefs.update({k: v for k, v in (state.get("preferences") or {}).items() if k in DEFAULT_PREFERENCES})
    prefs["light_days"] = dict(prefs.get("light_days") or {})
    prefs["daily_blocked"] = [dict(b) for b in (prefs.get("daily_blocked") or []) if isinstance(b, dict)]
    return prefs


def _daily_blocked(day, prefs):
    out = []
    for block in prefs["daily_blocked"]:
        try:
            start, end = tu.at_local(day, block["start"]), tu.at_local(day, block["end"])
        except (KeyError, ValueError):
            continue
        if end > start:
            out.append((start, end))
    return out


def _interval(item):
    return tu.parse(item["start"]), tu.parse(item["end"])


def _overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def _free_gaps(window_start, window_end, busy):
    """Free sub-intervals of [window_start, window_end) given busy intervals."""
    gaps, cursor = [], window_start
    for b_start, b_end in sorted(busy):
        if b_end <= cursor or b_start >= window_end:
            continue
        if b_start > cursor:
            gaps.append((cursor, min(b_start, window_end)))
        cursor = max(cursor, b_end)
        if cursor >= window_end:
            break
    if cursor < window_end:
        gaps.append((cursor, window_end))
    return gaps


def _day_window(day, prefs):
    start = tu.at_local(day, prefs["day_start"])
    end = tu.at_local(day, prefs["day_end"])
    if end <= start:            # e.g. 18:00 -> 02:00 for a night owl
        end = tu.at_local(day + timedelta(days=1), prefs["day_end"])
    return start, end


def _priority(task, now, unscheduled):
    deadline = tu.parse(task["deadline"])
    hours_left = (deadline - now).total_seconds() / 3600
    need_h = task["remaining_minutes"] / 60
    when = tu.local(deadline).strftime("%a %d %b %H:%M")
    if task["remaining_minutes"] == 0:
        return "Done", "No work remaining."
    if hours_left <= 0:
        return "Overdue", f"Deadline {when} has passed; {task['remaining_minutes']} min still to do."
    user = task.get("user_priority")
    if user:
        label = user
        why = f"You marked this {user.lower()} priority. Due {when}."
    elif hours_left <= 48 or need_h >= hours_left / 6:
        label, why = "High", f"Due {when} ({hours_left / 24:.1f} days) with {task['remaining_minutes']} min left."
    elif hours_left <= 120:
        label, why = "Medium", f"Due {when}; {task['remaining_minutes']} min left."
    else:
        label, why = "Low", f"Due {when}; plenty of time."
    if unscheduled:
        why += f" {unscheduled} min could not be fitted before the deadline."
    return label, why


def replan(state, now=None):
    """Return a new state with all future planned sessions recomputed."""
    now = now or tu.now()
    prefs = preferences(state)
    tasks = state["tasks"]
    commitments = state["commitments"]
    task_ids = {t["id"] for t in tasks}

    kept, busy, already = [], [], {}
    for s in state["sessions"]:
        if s.get("task_id") not in task_ids:
            continue                                    # task deleted: drop its sessions
        start, end = _interval(s)
        if s["status"] == "planned" and start >= now:
            continue                                    # future plan: rebuild below
        kept.append(s)                                  # completed, missed, ongoing or past
        if s["status"] == "planned" and end > now:      # in progress now
            busy.append((start, end))
            already[s["task_id"]] = already.get(s["task_id"], 0) + tu.minutes_between(now, end)
        elif s["status"] == "completed":
            busy.append((start, end))

    for c in commitments:
        busy.append(_interval(c))

    start_from = tu.ceil_to(now, SLOT)
    horizon = start_from + timedelta(days=HORIZON_DAYS)
    rank = {"High": 0, "Medium": 1, "Low": 2}
    order = sorted(tasks, key=lambda t: (rank.get(t.get("user_priority"), 1), tu.parse(t["deadline"]),
                                         -t["remaining_minutes"]))

    daily_used = {}        # local date -> study minutes planned
    task_daily = {}        # (task_id, local date) -> minutes
    for s in kept:
        if s["status"] in ("planned", "completed"):
            st, en = _interval(s)
            d = tu.local(st).date()
            daily_used[d] = daily_used.get(d, 0) + tu.minutes_between(st, en)

    new_sessions, warnings, unscheduled_by_task = [], [], {}
    brk = timedelta(minutes=prefs["break_minutes"])

    for task in order:
        need = max(0, task["remaining_minutes"] - already.get(task["id"], 0))
        deadline = min(tu.parse(task["deadline"]), horizon)
        placed = []
        day = tu.local(start_from).date() - timedelta(days=1)   # include a window that started yesterday
        while need > 0 and day <= tu.local(deadline).date():
            w_start, w_end = _day_window(day, prefs)
            w_start, w_end = max(w_start, start_from), min(w_end, deadline)
            cap = prefs["light_days"].get(day.isoformat(), prefs["max_daily_minutes"])
            if w_end > w_start:
                spaced = busy + _daily_blocked(day, prefs) + [(a, b + brk) for a, b in busy_study(new_sessions, kept)]
                for g_start, g_end in _free_gaps(w_start, w_end, spaced):
                    while need > 0:
                        room_day = min(cap - daily_used.get(day, 0),
                                       prefs["max_task_minutes_per_day"] - task_daily.get((task["id"], day), 0))
                        gap = tu.minutes_between(g_start, g_end)
                        length = min(prefs["session_minutes"], need, room_day, gap)
                        length -= length % SLOT if length >= SLOT else 0
                        leftover = need - length
                        if 0 < leftover < MIN_SESSION:
                            if length + leftover <= min(gap, room_day):
                                length = need      # finish the task instead of leaving a tiny scrap
                            elif need - MIN_SESSION >= MIN_SESSION:
                                length = need - MIN_SESSION   # leave a proper-sized last session
                        if length <= 0 or (length < MIN_SESSION and length < need):
                            break
                        s_start = g_start
                        s_end = s_start + timedelta(minutes=length)
                        session = {"id": "s_" + uuid4().hex[:8], "task_id": task["id"], "title": task["title"],
                                   "start": tu.fmt(s_start), "end": tu.fmt(s_end), "status": "planned"}
                        if task.get("module"):
                            session["module"] = task["module"]
                        new_sessions.append(session)
                        placed.append(session)
                        need -= length
                        daily_used[day] = daily_used.get(day, 0) + length
                        task_daily[(task["id"], day)] = task_daily.get((task["id"], day), 0) + length
                        g_start = s_end + brk
                        if g_start >= g_end:
                            break
                    if need <= 0:
                        break
            day += timedelta(days=1)
        for i, s in enumerate(placed, 1):
            s["title"] = f"{task['title']} ({i}/{len(placed)})" if len(placed) > 1 else task["title"]
        if need > 0:
            unscheduled_by_task[task["id"]] = need
            due = tu.local(tu.parse(task["deadline"])).strftime("%a %d %b %H:%M")
            warnings.append(f"{task['title']}: {need} min could not be scheduled before {due}. "
                            "Free up time, extend the deadline or reduce the estimate.")

    for task in tasks:
        task["priority"], task["reason"] = _priority(task, now, unscheduled_by_task.get(task["id"], 0))

    # Fixed blocks that clash with each other are the user's call, so warn rather than fix.
    ordered = sorted(commitments, key=lambda c: tu.parse(c["start"]))
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            if tu.parse(b["start"]) >= tu.parse(a["end"]):
                break
            if _overlaps(*_interval(a), *_interval(b)):
                warnings.append(f"Fixed blocks clash: '{a['title']}' and '{b['title']}' overlap.")

    state["sessions"] = sorted(kept + new_sessions, key=lambda s: tu.parse(s["start"]))
    state["warnings"] = warnings
    state["preferences"] = prefs
    return state


def busy_study(new_sessions, kept):
    """Study sessions that should keep a break around them."""
    out = [_interval(s) for s in new_sessions]
    out += [_interval(s) for s in kept if s["status"] in ("planned", "completed")]
    return out


def check_invariants(state, now=None):
    """Return a list of problems (empty = valid). Used by tests and as a safety net."""
    now = now or tu.now()
    problems = []
    tasks = {t["id"]: t for t in state["tasks"]}
    planned = [s for s in state["sessions"] if s["status"] == "planned"]
    for s in state["sessions"]:
        start, end = _interval(s)
        if end <= start:
            problems.append(f"{s['id']} has non-positive duration")
        if s["task_id"] not in tasks:
            problems.append(f"{s['id']} references unknown task")
    for s in planned:
        start, end = _interval(s)
        if start >= now and end > tu.parse(tasks[s["task_id"]]["deadline"]):
            problems.append(f"{s['id']} ends after its deadline")
        for c in state["commitments"]:
            if start >= now and _overlaps(start, end, *_interval(c)):
                problems.append(f"{s['id']} clashes with {c['title']}")
    future = sorted((_interval(s) for s in planned), key=lambda x: x[0])
    for (a_s, a_e), (b_s, b_e) in zip(future, future[1:]):
        if b_s < a_e:
            problems.append("two planned sessions overlap")
    ids = [s["id"] for s in state["sessions"]]
    if len(ids) != len(set(ids)):
        problems.append("duplicate session ids")
    return problems


def new_id(prefix):
    return f"{prefix}_{uuid4().hex[:8]}"
