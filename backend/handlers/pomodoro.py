from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Tuple

from services.opik_service import track
from services.supabase_service import SupabaseService


@track(name="pomodoro_handler")
def start_pomodoro(supabase: SupabaseService, user: dict, message: str) -> str:
    work, rest = _parse_start_times(message, user)
    supabase.create_pomodoro_session(
        user["id"],
        "work",
        datetime.utcnow(),
        work,
        status="active",
        cycle_work_minutes=work,
        cycle_break_minutes=rest,
    )
    return (
        f"⏱ Focus session started! {work} minutes of work time. I'll let you know when it's time for a break."
    )


@track(name="pomodoro_handler")
def stop_pomodoro(supabase: SupabaseService, user: dict) -> tuple[str, dict]:
    active = supabase.get_active_sessions_for_user(user["id"])
    now = datetime.utcnow()
    for session in active:
        supabase.update_pomodoro_session(
            session["id"],
            {"status": "cancelled", "end_time": now.isoformat()},
        )
    if not active:
        return "No active session to stop.", {"context": "idle", "data": {}}
    response = "Session stopped. What were you working on?"
    context = {"context": "awaiting_pomodoro_summary", "data": {"session_id": active[0]["id"]}}
    return response, context


@track(name="backfill_parser")
def handle_backfill(supabase: SupabaseService, user: dict, backfill: dict) -> str:
    start_time = backfill.get("start_time")
    end_time = backfill.get("end_time")
    description = backfill.get("description") or "Backfilled work"
    if not start_time or not end_time:
        return "I couldn't parse the time range. Try: 'I worked on X from 2pm to 4pm'."
    duration = int((end_time - start_time).total_seconds() / 60)
    supabase.create_pomodoro_session(
        user["id"],
        "work",
        start_time,
        duration,
        status="completed",
        is_backfill=True,
        what_did_you_do=description,
    )
    return (
        f"Got it! Logged {duration} minutes of work on '{description}' from {start_time.strftime('%-I:%M %p')} "
        f"to {end_time.strftime('%-I:%M %p')}."
    )


@track(name="pomodoro_handler")
def handle_summary(supabase: SupabaseService, session_id: str, message: str) -> str:
    supabase.update_pomodoro_session(session_id, {"what_did_you_do": message, "status": "completed"})
    return "Nice. Logged your session summary."


def get_stats(supabase: SupabaseService, user: dict, start_iso: str, end_iso: str) -> str:
    sessions = supabase._execute(
        supabase.client.table("pomodoro_sessions")
        .select("*")
        .eq("user_id", user["id"])
        .eq("session_type", "work")
        .gte("start_time", start_iso)
        .lte("start_time", end_iso)
    )
    if not sessions:
        return "No focus sessions logged today."
    total_minutes = 0
    items = []
    for session in sessions:
        start = datetime.fromisoformat(session["start_time"].replace("Z", "+00:00"))
        end = session.get("end_time")
        if end:
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            total_minutes += int((end_dt - start).total_seconds() / 60)
        if session.get("what_did_you_do"):
            items.append(f"- {session['what_did_you_do']}")
    hours = round(total_minutes / 60, 2)
    summary = f"Today you've focused for {hours} hours across {len(sessions)} sessions."
    if items:
        summary += "\nHere's what you did:\n" + "\n".join(items)
    return summary


def _parse_start_times(message: str, user: dict) -> Tuple[int, int]:
    numbers = [int(n) for n in re.findall(r"\d+", message)]
    if not numbers:
        return user.get("default_work_minutes", 25), user.get("default_break_minutes", 5)
    if len(numbers) == 1:
        return numbers[0], user.get("default_break_minutes", 5)
    return numbers[0], numbers[1]
