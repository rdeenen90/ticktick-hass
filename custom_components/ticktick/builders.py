"""Turn friendly service input into the values TickTick expects."""

import re
from typing import Any

from .ticktick_api_python.models.check_list_item import CheckListItem

_UNIT_MINUTES = {
    "m": 1,
    "min": 1,
    "minute": 1,
    "minutes": 1,
    "h": 60,
    "hour": 60,
    "hours": 60,
    "d": 1440,
    "day": 1440,
    "days": 1440,
    "w": 10080,
    "week": 10080,
    "weeks": 10080,
}
_BEFORE = re.compile(r"^(\d+)\s*([a-z]+)(?:\s+before)?$")
_AT_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")

_REPEAT_WORDS = {
    "daily": "FREQ=DAILY;INTERVAL=1",
    "weekly": "FREQ=WEEKLY;INTERVAL=1",
    "monthly": "FREQ=MONTHLY;INTERVAL=1",
    "yearly": "FREQ=YEARLY;INTERVAL=1",
    "weekdays": "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,TU,WE,TH,FR",
}
_REPEAT_UNITS = {
    "day": "DAILY",
    "days": "DAILY",
    "week": "WEEKLY",
    "weeks": "WEEKLY",
    "month": "MONTHLY",
    "months": "MONTHLY",
    "year": "YEARLY",
    "years": "YEARLY",
}
_EVERY = re.compile(r"^every\s+(?:(\d+)\s+)?([a-z]+)$")


def build_reminder(value: Any) -> str:
    """Return one TickTick reminder trigger.

    Accepts a raw trigger ("TRIGGER:-PT30M"), a time before the task is due
    ("30 minutes", "2h", "1 day"; a bare number is minutes), "on time", or
    "HH:MM" for that time on the day of an all-day task.
    """
    if isinstance(value, bool):
        raise ValueError(f"Invalid reminder: {value!r}")
    if isinstance(value, int):
        return _minutes_before(value)
    if not isinstance(value, str):
        raise ValueError(f"Invalid reminder: {value!r}")

    text = value.strip()
    if text.upper().startswith("TRIGGER:"):
        return text
    text = text.lower()
    if text in ("on time", "at time", "0"):
        return "TRIGGER:PT0S"
    if text.isdigit():
        return _minutes_before(int(text))
    if match := _AT_TIME.match(text):
        hours, minutes = int(match[1]), int(match[2])
        if hours < 24 and minutes < 60:
            return f"TRIGGER:P0DT{hours}H{minutes}M0S"
    if (match := _BEFORE.match(text)) and match[2] in _UNIT_MINUTES:
        return _minutes_before(int(match[1]) * _UNIT_MINUTES[match[2]])
    raise ValueError(
        f"Invalid reminder: {value!r}. Use e.g. '30 minutes', '1 day', 'on time', "
        "'09:00' or a raw 'TRIGGER:...' value"
    )


def build_reminders(value: Any) -> list[str]:
    """Return TickTick reminder triggers for one reminder or a list of them."""
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [build_reminder(item) for item in values]


def build_repeat_flag(value: Any) -> str | None:
    """Return a TickTick repeat rule.

    Accepts a raw rule ("RRULE:FREQ=DAILY;INTERVAL=1"), "daily", "weekly",
    "monthly", "yearly", "weekdays" or "every 2 weeks".
    """
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid repeat rule: {value!r}")

    text = value.strip()
    if text.upper().startswith("RRULE:"):
        return text
    if text.upper().startswith("FREQ="):
        return f"RRULE:{text}"
    text = text.lower()
    if text in _REPEAT_WORDS:
        return f"RRULE:{_REPEAT_WORDS[text]}"
    if (match := _EVERY.match(text)) and match[2] in _REPEAT_UNITS:
        interval = int(match[1] or 1)
        if interval > 0:
            return f"RRULE:FREQ={_REPEAT_UNITS[match[2]]};INTERVAL={interval}"
    raise ValueError(
        f"Invalid repeat rule: {value!r}. Use 'daily', 'weekly', 'monthly', "
        "'yearly', 'weekdays', 'every 2 weeks' or a raw 'RRULE:...' value"
    )


def build_items(value: Any) -> list[CheckListItem]:
    """Return subtasks from a list of titles or of {title, completed, id} objects."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Subtasks must be a list")

    items = []
    for entry in value:
        if isinstance(entry, str):
            entry = {"title": entry}
        if not isinstance(entry, dict) or not str(entry.get("title") or "").strip():
            raise ValueError(f"Invalid subtask: {entry!r}. Each subtask needs a title")
        data = {k: v for k, v in entry.items() if k != "completed"}
        if "completed" in entry:
            data["status"] = 1 if entry["completed"] else 0
        items.append(CheckListItem.from_dict(data))
    return items


def _minutes_before(minutes: int) -> str:
    return f"TRIGGER:-PT{minutes}M" if minutes else "TRIGGER:PT0S"
