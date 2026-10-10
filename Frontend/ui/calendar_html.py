"""Builds a Google-Calendar-style time grid as self-contained HTML.

Pure Python (no Streamlit import) so it can be tested on its own.
Events use the backend's FullCalendar-style dicts:
{"id", "title", "start", "end", "backgroundColor", "borderColor", "textColor", "extendedProps"}
with naive Europe/Dublin ISO times.
"""
from datetime import date, datetime, time, timedelta
from html import escape

DAY_START_HOUR = 7
DAY_END_HOUR = 24
PX_PER_MIN = 0.8
HEADER_PX = 64


def grid_height():
    return int((DAY_END_HOUR - DAY_START_HOUR) * 60 * PX_PER_MIN) + HEADER_PX + 8


def _segments(event, day):
    """The part of an event that falls on `day` within the visible hours, as (start_min, end_min)."""
    start = datetime.fromisoformat(event["start"])
    end = datetime.fromisoformat(event["end"])
    lo = datetime.combine(day, time(DAY_START_HOUR))
    hi = datetime.combine(day, time(0)) + timedelta(hours=DAY_END_HOUR)
    s, e = max(start, lo), min(end, hi)
    if e <= s:
        return None
    base = datetime.combine(day, time(0))
    return int((s - base).total_seconds() // 60), int((e - base).total_seconds() // 60), start, end


def _lanes(items):
    """Side-by-side columns for overlapping events (like Google Calendar)."""
    items.sort(key=lambda x: (x["s"], -(x["e"] - x["s"])))
    clusters, current, current_end = [], [], -1
    for it in items:
        if current and it["s"] >= current_end:
            clusters.append(current)
            current, current_end = [], -1
        current.append(it)
        current_end = max(current_end, it["e"])
    if current:
        clusters.append(current)
    for cluster in clusters:
        lane_ends = []
        for it in cluster:
            for i, lane_end in enumerate(lane_ends):
                if it["s"] >= lane_end:
                    it["lane"], lane_ends[i] = i, it["e"]
                    break
            else:
                it["lane"] = len(lane_ends)
                lane_ends.append(it["e"])
        for it in cluster:
            it["lanes"] = len(lane_ends)
    return items


def _event_html(it):
    ev = it["event"]
    props = ev.get("extendedProps", {})
    top = (it["s"] - DAY_START_HOUR * 60) * PX_PER_MIN
    height = max((it["e"] - it["s"]) * PX_PER_MIN - 2, 14)
    width = 100 / it["lanes"]
    left = it["lane"] * width
    when = f"{it['start']:%H:%M} – {it['end']:%H:%M}"
    tip_lines = [ev["title"], when]
    for key in ("location", "reason"):
        if props.get(key):
            tip_lines.append(props[key])
    if props.get("deadline"):
        tip_lines.append("Due " + props["deadline"].replace("T", " ")[:16])
    style = (f"top:{top:.1f}px;height:{height:.1f}px;left:calc({left:.3f}% + 1px);"
             f"width:calc({width:.3f}% - 3px);background:{ev.get('backgroundColor', '#039be5')};"
             f"color:{ev.get('textColor', '#fff')};border-left:4px solid {ev.get('borderColor', '#039be5')};")
    classes = "ev"
    if props.get("source") == "session":
        classes += " study"
    if props.get("status") in ("completed", "missed"):
        classes += " " + props["status"]
    body = f'<div class="t">{escape(ev["title"])}</div>'
    if height >= 30:
        body += f'<div class="m">{escape(when)}</div>'
    if height >= 44 and props.get("location"):
        body += f'<div class="m">{escape(props["location"])}</div>'
    return f'<div class="{classes}" style="{style}" title="{escape(chr(10).join(tip_lines))}">{body}</div>'


def render(events, days, today=None, now=None):
    """HTML for a time grid covering `days` (list of dates)."""
    today = today or date.today()
    now = now or datetime.now()
    hours = list(range(DAY_START_HOUR, DAY_END_HOUR))
    body_h = (DAY_END_HOUR - DAY_START_HOUR) * 60 * PX_PER_MIN

    head = ['<div class="corner"></div>']
    cols = []
    for day in days:
        is_today = day == today
        head.append(
            f'<div class="dh{" today" if is_today else ""}"><div class="dn">{day:%a}</div>'
            f'<div class="dd">{day.day}</div></div>')
        items = []
        for ev in events:
            seg = _segments(ev, day)
            if seg:
                items.append({"event": ev, "s": seg[0], "e": seg[1], "start": seg[2], "end": seg[3]})
        chips = "".join(_event_html(it) for it in _lanes(items))
        now_line = ""
        if is_today:
            minutes = now.hour * 60 + now.minute
            if DAY_START_HOUR * 60 <= minutes < DAY_END_HOUR * 60:
                now_line = f'<div class="now" style="top:{(minutes - DAY_START_HOUR * 60) * PX_PER_MIN:.1f}px"></div>'
        cols.append(f'<div class="col{" todaycol" if is_today else ""}">{chips}{now_line}</div>')

    gutter = "".join(
        f'<div class="hl" style="top:{(h - DAY_START_HOUR) * 60 * PX_PER_MIN:.1f}px">'
        f'{"" if h == DAY_START_HOUR else f"{h:02d}:00"}</div>' for h in hours)
    lines = "".join(
        f'<div class="line" style="top:{(h - DAY_START_HOUR) * 60 * PX_PER_MIN:.1f}px"></div>' for h in hours)
    n = len(days)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box}}
body{{margin:0;font-family:Roboto,"Google Sans",Arial,sans-serif;background:#fff;color:#3c4043}}
.cal{{border:1px solid #dadce0;border-radius:12px;overflow:hidden;background:#fff}}
.head{{display:grid;grid-template-columns:56px repeat({n},1fr);height:{HEADER_PX}px;border-bottom:1px solid #dadce0}}
.dh{{text-align:center;padding-top:8px}}
.dn{{font-size:11px;font-weight:500;letter-spacing:.8px;text-transform:uppercase;color:#70757a}}
.dd{{font-size:24px;line-height:36px;width:36px;height:36px;margin:2px auto 0;border-radius:50%;color:#3c4043}}
.today .dn{{color:#1a73e8}} .today .dd{{background:#1a73e8;color:#fff}}
.body{{position:relative;display:grid;grid-template-columns:56px repeat({n},1fr);height:{body_h:.0f}px}}
.gutter{{position:relative}}
.hl{{position:absolute;right:8px;transform:translateY(-7px);font-size:10px;color:#70757a}}
.grid{{position:absolute;left:56px;right:0;top:0;bottom:0;pointer-events:none;z-index:0}}
.line{{position:absolute;left:0;right:0;border-top:1px solid #f1f3f4}}
.col{{position:relative;border-left:1px solid #dadce0;z-index:1}}
.todaycol{{background:rgba(26,115,232,.04)}}
.ev{{position:absolute;border-radius:6px;padding:2px 6px;overflow:hidden;font-size:11.5px;line-height:1.25;
     box-shadow:0 1px 2px rgba(60,64,67,.25);cursor:default}}
.ev:hover{{box-shadow:0 2px 6px rgba(60,64,67,.4);z-index:5}}
.ev .t{{font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ev .m{{opacity:.9;font-size:10.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.ev.completed .t{{text-decoration:line-through}}
.now{{position:absolute;left:-1px;right:0;border-top:2px solid #ea4335;z-index:6}}
.now:before{{content:"";position:absolute;left:-6px;top:-7px;width:12px;height:12px;border-radius:50%;background:#ea4335}}
</style></head><body>
<div class="cal"><div class="head">{"".join(head)}</div>
<div class="body"><div class="grid">{lines}</div><div class="gutter">{gutter}</div>{"".join(cols)}</div></div>
</body></html>"""
