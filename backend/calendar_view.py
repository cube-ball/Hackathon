"""Turns planner state into Google-Calendar-style events.

The output is FullCalendar's event format, which is what the `streamlit-calendar`
component expects, so the frontend can pass it straight in:

    from backend_bridge import week_events
    calendar(events=week_events(state), options={...})
"""
from datetime import date, timedelta

from . import timeutil as tu

KIND_COLOURS = {
    "commute": "#9aa0a6",
    "work": "#616161",
    "personal": "#33b679",
    "sleep": "#3f51b5",
    "other": "#7986cb",
}
KIND_LABELS = {"lecture": "Lecture", "lab": "Lab", "tutorial": "Tutorial", "commute": "Commute",
               "work": "Work", "personal": "Personal", "study": "Study"}
DEFAULT_MODULE_COLOUR = "#039be5"


def module_colours(state):
    profile = state.get("profile") or {}
    return {m["code"]: m.get("colour", DEFAULT_MODULE_COLOUR) for m in profile.get("modules", [])}


def _lighten(hex_colour, amount=0.55):
    hex_colour = hex_colour.lstrip("#")
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (int(c + (255 - c) * amount) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _in_range(item, start, end):
    if start is None:
        return True
    return tu.parse(item["start"]) < end and tu.parse(item["end"]) > start


def week_events(state, week_start=None, days=7):
    """All events (or those overlapping [week_start, week_start + days)) as FullCalendar dicts."""
    colours = module_colours(state)
    tasks = {t["id"]: t for t in state.get("tasks", [])}
    if week_start is not None:
        if isinstance(week_start, str):
            week_start = date.fromisoformat(week_start[:10])
        range_start = tu.at_local(week_start, "00:00")
        range_end = tu.at_local(week_start + timedelta(days=days), "00:00")
    else:
        range_start = range_end = None

    events = []
    for c in state.get("commitments", []):
        if not _in_range(c, range_start, range_end):
            continue
        kind = c.get("kind", "other")
        colour = colours.get(c.get("module")) or KIND_COLOURS.get(kind, KIND_COLOURS["other"])
        events.append({
            "id": c["id"], "title": c["title"], "start": c["start"], "end": c["end"],
            "backgroundColor": colour, "borderColor": colour, "textColor": "#ffffff",
            "extendedProps": {"source": "commitment", "kind": kind, "kind_label": KIND_LABELS.get(kind, "Busy"),
                              "module": c.get("module"), "location": c.get("location", ""),
                              "locked": True},
        })
    for s in state.get("sessions", []):
        if not _in_range(s, range_start, range_end):
            continue
        task = tasks.get(s.get("task_id"), {})
        module = s.get("module") or task.get("module")
        base = colours.get(module, DEFAULT_MODULE_COLOUR)
        status = s.get("status", "planned")
        if status == "completed":
            bg, text, prefix = "#e0e0e0", "#5f6368", "✓ "
        elif status == "missed":
            bg, text, prefix = "#fce8e6", "#c5221f", "✗ "
        else:
            bg, text, prefix = _lighten(base), "#202124", "📚 "
        events.append({
            "id": s["id"], "title": prefix + s["title"], "start": s["start"], "end": s["end"],
            "backgroundColor": bg, "borderColor": base, "textColor": text,
            "extendedProps": {"source": "session", "kind": "study", "kind_label": "Study",
                              "module": module, "status": status, "task_id": s.get("task_id"),
                              "deadline": task.get("deadline"), "reason": task.get("reason", ""),
                              "locked": False},
        })
    events.sort(key=lambda e: tu.parse(e["start"]))
    return events


def legend(state):
    """[(label, colour)] for a colour key under the calendar."""
    profile = state.get("profile") or {}
    items = [(f"{m['code']} {m['title']}", m.get("colour", DEFAULT_MODULE_COLOUR)) for m in profile.get("modules", [])]
    items += [("Study session (lighter shade of module colour)", _lighten(DEFAULT_MODULE_COLOUR))]
    items += [(KIND_LABELS[k], v) for k, v in KIND_COLOURS.items() if k in KIND_LABELS]
    return items
