"""Time helpers.

The frontend sends and expects naive ISO wall times in Europe/Dublin,
e.g. "2026-10-16T17:00:00". Internally everything is an aware UTC datetime,
so arithmetic and comparisons stay correct across the October/March clock changes.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Dublin")
UTC = timezone.utc


def parse(value):
    """ISO string -> aware UTC datetime. Naive strings are Dublin wall time."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected an ISO date-time string")
    text = value.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        # Ambiguous times (the repeated hour in October) take the first occurrence.
        # Non-existent times (the skipped hour in March) roll forward past the gap.
        dt = dt.replace(tzinfo=TZ, fold=0)
    return dt.astimezone(UTC)


def fmt(dt):
    """Aware datetime -> naive Dublin wall-time ISO string for the frontend."""
    return dt.astimezone(TZ).replace(tzinfo=None).isoformat(timespec="seconds")


def local(dt):
    return dt.astimezone(TZ)


def now():
    return datetime.now(UTC)


def at_local(day, hhmm):
    """A local calendar date + "HH:MM" -> aware UTC datetime."""
    hour, minute = parse_hhmm(hhmm)
    naive = datetime(day.year, day.month, day.day, hour, minute)
    return naive.replace(tzinfo=TZ, fold=0).astimezone(UTC)


def parse_hhmm(text):
    if not isinstance(text, str):
        raise ValueError("Expected HH:MM")
    parts = text.strip().split(":")
    if len(parts) != 2:
        raise ValueError("Expected HH:MM")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Time out of range")
    return hour, minute


def ceil_to(dt, minutes=15):
    """Round up to the next multiple of `minutes` (UTC-based; Dublin offsets are whole hours)."""
    step = minutes * 60
    ts = dt.timestamp()
    rounded = -(-int(ts) // step) * step
    return datetime.fromtimestamp(rounded, UTC)


def minutes_between(start, end):
    return int((end - start).total_seconds() // 60)


def describe(dt):
    """Short human label, e.g. 'Tue 14:00'."""
    return local(dt).strftime("%a %H:%M")


__all__ = ["TZ", "UTC", "parse", "fmt", "local", "now", "at_local", "parse_hhmm",
           "ceil_to", "minutes_between", "describe", "timedelta"]
