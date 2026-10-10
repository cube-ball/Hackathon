"""OpenRouter call: turns a chat message into structured edits.

The model only proposes edits as JSON. bridge.py validates every field and
scheduler.py does all placement, so a bad model answer can't corrupt the plan.
"""
import json
import urllib.error
import urllib.request

from . import config
from . import timeutil as tu


class AIUnavailable(Exception):
    """No key configured, or OpenRouter could not be reached."""


SYSTEM_PROMPT = """You are {bot_name}, the personal study coach inside StudyFlow for {student}.
{persona}
Turn the student's message into edits for their plan. You never schedule study sessions
yourself: a separate scheduler places sessions after your edits are applied.

About the student:
{profile}

Current local time (Europe/Dublin): {now}
Interpret relative dates ("Friday", "tomorrow", "next week") from that time.
All times you output are Europe/Dublin wall times in the form YYYY-MM-DDTHH:MM:SS.

Current plan:
{plan}

Reply with ONE JSON object and nothing else:
{{
  "reply": "one or two friendly sentences saying what you understood",
  "actions": [ ... ]
}}

Allowed actions (use only these, exact field names):
- {{"kind":"add_task","title":str,"deadline":datetime,"remaining_minutes":int,"priority":"High"|"Medium"|"Low"|null,"module":str|null}}
  ("module" is one of the student's module codes when the work belongs to a module)
- {{"kind":"update_task","task_id":str,"title":str?,"deadline":datetime?,"remaining_minutes":int?,"priority":"High"|"Medium"|"Low"|null?}}
- {{"kind":"delete_task","task_id":str}}
- {{"kind":"add_commitment","title":str,"start":datetime,"end":datetime}}
  (lectures, work shifts, commutes, appointments, or time the student is unavailable;
   for something weekly, add each occurrence in the next 14 days)
- {{"kind":"remove_commitment","commitment_id":str}}
- {{"kind":"light_day","date":"YYYY-MM-DD","max_minutes":int}}
  (student is tired/busy that day; usually 0-60 minutes of study)
- {{"kind":"set_preferences","day_start":"HH:MM"?,"day_end":"HH:MM"?,"max_daily_minutes":int?,"session_minutes":int?}}
  (day_start/day_end = the window study may happen in, e.g. derived from wake time and bedtime)
- {{"kind":"clarify","question":str}}

Rules:
- Use task_id / commitment_id values exactly as listed in the current plan.
- If the student gives an estimate in hours, convert to minutes.
- If a new task has no deadline or no time estimate, use "clarify" and ask for it. Do not guess.
- If nothing needs to change (a greeting, or a question like "what's on tomorrow?"), return an empty
  actions list and answer in reply using the upcoming schedule above. Use the student's first name.
- Never invent tasks or commitments the student did not mention.
"""


STRICT_PERSONA = ("Be a strict but kind coach: hold the student to the plan, keep replies short, "
                  "never agree to drop work without moving it somewhere, protect sleep and meals, "
                  "and name the module code when talking about coursework.")
FRIENDLY_PERSONA = "Be friendly, encouraging and brief."


def _profile_summary(state):
    p = state.get("profile") or {}
    if not p:
        return "(no profile yet)"
    lines = [f"Name: {p.get('name', 'Student')}; {p.get('programme', '')} at {p.get('university', '')}"]
    if p.get("goals"):
        lines.append(f"Goals: {p['goals']}")
    if p.get("modules"):
        lines.append("Modules: " + "; ".join(f"{m['code']} {m['title']}" for m in p["modules"]))
    if p.get("commute"):
        lines.append(f"Commute: {p['commute'].get('route')} ({p['commute'].get('minutes_each_way')} min each way)")
    if p.get("sleep"):
        lines.append(f"Sleep: bed {p['sleep'].get('bedtime')}, wake {p['sleep'].get('wake')}")
    if p.get("job"):
        lines.append(f"Job: {p['job']}")
    return "\n".join(lines)


def _upcoming(state, now, days=7):
    end = now + tu.timedelta(days=days)
    items = []
    for c in state.get("commitments", []):
        start = tu.parse(c["start"])
        if now <= start < end:
            items.append((start, f"{tu.describe(start)}-{tu.local(tu.parse(c['end'])):%H:%M} {c['title']}"))
    for s in state.get("sessions", []):
        start = tu.parse(s["start"])
        if now <= start < end and s.get("status") == "planned":
            items.append((start, f"{tu.describe(start)}-{tu.local(tu.parse(s['end'])):%H:%M} STUDY {s['title']}"))
    items.sort()
    return "\n".join(text for _, text in items[:80]) or "(nothing scheduled)"


def _plan_summary(state):
    lines = []
    for t in state["tasks"]:
        module = f" [{t['module']}]" if t.get("module") else ""
        lines.append(f"task {t['id']}{module}: {t['title']} | due {t['deadline']} | {t['remaining_minutes']} min left")
    for c in state["commitments"]:
        if tu.parse(c["end"]) < tu.now() - tu.timedelta(days=1):
            continue                                   # keep the prompt short: skip old blocks
        lines.append(f"commitment {c['id']}: {c['title']} | {c['start']} -> {c['end']}")
    prefs = state.get("preferences") or {}
    if prefs:
        lines.append("preferences: " + json.dumps({k: prefs[k] for k in ("day_start", "day_end", "max_daily_minutes")
                                                    if k in prefs}))
    return "\n".join(lines) or "(empty: no tasks or commitments yet)"


def _extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model did not return JSON")
    return json.loads(text[start:end + 1])


def interpret(message, state, now=None):
    """Return {"reply": str, "actions": list} from the model (not yet validated)."""
    key = config.openrouter_key()
    if not key:
        raise AIUnavailable("OPENROUTER_API_KEY is not set")
    now = now or tu.now()
    profile = state.get("profile") or {}
    prompt = SYSTEM_PROMPT.format(
        bot_name=profile.get("bot_name", "StudyFlow"),
        student=profile.get("name", "the student"),
        persona=STRICT_PERSONA if profile.get("style", "strict") == "strict" else FRIENDLY_PERSONA,
        profile=_profile_summary(state),
        now=tu.local(now).strftime("%A %Y-%m-%dT%H:%M:%S"),
        plan=_plan_summary(state) + "\n\nUpcoming 7 days:\n" + _upcoming(state, now))
    body = {
        "model": config.OPENROUTER_MODEL,
        "temperature": 0,
        "max_tokens": 1200,
        "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": message}],
    }
    request = urllib.request.Request(
        config.OPENROUTER_URL, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "HTTP-Referer": config.APP_URL, "X-Title": "StudyFlow"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")[:300]
        raise AIUnavailable(f"OpenRouter returned {err.code}: {detail}") from err
    except (urllib.error.URLError, TimeoutError) as err:
        raise AIUnavailable(f"Could not reach OpenRouter: {err}") from err
    try:
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
    except (KeyError, IndexError, TypeError, ValueError) as err:
        raise AIUnavailable("The AI reply could not be understood. Try rephrasing.") from err
    if not isinstance(parsed, dict):
        raise AIUnavailable("The AI reply could not be understood. Try rephrasing.")
    actions = parsed.get("actions")
    return {"reply": str(parsed.get("reply") or "").strip(),
            "actions": actions if isinstance(actions, list) else []}
