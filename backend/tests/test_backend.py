"""Run from the repo root:  python -m unittest discover -s backend/tests -t .

No network needed: the AI and Stripe calls are replaced with fakes.
"""
import hashlib
import hmac
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from backend import ai, bridge, billing, calendar_view, config, demo_student, scheduler, store
from backend import timeutil as tu

NOW = tu.parse("2026-10-12T08:00:00")          # a Monday morning in Dublin


def empty():
    return {"tasks": [], "commitments": [], "sessions": [], "warnings": []}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(config, "DB_PATH", Path(self.tmp.name) / "test.db")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def act(self, action, state):
        result = bridge.handle_action(action, state, now=NOW)
        self.assertIsInstance(result["reply"], str)
        for key in ("tasks", "commitments", "sessions", "warnings"):
            self.assertIsInstance(result["state"][key], list)
        self.assertEqual(scheduler.check_invariants(result["state"], NOW), [])
        return result

    def add_task(self, state, title="Circuits report", due="2026-10-16T17:00:00", minutes=180):
        return self.act({"type": "save_task", "task": {"title": title, "deadline": due,
                                                        "remaining_minutes": minutes}}, state)["state"]


class SchedulerTests(Base):
    def test_task_is_fully_scheduled_inside_study_hours(self):
        state = self.add_task(empty())
        planned = [s for s in state["sessions"] if s["status"] == "planned"]
        total = sum(tu.minutes_between(tu.parse(s["start"]), tu.parse(s["end"])) for s in planned)
        self.assertEqual(total, 180)
        for s in planned:
            start, end = tu.local(tu.parse(s["start"])), tu.local(tu.parse(s["end"]))
            self.assertGreaterEqual(start.hour, 9)
            self.assertLessEqual((end.hour, end.minute), (21, 0))
        self.assertEqual(state["warnings"], [])
        self.assertIn(state["tasks"][0]["priority"], {"High", "Medium", "Low"})

    def test_commitment_moves_clashing_sessions(self):
        state = self.add_task(empty())
        first = state["sessions"][0]
        result = self.act({"type": "add_commitment", "commitment": {
            "title": "Lab", "start": first["start"], "end": first["end"]}}, state)
        self.assertNotIn(first["start"], [s["start"] for s in result["state"]["sessions"]])

    def test_complete_counts_once_and_missed_is_rescheduled(self):
        state = self.add_task(empty(), minutes=120)
        sid = state["sessions"][0]["id"]
        state = self.act({"type": "session_status", "session_id": sid, "status": "completed"}, state)["state"]
        self.assertEqual(state["tasks"][0]["remaining_minutes"], 60)
        with self.assertRaises(ValueError):
            bridge.handle_action({"type": "session_status", "session_id": sid, "status": "completed"}, state, now=NOW)
        planned = [s for s in state["sessions"] if s["status"] == "planned"]
        state = self.act({"type": "session_status", "session_id": planned[0]["id"], "status": "missed"}, state)["state"]
        self.assertEqual(state["tasks"][0]["remaining_minutes"], 60)
        still = [s for s in state["sessions"] if s["status"] == "planned"]
        self.assertEqual(sum(tu.minutes_between(tu.parse(s["start"]), tu.parse(s["end"])) for s in still), 60)
        self.assertEqual([s["status"] for s in state["sessions"]].count("completed"), 1)

    def test_overload_is_warned_not_faked(self):
        state = self.add_task(empty(), due="2026-10-12T12:00:00", minutes=600)
        self.assertTrue(any("could not be scheduled" in w for w in state["warnings"]))

    def test_never_schedules_in_the_past(self):
        state = self.add_task(empty())
        for s in state["sessions"]:
            self.assertGreaterEqual(tu.parse(s["start"]), NOW)

    def test_clock_change_week(self):
        later = tu.parse("2026-10-24T20:00:00")     # clocks go back 25 Oct 2026
        state = bridge.handle_action({"type": "save_task", "task": {
            "title": "Essay", "deadline": "2026-10-27T12:00:00", "remaining_minutes": 300}}, empty(), now=later)["state"]
        self.assertEqual(scheduler.check_invariants(state, later), [])
        self.assertEqual(tu.fmt(tu.parse("2026-10-25T01:30:00")), "2026-10-25T01:30:00")
        self.assertEqual(tu.fmt(tu.parse("2026-03-29T01:30:00")), "2026-03-29T02:30:00")  # skipped hour

    def test_bad_inputs_raise(self):
        with self.assertRaises(ValueError):
            bridge.handle_action({"type": "add_commitment", "commitment": {
                "title": "x", "start": "2026-10-12T10:00:00", "end": "2026-10-12T09:00:00"}}, empty(), now=NOW)
        with self.assertRaises(ValueError):
            bridge.handle_action({"type": "save_task", "task": {"title": "", "deadline": "2026-10-16T17:00:00",
                                                                "remaining_minutes": 10}}, empty(), now=NOW)
        with self.assertRaises(ValueError):
            bridge.handle_action({"type": "nope"}, empty(), now=NOW)

    def test_editing_task_keeps_completed_work(self):
        state = self.add_task(empty(), minutes=120)
        sid = state["sessions"][0]["id"]
        state = self.act({"type": "session_status", "session_id": sid, "status": "completed"}, state)["state"]
        tid = state["tasks"][0]["id"]
        state = self.act({"type": "save_task", "task": {"id": tid, "title": "Circuits report",
                                                         "deadline": "2026-10-18T17:00:00",
                                                         "remaining_minutes": 90}}, state)["state"]
        self.assertIn(sid, [s["id"] for s in state["sessions"]])
        self.assertEqual(len(state["tasks"]), 1)


class ChatTests(Base):
    def fake_ai(self, actions, reply="Got it."):
        return mock.patch.object(ai, "interpret", return_value={"reply": reply, "actions": actions})

    def test_chat_applies_valid_actions_and_skips_bad_ones(self):
        state = self.add_task(empty())
        tid = state["tasks"][0]["id"]
        actions = [
            {"kind": "add_commitment", "title": "Work", "start": "2026-10-14T17:00:00", "end": "2026-10-14T22:00:00"},
            {"kind": "light_day", "date": "2026-10-13", "max_minutes": 0},
            {"kind": "update_task", "task_id": tid, "priority": "High"},
            {"kind": "update_task", "task_id": "does-not-exist", "remaining_minutes": 5},
            {"kind": "launch_rocket"},
        ]
        with self.fake_ai(actions):
            result = self.act({"type": "chat", "message": "I work Wed 5-10 and I'm wrecked Tuesday",
                               "timezone": "Europe/Dublin"}, state)
        s = result["state"]
        self.assertEqual(len(s["commitments"]), 1)
        self.assertEqual(s["tasks"][0]["priority"], "High")
        for sess in s["sessions"]:
            self.assertNotEqual(tu.local(tu.parse(sess["start"])).date().isoformat(), "2026-10-13")
        self.assertIn("Skipped", result["reply"])
        self.assertIn("2 free AI update", result["reply"])

    def test_clarify_leaves_state_unchanged(self):
        state = self.add_task(empty())
        with self.fake_ai([{"kind": "clarify", "question": "When is it due?"}]):
            result = bridge.handle_action({"type": "chat", "message": "add an essay"}, state, now=NOW)
        self.assertEqual(result["reply"], "When is it due?")
        self.assertEqual(result["state"]["sessions"], state["sessions"])

    def test_missing_key_is_explained(self):
        with mock.patch.object(config, "openrouter_key", return_value=None):
            result = bridge.handle_action({"type": "chat", "message": "hi"}, empty(), now=NOW)
        self.assertIn("OPENROUTER_API_KEY", result["reply"])

    def test_quota_then_upgrade_link(self):
        state = empty()
        act = [{"kind": "add_task", "title": "T", "deadline": "2026-10-20T12:00:00", "remaining_minutes": 30}]
        with self.fake_ai(act):
            for _ in range(config.FREE_UPDATES):
                state = bridge.handle_action({"type": "chat", "message": "add T"}, state, now=NOW)["state"]
        with mock.patch.object(billing, "create_checkout", return_value=("cs_test_1", "https://checkout.stripe.com/x")):
            result = bridge.handle_action({"type": "chat", "message": "add more"}, state, now=NOW)
        self.assertIn("https://checkout.stripe.com/x", result["reply"])
        self.assertEqual(result["state"], bridge._normalise(state))

    def test_ai_json_extraction(self):
        self.assertEqual(ai._extract_json('```json\n{"reply":"x","actions":[]}\n```')["reply"], "x")


class StripeTests(Base):
    SECRET = "whsec_test123"

    def signed(self, event, t=None):
        payload = json.dumps(event).encode()
        t = t or int(time.time())
        sig = hmac.new(self.SECRET.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
        return payload, f"t={t},v1={sig}"

    def event(self):
        return {"type": "checkout.session.completed", "data": {"object": {
            "id": "cs_test_1", "client_reference_id": config.USER_ID, "amount_total": 900,
            "currency": "eur", "payment_status": "paid"}}}

    def test_signature_checks(self):
        payload, header = self.signed(self.event())
        self.assertEqual(billing.verify_webhook(payload, header, self.SECRET)["type"], "checkout.session.completed")
        with self.assertRaises(ValueError):
            billing.verify_webhook(payload + b" ", header, self.SECRET)
        old_payload, old_header = self.signed(self.event(), t=int(time.time()) - 3600)
        with self.assertRaises(ValueError):
            billing.verify_webhook(old_payload, old_header, self.SECRET)

    def test_webhook_unlocks_pro_once(self):
        self.assertIn("pro granted", billing.handle_event(self.event()))
        self.assertIn("duplicate", billing.handle_event(self.event()))
        user = store.get_user(config.USER_ID)
        self.assertEqual(user["tier"], "pro")
        self.assertIsNone(store.updates_remaining(user))

    def test_live_keys_refused(self):
        with mock.patch.object(config, "stripe_secret_key", return_value="sk_live_abc"):
            with self.assertRaises(billing.BillingError):
                billing.create_checkout("u")

    def test_flask_webhook_route(self):
        try:
            from backend.app import app
        except ImportError:
            self.skipTest("flask not installed")
        client = app.test_client()
        payload, header = self.signed(self.event())
        with mock.patch.object(config, "stripe_webhook_secret", return_value=self.SECRET):
            ok = client.post("/api/stripe/webhook", data=payload, headers={"Stripe-Signature": header})
            bad = client.post("/api/stripe/webhook", data=payload, headers={"Stripe-Signature": "t=1,v1=00"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.get_json()["error"]["code"], "bad_signature")
        self.assertEqual(client.get("/api/account").get_json()["tier"], "pro")


class DemoStudentTests(Base):
    def test_demo_week_is_valid_and_fits(self):
        state = demo_student.initial_state(NOW)
        self.assertEqual(scheduler.check_invariants(state, NOW), [])
        self.assertEqual(state["warnings"], [])
        self.assertEqual(len(state["profile"]["modules"]), 6)
        planned = [s for s in state["sessions"] if s["status"] == "planned"]
        self.assertTrue(planned)
        for s in planned:
            self.assertGreaterEqual(tu.minutes_between(tu.parse(s["start"]), tu.parse(s["end"])), 30)
            start, end = tu.local(tu.parse(s["start"])), tu.local(tu.parse(s["end"]))
            lunch_s, lunch_e = start.replace(hour=13, minute=0), start.replace(hour=14, minute=0)
            self.assertFalse(start < lunch_e and end > lunch_s, f"study over lunch: {s}")
            self.assertTrue(s.get("module"))

    def test_commitments_do_not_clash(self):
        state = demo_student.initial_state(NOW)
        self.assertFalse(any("clash" in w for w in state["warnings"]))

    def test_calendar_events_format(self):
        state = demo_student.initial_state(NOW)
        events = bridge.week_events(state, "2026-10-12")
        self.assertTrue(events)
        for e in events:
            for key in ("id", "title", "start", "end", "backgroundColor", "borderColor", "textColor", "extendedProps"):
                self.assertIn(key, e)
            day = e["start"][:10]
            self.assertTrue("2026-10-11" <= day <= "2026-10-18")
        kinds = {e["extendedProps"]["kind"] for e in events}
        self.assertTrue({"lecture", "lab", "study", "commute", "work"} <= kinds)
        self.assertEqual(len(bridge.week_events(state)), len(state["commitments"]) + len(state["sessions"]))
        self.assertTrue(calendar_view.legend(state))

    def test_reset_and_intro(self):
        result = self.act({"type": "reset_demo"}, empty())
        self.assertIn("Aoife", result["reply"])
        self.assertIn("Sparky", result["reply"])
        self.assertEqual(bridge.initial_state(NOW)["profile"]["name"], "Aoife Byrne")

    def test_prompt_includes_profile_and_schedule(self):
        state = demo_student.initial_state(NOW)
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"choices": [{"message": {"content": '{"reply":"ok","actions":[]}'}}]}).encode()

        def fake_urlopen(request, timeout=None):
            captured["body"] = json.loads(request.data.decode())
            return FakeResponse()

        with mock.patch.object(config, "openrouter_key", return_value="sk-or-test"), \
                mock.patch("urllib.request.urlopen", fake_urlopen):
            result = ai.interpret("what's on tomorrow?", state, NOW)
        system = captured["body"]["messages"][0]["content"]
        self.assertIn("Sparky", system)
        self.assertIn("EEEN30020 Circuit Theory", system)
        self.assertIn("Upcoming 7 days", system)
        self.assertEqual(result, {"reply": "ok", "actions": []})

    def test_ai_task_gets_module(self):
        state = demo_student.initial_state(NOW)
        act = [{"kind": "add_task", "title": "Revise for machines test", "deadline": "2026-10-22T09:00:00",
                "remaining_minutes": 120, "module": "eeen30090"}]
        with mock.patch.object(ai, "interpret", return_value={"reply": "Added.", "actions": act}):
            result = self.act({"type": "chat", "message": "machines test next thursday, 2 hours"}, state)
        task = [t for t in result["state"]["tasks"] if t["title"].startswith("Revise")][0]
        self.assertEqual(task["module"], "EEEN30090")


if __name__ == "__main__":
    unittest.main()
