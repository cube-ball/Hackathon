# Flask Backend

Base URL: `http://localhost:5000`
Headers on every request except the webhook: `X-User-Id: <anonymous id>`
Money is in **cents**. Times are ISO 8601 (Europe/Dublin).
Errors: `{"error": {"code": "string", "message": "string"}}`

---

## 1. POST /api/plan/generate
Builds a week plan from setup data, scheduling around sleep, commute and commitments.

**Request**
```json
{
  "week_start": "2026-10-12",
  "sleep": { "target_hours": 8, "bedtime": "23:30", "wake": "07:30" },
  "commute": { "route": "46A", "minutes_each_way": 40 },
  "commitments": [
    { "title": "Stats lecture", "day": "mon", "start": "09:00", "end": "10:00" }
  ],
  "deadlines": [
    { "title": "Stats assignment", "due": "2026-10-16T17:00:00+01:00", "est_hours": 4, "priority": "high" }
  ]
}
```

**Response 200**
```json
{
  "plan_id": "pl_8f2a",
  "week_start": "2026-10-12",
  "blocks": [
    {
      "id": "b_01",
      "type": "commute",
      "title": "Bus to UCD (46A)",
      "start": "2026-10-12T08:05:00+01:00",
      "end": "2026-10-12T08:45:00+01:00",
      "reason": "Lecture at 09:00 plus 15 min buffer",
      "locked": false
    },
    {
      "id": "b_02",
      "type": "study",
      "title": "Stats assignment (session 1/2)",
      "start": "2026-10-13T16:00:00+01:00",
      "end": "2026-10-13T18:00:00+01:00",
      "reason": "High priority, due Fri 17:00, free slot after commute",
      "locked": false
    }
  ],
  "warnings": [],
  "tier": "free",
  "updates_remaining": 3
}
```
`warnings` lists anything that could not be scheduled, e.g. `"Only 6h free this week for 9h of deadlines"`.

---

## 2. POST /api/plan/update
Natural-language change. The backend parses the message via OpenRouter into constraints, then the scheduler re-plans. Returns `402` when the free quota is used up.

**Request**
```json
{
  "plan_id": "pl_8f2a",
  "message": "I'm wrecked Tuesday and the bus is cancelled Thursday"
}
```

**Response 200**
```json
{
  "plan_id": "pl_8f2a",
  "parsed_constraints": [
    { "kind": "reduce_load", "date": "2026-10-13", "reason": "tired" },
    { "kind": "no_commute", "date": "2026-10-15", "reason": "bus cancelled" }
  ],
  "changes": [
    {
      "block_id": "b_02",
      "action": "moved",
      "from": "2026-10-13T16:00:00+01:00",
      "to": "2026-10-14T16:00:00+01:00",
      "reason": "Lighter Tuesday; still finishes before the Friday deadline"
    }
  ],
  "warnings": [],
  "updates_remaining": 2
}
```

**Response 402 (free quota used)**
```json
{ "error": { "code": "upgrade_required", "message": "Free updates used. Upgrade to continue." } }
```

---

## 3. GET /api/plan?plan_id=pl_8f2a
Returns the current plan and the user's entitlement. The frontend polls this on `/success` until `tier` becomes `pro`.

**Response 200**
```json
{
  "plan_id": "pl_8f2a",
  "week_start": "2026-10-12",
  "blocks": [
    {
      "id": "b_02",
      "type": "study",
      "title": "Stats assignment (session 1/2)",
      "start": "2026-10-14T16:00:00+01:00",
      "end": "2026-10-14T18:00:00+01:00",
      "reason": "Lighter Tuesday; still finishes before the Friday deadline",
      "locked": false
    }
  ],
  "tier": "pro",
  "updates_remaining": null
}
```
`updates_remaining` is `null` for Pro (unlimited).

---

## 4. POST /api/checkout
Creates a Stripe Checkout Session (sandbox) for the Semester Pass.

**Request**
```json
{
  "success_url": "http://localhost:3000/success",
  "cancel_url": "http://localhost:3000/upgrade"
}
```

**Response 200**
```json
{
  "session_id": "cs_test_a1B2c3",
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_a1B2c3",
  "product": "Semester Pass",
  "amount": 900,
  "currency": "eur"
}
```

---

## 5. POST /api/stripe/webhook
Called by Stripe, not the frontend. No `X-User-Id`; the body is the raw event, verified with the `Stripe-Signature` header. On `checkout.session.completed` the backend sets `tier=pro` for `client_reference_id` and records the order.

**Request body (abridged Stripe event)**
```json
{
  "type": "checkout.session.completed",
  "data": {
    "object": {
      "id": "cs_test_a1B2c3",
      "client_reference_id": "u_42",
      "amount_total": 900,
      "currency": "eur",
      "payment_status": "paid"
    }
  }
}
```

**Response 200**
```json
{ "received": true }
```
Invalid signature returns `400` with `{"error": {"code": "bad_signature", "message": "..."}}`.
