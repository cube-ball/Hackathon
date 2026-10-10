"""The only place the UI calls the backend. No API keys belong in UI files."""
from copy import deepcopy
from datetime import datetime
from uuid import uuid4
from config import DEMO_MODE


def perform_action(action, state):
    # Copy first: a failing backend must not mutate the visible plan.
    if DEMO_MODE:
        result = demo_action(action, deepcopy(state))
    else:
        from backend_bridge import handle_action
        result = handle_action(action, deepcopy(state))
    if not isinstance(result, dict) or not isinstance(result.get("reply"), str):
        raise ValueError("Expected a reply string and state object")
    plan = result.get("state")
    if not isinstance(plan, dict):
        raise ValueError("Missing planner state")
    for key in ("tasks", "commitments", "sessions", "warnings"):
        if not isinstance(plan.get(key), list):
            raise ValueError(f"Expected list: {key}")
    # Backend owns deeper validation of constraints and field contents.
    return result


def demo_action(action, state):
    kind = action["type"]
    if kind == "chat":
        return {"reply": "Demo only: your message reached the service adapter. Connect OpenRouter in backend_bridge.py to interpret it. Use the forms to test adding tasks and commitments.", "state": state}
    if kind == "save_task":
        task = dict(action["task"])
        task.setdefault("id", str(uuid4()))
        task.update(priority="Not assessed", reason="Awaiting backend prioritisation.")
        state["tasks"] = [t for t in state["tasks"] if t["id"] != task["id"]] + [task]
        # Discard stale future sessions when estimates/deadlines change.
        state["sessions"] = [s for s in state["sessions"] if s["task_id"] != task["id"] or s["status"] == "completed"]
        reply = "Task saved in this demo session. Automatic scheduling is not connected."
    elif kind == "add_commitment":
        item = dict(action["commitment"])
        item["id"] = str(uuid4())
        state["commitments"].append(item)
        # In demo mode invalidate affected planned blocks rather than claim replanning.
        a, b = datetime.fromisoformat(item["start"]), datetime.fromisoformat(item["end"])
        state["sessions"] = [s for s in state["sessions"] if s["status"] != "planned" or not (
            datetime.fromisoformat(s["start"]) < b and datetime.fromisoformat(s["end"]) > a)]
        reply = "Commitment saved. Any clashing planned sessions were removed; connect the backend to reschedule them."
    elif kind == "session_status":
        session = next(s for s in state["sessions"] if s["id"] == action["session_id"])
        if session["status"] != "planned":
            raise ValueError("Session already processed")
        session["status"] = action["status"]
        if action["status"] == "completed":
            minutes = int((datetime.fromisoformat(session["end"]) - datetime.fromisoformat(session["start"])).total_seconds() / 60)
            task = next(t for t in state["tasks"] if t["id"] == session["task_id"])
            task["remaining_minutes"] = max(0, task["remaining_minutes"] - minutes)
        reply = "Session updated. Demo mode does not automatically move missed work."
    else:
        raise ValueError("Unknown action")
    state["warnings"] = []
    for task in state["tasks"]:
        scheduled = sum(int((datetime.fromisoformat(s["end"]) - datetime.fromisoformat(s["start"])).total_seconds()/60)
                        for s in state["sessions"] if s["task_id"] == task["id"] and s["status"] == "planned")
        missing = max(0, task["remaining_minutes"] - scheduled)
        if missing:
            state["warnings"].append(f"{task['title']}: {missing} minutes unscheduled. Demo mode cannot determine whether this fits.")
    return {"reply": reply, "state": state}
