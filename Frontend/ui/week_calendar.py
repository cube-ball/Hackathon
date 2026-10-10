"""Google-Calendar-style week/day view with a toolbar and an event details panel."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components

from ui import calendar_html

try:
    from backend_bridge import week_events
except ImportError:          # frontend-only fallback: plain events without colours
    def week_events(state, week_start=None):
        out = []
        for c in state["commitments"]:
            out.append({"id": c["id"], "title": c["title"], "start": c["start"], "end": c["end"],
                        "backgroundColor": "#039be5", "borderColor": "#039be5", "textColor": "#fff",
                        "extendedProps": {"source": "commitment", "kind": "other"}})
        for s in state["sessions"]:
            out.append({"id": s["id"], "title": s["title"], "start": s["start"], "end": s["end"],
                        "backgroundColor": "#c6dafc", "borderColor": "#1a73e8", "textColor": "#202124",
                        "extendedProps": {"source": "session", "kind": "study", "status": s["status"],
                                          "task_id": s["task_id"]}})
        return out


DUBLIN = ZoneInfo("Europe/Dublin")


def now_local():
    """Dublin wall time (servers such as Streamlit Cloud run on UTC)."""
    return datetime.now(DUBLIN).replace(tzinfo=None)


def _init():
    if "cal_anchor" not in st.session_state:
        st.session_state.cal_anchor = now_local().date()
    if "cal_view" not in st.session_state:
        st.session_state.cal_view = "Week"


def _shift(days):
    st.session_state.cal_anchor = st.session_state.cal_anchor + timedelta(days=days)


def _today():
    st.session_state.cal_anchor = now_local().date()


def _visible_days():
    anchor = st.session_state.cal_anchor
    if st.session_state.cal_view == "Day":
        return [anchor]
    monday = anchor - timedelta(days=anchor.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def _title(days):
    first, last = days[0], days[-1]
    if len(days) == 1:
        return f"{first:%A, %d %B %Y}"
    if first.month == last.month:
        return f"{first:%B} {first.day} – {last.day}, {last.year}"
    return f"{first:%b} {first.day} – {last:%b} {last.day}, {last.year}"


def render_calendar(state, dispatch):
    _init()
    step = 1 if st.session_state.cal_view == "Day" else 7
    bar = st.columns([1, 0.45, 0.45, 3.2, 1.6], vertical_alignment="center")
    bar[0].button("Today", on_click=_today)
    bar[1].button("‹", on_click=_shift, args=(-step,), help="Previous")
    bar[2].button("›", on_click=_shift, args=(step,), help="Next")
    days = _visible_days()
    bar[3].markdown(f"<div class='cal-title'>{_title(days)}</div>", unsafe_allow_html=True)
    bar[4].radio("View", ["Week", "Day"], key="cal_view", horizontal=True, label_visibility="collapsed")

    events = week_events(state, days[0].isoformat())
    if len(days) == 1:
        events = [e for e in events if e["start"][:10] <= days[0].isoformat() <= e["end"][:10]]
    html = calendar_html.render(events, days, today=now_local().date(), now=now_local())
    components.html(html, height=calendar_html.grid_height(), scrolling=False)
    st.caption("Hover over a block for details. Times are Europe/Dublin.")
    _details(state, events, dispatch)


def _label(event):
    start = datetime.fromisoformat(event["start"])
    end = datetime.fromisoformat(event["end"])
    return f"{start:%a %d %b · %H:%M}–{end:%H:%M} · {event['title']}"


def _details(state, events, dispatch):
    if not events:
        st.info("Nothing scheduled in this view.")
        return
    modules = {m["code"]: m["title"] for m in (state.get("profile") or {}).get("modules", [])}
    by_id = {e["id"]: e for e in events}
    ids = list(by_id)
    now = now_local().isoformat()
    upcoming = [e["id"] for e in events if e["extendedProps"].get("source") == "session"
                and e["extendedProps"].get("status") == "planned" and e["end"] >= now]
    default = ids.index(upcoming[0]) if upcoming else 0
    with st.container(border=True):
        st.markdown("**Event details**")
        chosen = st.selectbox("Event", ids, index=default, format_func=lambda i: _label(by_id[i]),
                              label_visibility="collapsed")
        ev = by_id[chosen]
        props = ev["extendedProps"]
        start, end = datetime.fromisoformat(ev["start"]), datetime.fromisoformat(ev["end"])
        swatch = (f"<span style='display:inline-block;width:12px;height:12px;border-radius:3px;"
                  f"background:{ev.get('borderColor', '#1a73e8')};margin-right:8px'></span>")
        st.markdown(f"{swatch}<b>{ev['title']}</b>", unsafe_allow_html=True)
        lines = [f"🕒 {start:%A %d %B, %H:%M} – {end:%H:%M}"]
        if props.get("kind_label"):
            lines.append(f"🏷️ {props['kind_label']}")
        if props.get("module"):
            lines.append(f"📘 {props['module']} {modules.get(props['module'], '')}")
        if props.get("location"):
            lines.append(f"📍 {props['location']}")
        if props.get("deadline"):
            due = datetime.fromisoformat(props["deadline"])
            lines.append(f"⏰ Deadline {due:%a %d %b %H:%M}")
        if props.get("reason"):
            lines.append(f"💡 {props['reason']}")
        if props.get("status"):
            lines.append(f"Status: **{props['status']}**")
        st.markdown("  \n".join(lines))
        if props.get("source") == "session" and props.get("status") == "planned":
            a, b = st.columns(2)
            if a.button("✓ Mark completed", key=f"done_{chosen}", type="primary"):
                dispatch({"type": "session_status", "session_id": chosen, "status": "completed"})
            if b.button("✗ Mark missed", key=f"miss_{chosen}"):
                dispatch({"type": "session_status", "session_id": chosen, "status": "missed"})
