from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TERMINAL_STATUSES = {"completed", "cancelled"}
TRANSITIONS = {
    "start": {"draft", "paused"},
    "pause": {"running"},
    "resume": {"paused"},
    "cancel": {"draft", "running", "paused"},
}
TARGET_STATUS = {"start": "running", "pause": "paused", "resume": "running", "cancel": "cancelled"}


def transition_status(current: str, action: str) -> str:
    if current not in TRANSITIONS.get(action, set()):
        raise ValueError(f"cannot {action} campaign in {current} status")
    return TARGET_STATUS[action]


def dialing_allowed(
    schedule: dict[str, Any], *, now: datetime, contact_timezone: str | None = None
) -> bool:
    timezone = contact_timezone or str(schedule.get("timezone", "UTC"))
    try:
        local = now.astimezone(ZoneInfo(timezone))
    except ZoneInfoNotFoundError:
        return False
    days = schedule.get("days", [0, 1, 2, 3, 4])
    normalized = {int(day) for day in days}
    if local.weekday() not in normalized:
        return False
    window = schedule.get("window", {})
    start = time.fromisoformat(str(window.get("start", "08:00")))
    end = time.fromisoformat(str(window.get("end", "20:00")))
    legal_start, legal_end = time(8), time(20)
    effective_start, effective_end = max(start, legal_start), min(end, legal_end)
    return effective_start <= local.time().replace(tzinfo=None) < effective_end


def select_dispatchable(
    campaign: dict[str, Any],
    contacts: list[dict[str, Any]],
    calls: list[dict[str, Any]],
    do_not_call: set[str],
    *,
    now: datetime,
    plan_max_concurrency: int,
) -> list[dict[str, Any]]:
    if campaign.get("status") != "running" or not dialing_allowed(campaign["schedule"], now=now):
        return []
    schedule = campaign["schedule"]
    configured = int(schedule.get("max_concurrency", plan_max_concurrency))
    limit = max(0, min(configured, plan_max_concurrency))
    active = sum(
        1
        for call in calls
        if call.get("campaign_id") == campaign["id"]
        and call.get("status") in {"queued", "ringing", "in_progress"}
    )
    available = max(0, limit - active)
    due = []
    for contact in contacts:
        if contact.get("status") not in {"pending", "retry"} or contact["phone"] in do_not_call:
            continue
        next_attempt = contact.get("next_attempt_at")
        if next_attempt is not None and next_attempt > now:
            continue
        timezone = (contact.get("variables") or {}).get("timezone")
        if dialing_allowed(schedule, now=now, contact_timezone=timezone):
            due.append(contact)
    return due[:available]


def retry_at(
    status: str, attempts: int, policy: dict[str, Any], *, now: datetime
) -> datetime | None:
    if status not in {"no_answer", "busy", "failed"}:
        return None
    if attempts >= int(policy.get("max_attempts", 3)):
        return None
    delays = policy.get("delays_s", [300, 1800, 7200])
    delay = int(delays[min(max(attempts - 1, 0), len(delays) - 1)]) if delays else 300
    return now + timedelta(seconds=delay)
