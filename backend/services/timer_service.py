from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from config import settings
from services.opik_service import set_trace_context, track
from services.supabase_service import SupabaseService
from services.twilio_service import TwilioService
from utils.thread_utils import phone_hash, thread_id_for_day


class TimerService:
    def __init__(self, supabase: SupabaseService, twilio: TwilioService) -> None:
        self.supabase = supabase
        self.twilio = twilio
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if not self._task:
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            try:
                await self._check_pomodoros()
                await self._check_task_reminders()
                await self._check_nudges()
            except Exception:
                # Avoid crashing loop
                pass
            await asyncio.sleep(settings.POMODORO_POLL_SECONDS)

    @track(name="pomodoro_handler")
    async def _check_pomodoros(self) -> None:
        now = datetime.now(timezone.utc)
        sessions = self.supabase.get_active_sessions()
        for session in sessions:
            end_time = session.get("end_time")
            if not end_time:
                continue
            try:
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if end_dt > now:
                continue

            # Mark session complete
            self.supabase.update_pomodoro_session(session["id"], {"status": "completed"})

            user_id = session["user_id"]
            user = self.supabase._execute(
                self.supabase.client.table("users").select("*").eq("id", user_id).limit(1)
            )
            if not user:
                continue
            user = user[0]
            phone_number = user["phone_number"]
            thread_id = thread_id_for_day(phone_number, user.get("timezone", "UTC"))
            set_trace_context(
                thread_id=thread_id,
                metadata={
                    "user_id": user.get("id"),
                    "phone_hash": phone_hash(phone_number),
                    "feature": "pomodoro",
                },
                tags=["whatsapp", "system"],
            )

            if session["session_type"] == "work":
                # Start break immediately (use session cycle if present)
                break_minutes = session.get("cycle_break_minutes") or user.get("default_break_minutes", 5)
                self.supabase.create_pomodoro_session(
                    user_id,
                    "break",
                    now,
                    break_minutes,
                    status="active",
                    cycle_work_minutes=session.get("cycle_work_minutes") or user.get("default_work_minutes", 25),
                    cycle_break_minutes=break_minutes,
                )
                self.twilio.send_message(
                    phone_number,
                    f"⏱ Work block complete! Take a {break_minutes}-minute break.\n"
                    "Quick check-in — what did you work on?",
                )
                self.supabase.upsert_state(
                    user_id,
                    phone_number,
                    "awaiting_pomodoro_summary",
                    {
                        "session_id": session["id"],
                        "summary_requested_at": now.isoformat(),
                        "summary_nudged": False,
                    },
                )
            else:
                # Start next work session automatically unless stopped
                work_minutes = session.get("cycle_work_minutes") or user.get("default_work_minutes", 25)
                self.supabase.create_pomodoro_session(
                    user_id,
                    "work",
                    now,
                    work_minutes,
                    status="active",
                    cycle_work_minutes=work_minutes,
                    cycle_break_minutes=session.get("cycle_break_minutes") or user.get("default_break_minutes", 5),
                )
                self.twilio.send_message(
                    phone_number,
                    f"✅ Break over. Starting a {work_minutes}-minute focus block now.\n"
                    "Send 'stop' anytime to end.",
                )

    async def _check_task_reminders(self) -> None:
        now = datetime.now(timezone.utc)
        due_tasks = self.supabase.fetch_due_task_reminders(now)
        for task in due_tasks:
            user_id = task["user_id"]
            user = self.supabase._execute(
                self.supabase.client.table("users").select("*").eq("id", user_id).limit(1)
            )
            if not user:
                continue
            phone_number = user[0]["phone_number"]
            thread_id = thread_id_for_day(phone_number, user[0].get("timezone", "UTC"))
            set_trace_context(
                thread_id=thread_id,
                metadata={
                    "user_id": user_id,
                    "phone_hash": phone_hash(phone_number),
                    "feature": "task_reminder",
                },
                tags=["whatsapp", "system"],
            )
            self.twilio.send_message(phone_number, f"⏰ Reminder: {task['title']}")
            self.supabase.mark_task_reminder_sent(task["id"])

    async def _check_nudges(self) -> None:
        now = datetime.now(timezone.utc)
        states = self.supabase._execute(
            self.supabase.client.table("conversation_state")
            .select("*")
            .eq("current_context", "awaiting_pomodoro_summary")
        )
        for state in states:
            data = state.get("context_data") or {}
            requested_at = data.get("summary_requested_at")
            nudged = data.get("summary_nudged")
            if not requested_at or nudged:
                continue
            user = self.supabase._execute(
                self.supabase.client.table("users").select("*").eq("id", state["user_id"]).limit(1)
            )
            tz = "UTC"
            if user:
                tz = user[0].get("timezone", "UTC")
            thread_id = thread_id_for_day(state["phone_number"], tz)
            set_trace_context(
                thread_id=thread_id,
                metadata={
                    "user_id": state.get("user_id"),
                    "phone_hash": phone_hash(state["phone_number"]),
                    "feature": "pomodoro_nudge",
                },
                tags=["whatsapp", "system"],
            )
            try:
                requested_dt = datetime.fromisoformat(requested_at.replace("Z", "+00:00"))
                if requested_dt.tzinfo is None:
                    requested_dt = requested_dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
            if (now - requested_dt).total_seconds() >= settings.POMODORO_NUDGE_SECONDS:
                self.twilio.send_message(
                    state["phone_number"],
                    "Quick reminder — what did you work on in that last focus session?",
                )
                data["summary_nudged"] = True
                self.supabase.upsert_state(state["user_id"], state["phone_number"], "awaiting_pomodoro_summary", data)
