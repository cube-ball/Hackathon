# Talk-to-Plan Student Planner

## Purpose
A weekly planner for students that you update by talking to it. It turns deadlines, sleep schedule, commute and commitments into a workable week, then re-plans when something changes ("I'm wrecked Tuesday", "bus is cancelled Thursday").

## Target user
UCD undergraduates juggling lectures, assignments, part-time work and a bus commute, who find Google Calendar too manual to maintain. Assumption to validate: they will type or speak a short message instead of dragging events around.

## Core user flow
1. Open the app. An anonymous user ID is created.
2. **Setup:** enter sleep window, commute (route, minutes each way) and fixed commitments (lectures, work).
3. Add deadlines (title, due date, estimated hours, priority).
4. Click **Generate week**. The backend builds a plan around sleep, commute and commitments, with each block carrying a short reason.
5. View the week plan, with a streamed AI explanation of why it is shaped this way.
6. Type a message in the chat bar. The AI parses it into structured constraints, the scheduler re-plans, and the UI highlights what moved.
7. After 3 free updates, the app shows the upgrade prompt. The student pays via Stripe Checkout (sandbox) and gets unlimited updates immediately.

## Pages
- `/setup`: sleep, commute, commitments, deadlines.
- `/` (planner): week view, chat bar, change highlights, "why" panel.
- `/upgrade`: Semester Pass details and Buy button.
- `/success`: polls entitlement until the webhook has unlocked Pro.

## Data stored (SQLite)
- **users:** id, tier (free/pro), updates_used
- **preferences:** sleep target, bedtime, wake time, commute route and minutes
- **commitments** and **deadlines:** title, times, est_hours, priority
- **plans** and **blocks:** week_start, block type, start, end, reason, locked flag
- **update_log:** user message, parsed constraints (JSON), timestamp
- **sleep_logs:** date, bedtime, wake time (from chat)
- **orders:** stripe_session_id, amount_cents, currency, status

Not stored: card data (Stripe holds it) and real student timetables (demo uses synthetic data).

## How Stripe is used
- **Product:** Semester Pass, 900 cents (EUR 9.00), one-time. Free tier gets 3 chat updates; Pro is unlimited.
- Flask creates a Checkout Session (`mode=payment`) with `client_reference_id = user_id`.
- Stripe redirects to `/success`, but access is granted only by the `checkout.session.completed` webhook (signature verified), which sets `tier=pro` and records the order.
- Sandbox only. Test card 4242 4242 4242 4242.

## AI (OpenRouter)
- **Backend (Flask):** parses chat messages and sleep reports into structured constraints. The LLM never places blocks; the scheduler does.
- **Frontend (Next.js route handler):** streams the "why this plan" explanation. API key stays server-side.
