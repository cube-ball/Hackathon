# Backend handoff

This is a proposed contract: agree it with the team, then keep it stable.
`backend_bridge.py` (alongside app.py) must export `handle_action(action, state)`.
Return {"reply": str, "state": full_state}. On failure, raise an exception;
the frontend retains the previous plan. Never put secret keys in returned content.
For clarifications, return a question in reply and unchanged state. Persist pending
clarification context in your backend or extra state fields (the UI preserves them).

## State

- tasks: list of {id, title, deadline, remaining_minutes, priority, reason}
- commitments: list of {id, title, start, end}
- sessions: list of {id, task_id, title, start, end, status}
- warnings: list of human-readable strings

Priority and reason are strings. Status is planned, completed or missed.
IDs are stable unique strings. Effort is integer minutes >= 0.
The UI prototype exchanges ISO local wall times in Europe/Dublin, e.g.
2026-10-16T17:00:00. Do not mix naive and aware datetimes internally. Backend must
normalise to Europe/Dublin, handle ambiguous/nonexistent times around clock changes,
and return this same local format. A production version should adopt a coordinated
aware timestamp contract on both sides.

## Actions

Chat:
{"type":"chat","message":"I work Wednesday 5–10 pm","timezone":"Europe/Dublin"}
Use current Europe/Dublin date to interpret relative dates. Ask for missing details.
Don't fabricate a schedule if the workload cannot fit.

Add/edit task:
{"type":"save_task","task":{"title":"Report","deadline":"2026-10-16T17:00:00","remaining_minutes":180}}
An existing task includes id; otherwise assign one. Reassess/replan affected work.

Add fixed block:
{"type":"add_commitment","commitment":{"title":"Work","start":"2026-10-14T17:00:00","end":"2026-10-14T22:00:00"}}
Validate end > start, keep the block protected and replan affected study sessions.

Session status:
{"type":"session_status","session_id":"s1","status":"missed"}
Or status completed. Completion reduces remaining effort once; missed does not.
Never double-count completion. Keep completed work unchanged on replanning.

## Backend correctness checks

Positive session durations, valid task references, no overlapping planned sessions,
no conflicts with fixed blocks, planned work before deadlines, no scheduling in the
past, no duplicate allocation, and explicit unscheduled work. Validate AI outputs;
use code for arithmetic and constraint enforcement. Warn about fixed-block conflicts.

## Frontend responsibility

Collect input; show spinner; call the adapter; show reply/calendar/tasks/warnings.
The UI should not independently create a conflicting second scheduling algorithm.

## Persistence

This starter uses Streamlit session state, not SQLite. If implementing persistence,
provide a load function used on app startup and save accepted state in the backend.
Use per-user data isolation before adding multiple users. For today's demo, one
local synthetic student is sufficient. Never claim shared persistent accounts exist.
