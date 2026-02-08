from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from postgrest.exceptions import APIError
from supabase import Client, create_client

from config import settings


class SupabaseService:
    def __init__(self) -> None:
        self.client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SECRET_KEY)

    def _execute(self, query) -> Any:
        response = query.execute()
        if hasattr(response, "error") and response.error:
            raise RuntimeError(response.error)
        return response.data

    # Users
    def get_user_by_phone(self, phone_number: str) -> dict | None:
        data = self._execute(
            self.client.table("users").select("*").eq("phone_number", phone_number).limit(1)
        )
        return data[0] if data else None

    def create_user(self, phone_number: str) -> dict:
        payload = {"phone_number": phone_number}
        data = self._execute(self.client.table("users").insert(payload))
        return data[0]

    def update_user(self, user_id: str, fields: dict) -> dict:
        fields["updated_at"] = datetime.utcnow().isoformat()
        data = self._execute(self.client.table("users").update(fields).eq("id", user_id))
        return data[0]

    def get_or_create_user(self, phone_number: str) -> dict:
        user = self.get_user_by_phone(phone_number)
        if user:
            return user
        return self.create_user(phone_number)

    # Conversation state
    def get_state(self, user_id: str) -> dict | None:
        data = self._execute(
            self.client.table("conversation_state").select("*").eq("user_id", user_id).limit(1)
        )
        return data[0] if data else None

    def upsert_state(self, user_id: str, phone_number: str, context: str | None, context_data: dict) -> dict:
        payload = {
            "user_id": user_id,
            "phone_number": phone_number,
            "current_context": context,
            "context_data": context_data,
            "updated_at": datetime.utcnow().isoformat(),
        }
        try:
            data = self._execute(
                self.client.table("conversation_state").upsert(payload, on_conflict="user_id")
            )
            return data[0]
        except APIError as exc:
            # Fallback if unique constraint is missing
            if "42P10" not in str(exc):
                raise
            existing = self._execute(
                self.client.table("conversation_state").select("*").eq("user_id", user_id).limit(1)
            )
            if existing:
                data = self._execute(
                    self.client.table("conversation_state").update(payload).eq("user_id", user_id)
                )
                return data[0]
            data = self._execute(self.client.table("conversation_state").insert(payload))
            return data[0]

    def clear_state(self, user_id: str) -> None:
        self._execute(self.client.table("conversation_state").delete().eq("user_id", user_id))

    # Pomodoro
    def create_pomodoro_session(
        self,
        user_id: str,
        session_type: str,
        start_time: datetime,
        duration_minutes: int,
        status: str = "active",
        is_backfill: bool = False,
        what_did_you_do: str | None = None,
        cycle_work_minutes: int | None = None,
        cycle_break_minutes: int | None = None,
    ) -> dict:
        end_time = start_time + timedelta(minutes=duration_minutes)
        payload = {
            "user_id": user_id,
            "session_type": session_type,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "planned_duration_minutes": duration_minutes,
            "status": status,
            "is_backfill": is_backfill,
            "what_did_you_do": what_did_you_do,
        }
        if cycle_work_minutes is not None:
            payload["cycle_work_minutes"] = cycle_work_minutes
        if cycle_break_minutes is not None:
            payload["cycle_break_minutes"] = cycle_break_minutes
        data = self._execute(self.client.table("pomodoro_sessions").insert(payload))
        return data[0]

    def update_pomodoro_session(self, session_id: str, fields: dict) -> dict:
        data = self._execute(
            self.client.table("pomodoro_sessions").update(fields).eq("id", session_id)
        )
        return data[0]

    def get_active_sessions(self) -> list[dict]:
        data = self._execute(
            self.client.table("pomodoro_sessions").select("*").eq("status", "active")
        )
        return data

    def get_active_sessions_for_user(self, user_id: str) -> list[dict]:
        data = self._execute(
            self.client.table("pomodoro_sessions").select("*").eq("status", "active").eq("user_id", user_id)
        )
        return data

    # Tasks
    def insert_task(self, user_id: str, title: str, raw_message: str, reminder_time: datetime | None) -> dict:
        payload = {
            "user_id": user_id,
            "title": title,
            "raw_message": raw_message,
            "reminder_time": reminder_time.isoformat() if reminder_time else None,
        }
        data = self._execute(self.client.table("tasks").insert(payload))
        return data[0]

    def list_incomplete_tasks(self, user_id: str) -> list[dict]:
        data = self._execute(
            self.client.table("tasks")
            .select("*")
            .eq("user_id", user_id)
            .eq("completed", False)
            .order("created_at", desc=False)
        )
        return data

    def complete_task(self, task_id: str) -> dict:
        payload = {"completed": True, "completed_at": datetime.utcnow().isoformat()}
        data = self._execute(self.client.table("tasks").update(payload).eq("id", task_id))
        return data[0]

    def fetch_due_task_reminders(self, now: datetime) -> list[dict]:
        data = self._execute(
            self.client.table("tasks")
            .select("*")
            .lte("reminder_time", now.isoformat())
            .eq("reminder_sent", False)
        )
        return data

    def mark_task_reminder_sent(self, task_id: str) -> dict:
        payload = {"reminder_sent": True}
        data = self._execute(self.client.table("tasks").update(payload).eq("id", task_id))
        return data[0]

    # Calories
    def insert_calorie_log(
        self,
        user_id: str,
        meal_description: str,
        calories: int | None,
        protein_g: float | None,
        carbs_g: float | None,
        fat_g: float | None,
        fiber_g: float | None,
        confirmed: bool,
        image_url: str | None = None,
    ) -> dict:
        payload = {
            "user_id": user_id,
            "meal_description": meal_description,
            "image_url": image_url,
            "calories": calories,
            "protein_g": protein_g,
            "carbs_g": carbs_g,
            "fat_g": fat_g,
            "fiber_g": fiber_g,
            "confirmed": confirmed,
        }
        data = self._execute(self.client.table("calorie_logs").insert(payload))
        return data[0]

    def list_today_calories(self, user_id: str, start_iso: str, end_iso: str) -> list[dict]:
        data = self._execute(
            self.client.table("calorie_logs")
            .select("*")
            .eq("user_id", user_id)
            .gte("logged_at", start_iso)
            .lte("logged_at", end_iso)
        )
        return data
