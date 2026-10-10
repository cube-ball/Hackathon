"""Fictional demo student: a Stage 3 UCD Electronic & Electrical Engineering student.

Module codes and titles follow UCD's published Stage 3 E&E autumn list (core + two
options). Times, rooms, deadlines and the student are made up for the demo.
Dates are generated relative to today so the demo always shows a live week.
"""
import copy
from datetime import date, timedelta

from . import scheduler
from . import timeutil as tu

BOT_NAME = "Sparky"

PROFILE = {
    "name": "Aoife Byrne",
    "programme": "BE Electronic & Electrical Engineering, Stage 3",
    "university": "University College Dublin",
    "bot_name": BOT_NAME,
    "style": "strict",
    "goals": "Keep a 2:1 average, get lab reports in early, protect sleep before 9am lectures.",
    "commute": {"route": "46A bus", "minutes_each_way": 40},
    "sleep": {"bedtime": "23:30", "wake": "07:15"},
    "job": "Part-time at a supermarket: Thursday 18:00-22:00 and Saturday 10:00-16:00",
    "fictional": True,
    "modules": [
        {"code": "EEEN30020", "title": "Circuit Theory", "colour": "#1a73e8"},
        {"code": "EEEN30110", "title": "Signals and Systems", "colour": "#8e24aa"},
        {"code": "ACM30030", "title": "Multivariable Calculus for Engineers 2", "colour": "#f4511e"},
        {"code": "COMP20080", "title": "Computer Science for Engineers 2", "colour": "#0b8043"},
        {"code": "EEEN30190", "title": "Digital System Design", "colour": "#d81b60"},
        {"code": "EEEN30090", "title": "Electrical Machines", "colour": "#f6bf26"},
    ],
}

# (weekday 0=Mon, start, end, module code, kind, room)  -- sample timetable, not the real one
TIMETABLE = [
    (0, "09:00", "10:00", "EEEN30020", "lecture", "Eng. Building E1.01"),
    (0, "11:00", "12:00", "ACM30030", "lecture", "Science Hub H2.20"),
    (0, "14:00", "15:00", "EEEN30110", "lecture", "Eng. Building E0.32"),
    (0, "15:00", "17:00", "COMP20080", "lab", "Computer Lab B1.08"),
    (1, "10:00", "11:00", "EEEN30190", "lecture", "Eng. Building E1.01"),
    (1, "12:00", "13:00", "EEEN30090", "lecture", "Eng. Building E0.32"),
    (1, "14:00", "17:00", "EEEN30020", "lab", "Electronics Lab E2.14"),
    (2, "09:00", "10:00", "EEEN30110", "lecture", "Eng. Building E1.01"),
    (2, "10:00", "11:00", "ACM30030", "tutorial", "Science Hub H1.12"),
    (2, "12:00", "13:00", "EEEN30020", "tutorial", "Eng. Building E1.18"),
    (3, "09:00", "10:00", "COMP20080", "lecture", "Science Hub H2.20"),
    (3, "11:00", "13:00", "EEEN30190", "lab", "Digital Lab E2.05"),
    (3, "14:00", "15:00", "EEEN30090", "lecture", "Eng. Building E0.32"),
    (4, "10:00", "11:00", "ACM30030", "lecture", "Science Hub H2.20"),
    (4, "11:00", "12:00", "EEEN30110", "tutorial", "Eng. Building E1.18"),
    (4, "14:00", "16:00", "EEEN30090", "lab", "Machines Lab E0.10"),
]

# (weekday, start, end, title, kind, location, on_campus)
PERSONAL = [
    (2, "19:00", "20:30", "Football (social league)", "personal", "UCD sports pitches", True),
    (3, "18:00", "22:00", "Supermarket shift", "work", "Local supermarket", False),
    (5, "10:00", "16:00", "Supermarket shift", "work", "Local supermarket", False),
]

# (module, title, days from today, due time, minutes of work)
ASSIGNMENTS = [
    ("ACM30030", "Calculus 2: weekly online quiz", 2, "10:00", 90),
    ("EEEN30110", "Signals & Systems: problem set 3", 4, "12:00", 180),
    ("EEEN30020", "Circuit Theory: lab report 2", 6, "17:00", 240),
    ("EEEN30190", "Digital System Design: design assignment 1 (VHDL)", 9, "17:00", 360),
    ("COMP20080", "CS for Engineers 2: programming assignment", 11, "23:00", 240),
    ("EEEN30090", "Electrical Machines: assignment 1", 13, "17:00", 180),
]

STRICT_PREFERENCES = {
    "day_start": "08:00",
    "day_end": "22:00",
    "max_daily_minutes": 240,
    "session_minutes": 45,
    "break_minutes": 15,
    "max_task_minutes_per_day": 135,
    "light_days": {},
    "daily_blocked": [
        {"title": "Lunch", "start": "13:00", "end": "14:00"},
        {"title": "Dinner", "start": "18:00", "end": "18:45"},
    ],
}

WEEKS = 3


def module_title(code):
    for m in PROFILE["modules"]:
        if m["code"] == code:
            return m["title"]
    return code


def _stamp(day, hhmm):
    return tu.fmt(tu.at_local(day, hhmm))


def _minus(hhmm, minutes):
    h, m = tu.parse_hhmm(hhmm)
    total = h * 60 + m - minutes
    return f"{total // 60:02d}:{total % 60:02d}"


def _plus(hhmm, minutes):
    return _minus(hhmm, -minutes)


def commitments(today):
    monday = today - timedelta(days=today.weekday())
    commute = PROFILE["commute"]["minutes_each_way"]
    items = []

    def add(day, start, end, title, kind, location, module=None):
        item = {"id": scheduler.new_id("c"), "title": title, "start": _stamp(day, start),
                "end": _stamp(day, end), "kind": kind, "location": location}
        if module:
            item["module"] = module
        items.append(item)

    for week in range(WEEKS):
        for weekday in range(7):
            day = monday + timedelta(days=7 * week + weekday)
            campus = [(s, e) for (wd, s, e, *_r) in TIMETABLE if wd == weekday]
            campus += [(s, e) for (wd, s, e, _t, _k, _l, on) in PERSONAL if wd == weekday and on]
            if campus:
                first, last = min(s for s, _ in campus), max(e for _, e in campus)
                add(day, _minus(first, commute + 15), _minus(first, 15), f"Commute in ({PROFILE['commute']['route']})",
                    "commute", PROFILE["commute"]["route"])
                add(day, last, _plus(last, commute), f"Commute home ({PROFILE['commute']['route']})",
                    "commute", PROFILE["commute"]["route"])
            for wd, start, end, code, kind, room in TIMETABLE:
                if wd == weekday:
                    add(day, start, end, f"{code} {module_title(code)} ({kind})", kind, room, code)
            for wd, start, end, title, kind, location, _on in PERSONAL:
                if wd == weekday:
                    add(day, start, end, title, kind, location)
    return items


def tasks(today):
    out = []
    for code, title, days, due, minutes in ASSIGNMENTS:
        out.append({"id": scheduler.new_id("t"), "title": title, "module": code,
                    "deadline": _stamp(today + timedelta(days=days), due),
                    "remaining_minutes": minutes, "priority": "", "reason": ""})
    return out


def initial_state(now=None):
    """A complete, scheduled demo week for the fictional student."""
    now = now or tu.now()
    today = tu.local(now).date()
    state = {
        "profile": copy.deepcopy(PROFILE),
        "preferences": copy.deepcopy(STRICT_PREFERENCES),
        "tasks": tasks(today),
        "commitments": commitments(today),
        "sessions": [],
        "warnings": [],
    }
    return scheduler.replan(state, now)


def as_date(value):
    return value if isinstance(value, date) else date.fromisoformat(value)
