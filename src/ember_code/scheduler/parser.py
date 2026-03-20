"""Natural language time parser for scheduling.

Supports formats like:
- "in 5 minutes", "in 2 hours", "in 1 day"
- "at 5pm", "at 17:00", "at 5:30pm"
- "tomorrow", "tomorrow at 9am"
- "2026-03-20 14:00"

Recurrence patterns:
- "every 30 minutes", "every 2 hours", "every 1 day"
- "daily", "hourly", "weekly"
- "daily at 9am", "weekly at 5pm"
"""

import re
from datetime import datetime, timedelta


def parse_time(text: str) -> datetime | None:
    """Parse a natural language time expression into a datetime.

    Returns None if the text can't be parsed.
    """
    text = text.strip().lower()

    # "in X minutes/hours/days"
    m = re.match(r"in\s+(\d+)\s+(min(?:ute)?s?|hours?|days?|secs?|seconds?)", text)
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("sec"):
            return datetime.now() + timedelta(seconds=amount)
        if unit.startswith("min"):
            return datetime.now() + timedelta(minutes=amount)
        if unit.startswith("hour"):
            return datetime.now() + timedelta(hours=amount)
        if unit.startswith("day"):
            return datetime.now() + timedelta(days=amount)

    # "at HH:MM" or "at H:MMam/pm" or "at Hpm"
    m = re.match(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = m.group(3)
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        target = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= datetime.now():
            target += timedelta(days=1)  # next occurrence
        return target

    # "tomorrow" or "tomorrow at ..."
    if text.startswith("tomorrow"):
        rest = text[len("tomorrow") :].strip()
        base = datetime.now() + timedelta(days=1)
        if rest.startswith("at"):
            inner = parse_time(rest)
            if inner:
                return base.replace(hour=inner.hour, minute=inner.minute, second=0, microsecond=0)
        return base.replace(hour=9, minute=0, second=0, microsecond=0)  # default 9am

    # ISO format "YYYY-MM-DD HH:MM"
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    return None


# ── Recurrence ──────────────────────────────────────────────────


_RECURRENCE_ALIASES = {
    "hourly": "every 1 hours",
    "daily": "every 1 days",
    "weekly": "every 7 days",
}


def parse_recurrence(text: str) -> tuple[str, datetime | None]:
    """Parse a recurrence pattern and compute the first scheduled time.

    Args:
        text: e.g. "every 30 minutes", "daily", "daily at 9am", "hourly"

    Returns:
        (canonical_recurrence, first_scheduled_at) or ("", None) if not a recurrence.
    """
    text = text.strip().lower()

    # "daily at 9am" → split into recurrence + time
    at_time: datetime | None = None
    for alias, canonical in _RECURRENCE_ALIASES.items():
        if text.startswith(alias):
            rest = text[len(alias) :].strip()
            if rest.startswith("at"):
                at_time = parse_time(rest)
            elif not rest:
                at_time = _next_occurrence(canonical)
            if at_time is not None:
                return canonical, at_time

    # "every N units"
    m = re.match(r"every\s+(\d+)\s+(min(?:ute)?s?|hours?|days?|weeks?)", text)
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        canonical = f"every {amount} {_normalize_unit(unit)}"

        # Check for "every 2 hours at 9am"
        rest = text[m.end() :].strip()
        at_time = parse_time(rest) if rest.startswith("at") else _next_occurrence(canonical)

        if at_time is not None:
            return canonical, at_time

    return "", None


def next_occurrence_from_recurrence(recurrence: str, last_run: datetime) -> datetime | None:
    """Compute the next occurrence given a recurrence pattern and the last run time.

    Args:
        recurrence: canonical form like "every 1 days", "every 30 minutes"
        last_run: when the task last ran

    Returns:
        The next scheduled datetime, or None if the pattern is invalid.
    """
    delta = _recurrence_to_delta(recurrence)
    if delta is None:
        return None
    return last_run + delta


def _next_occurrence(recurrence: str) -> datetime | None:
    """Compute the first occurrence from now."""
    delta = _recurrence_to_delta(recurrence)
    if delta is None:
        return None
    return datetime.now() + delta


def _recurrence_to_delta(recurrence: str) -> timedelta | None:
    """Convert canonical recurrence to timedelta."""
    m = re.match(r"every\s+(\d+)\s+(minutes?|hours?|days?|weeks?)", recurrence)
    if not m:
        return None
    amount = int(m.group(1))
    unit = m.group(2)
    if unit.startswith("minute"):
        return timedelta(minutes=amount)
    if unit.startswith("hour"):
        return timedelta(hours=amount)
    if unit.startswith("day"):
        return timedelta(days=amount)
    if unit.startswith("week"):
        return timedelta(weeks=amount)
    return None


def _normalize_unit(unit: str) -> str:
    """Normalize time unit to plural form."""
    if unit.startswith("min"):
        return "minutes"
    if unit.startswith("hour"):
        return "hours"
    if unit.startswith("day"):
        return "days"
    if unit.startswith("week"):
        return "weeks"
    return unit
