from datetime import date, datetime, time, timedelta


def initial_state():
    # Use next Monday so the sample is always a clearly future week.
    today = date.today()
    monday = today + timedelta(days=7 - today.weekday())
    def stamp(day, hour):
        return datetime.combine(monday + timedelta(days=day), time(hour)).isoformat()
    return {
        "tasks": [
            {"id": "t1", "title": "Circuits report", "deadline": stamp(4, 17),
             "remaining_minutes": 180, "priority": "High", "reason": "Example priority: closest assignment deadline."},
            {"id": "t2", "title": "Programming assignment", "deadline": stamp(6, 18),
             "remaining_minutes": 120, "priority": "Medium", "reason": "Example priority: later deadline."}],
        "commitments": [
            {"id": "c1", "title": "Classes", "start": stamp(0, 9), "end": stamp(0, 12)},
            {"id": "c2", "title": "Work shift", "start": stamp(2, 17), "end": stamp(2, 22)},
            {"id": "c3", "title": "Commute", "start": stamp(0, 8), "end": stamp(0, 9)}],
        "sessions": [
            {"id": "s1", "task_id": "t1", "title": "Report: calculations", "start": stamp(0, 14), "end": stamp(0, 15), "status": "planned"},
            {"id": "s2", "task_id": "t1", "title": "Report: discussion", "start": stamp(1, 14), "end": stamp(1, 15), "status": "planned"},
            {"id": "s3", "task_id": "t1", "title": "Report: final checks", "start": stamp(3, 14), "end": stamp(3, 15), "status": "planned"}],
        "warnings": ["Demo: programming has 2 hours of work without scheduled sessions."]}
