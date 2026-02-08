from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from handlers.calories import (
    daily_summary,
    handle_calorie_confirmation,
    log_calorie_image,
    log_calorie_text,
    update_goal,
)
from handlers.onboarding import handle_onboarding
from handlers.pomodoro import (
    handle_backfill,
    handle_summary,
    start_pomodoro,
    stop_pomodoro,
    get_stats,
)
from handlers.tasks import add_task, complete_task, list_tasks, parse_task_completion
from services.openai_service import OpenAIService
from services.opik_service import track
from services.supabase_service import SupabaseService
from services.twilio_service import TwilioService
from utils.time_utils import day_range_utc


class MessageRouter:
    def __init__(self) -> None:
        self.supabase = SupabaseService()
        self.openai = OpenAIService()
        self.twilio = TwilioService()

    @track(name="message_router")
    async def route(self, phone_number: str, body: str, media_url: Optional[str] = None) -> str:
        try:
            user = self.supabase.get_or_create_user(phone_number)
        except Exception:
            return (
                "Server is misconfigured and can't reach the database right now. "
                "Please verify SUPABASE_URL and SUPABASE_SECRET_KEY."
            )
        state = self.supabase.get_state(user["id"])
        context = state.get("current_context") if state else None
        context_data = state.get("context_data") if state else {}

        message = body.strip()

        # Onboarding
        if not user.get("onboarding_complete") or message == "/onboarding":
            reply, new_state = handle_onboarding(self.supabase, user, phone_number, message)
            self.supabase.upsert_state(user["id"], phone_number, new_state.get("context"), new_state.get("data", {}))
            return reply

        # Context-specific handling
        if context == "awaiting_pomodoro_summary":
            session_id = (context_data or {}).get("session_id")
            if session_id:
                reply = handle_summary(self.supabase, session_id, message)
            else:
                reply = "Thanks!"
            self.supabase.upsert_state(user["id"], phone_number, "idle", {})
            return reply

        if context == "awaiting_calorie_confirm":
            reply, new_state = handle_calorie_confirmation(self.supabase, user, message, context_data or {})
            self.supabase.upsert_state(user["id"], phone_number, new_state.get("context"), new_state.get("data", {}))
            return reply

        if context == "awaiting_task_completion":
            idx = parse_task_completion(message)
            task_ids = (context_data or {}).get("task_ids", [])
            if idx and 1 <= idx <= len(task_ids):
                reply = complete_task(self.supabase, task_ids[idx - 1])
                self.supabase.upsert_state(user["id"], phone_number, "idle", {})
                return reply
            # fall through to normal routing

        # Media (photo-based calorie logging)
        if media_url:
            data_url = await self.twilio.download_media_data_url(media_url)
            reply, new_state = log_calorie_image(self.supabase, self.openai, user, data_url)
            self.supabase.upsert_state(user["id"], phone_number, new_state.get("context"), new_state.get("data", {}))
            return reply

        # Command matcher
        command_response = self._handle_command(user, phone_number, message)
        if command_response:
            return command_response

        # LLM intent classification
        intent = self.openai.classify_intent(message, context or "idle")
        intent_name = intent.get("intent", "general_chat")

        if intent_name == "pomodoro_start":
            return start_pomodoro(self.supabase, user, message)
        if intent_name == "pomodoro_stop":
            reply, new_state = stop_pomodoro(self.supabase, user)
            self.supabase.upsert_state(user["id"], phone_number, new_state.get("context"), new_state.get("data", {}))
            return reply
        if intent_name == "pomodoro_stats":
            start_iso, end_iso = day_range_utc(user.get("timezone", "UTC"))
            return get_stats(self.supabase, user, start_iso, end_iso)
        if intent_name == "pomodoro_backfill":
            backfill = self.openai.parse_backfill(message, user.get("timezone", "UTC"))
            return handle_backfill(self.supabase, user, backfill)
        if intent_name == "task_add":
            return add_task(self.supabase, self.openai, user, message)
        if intent_name == "task_list":
            reply, new_state = list_tasks(self.supabase, user)
            self.supabase.upsert_state(user["id"], phone_number, new_state.get("context"), new_state.get("data", {}))
            return reply
        if intent_name == "task_complete":
            idx = parse_task_completion(message)
            if idx and state and state.get("context_data"):
                task_ids = state.get("context_data", {}).get("task_ids", [])
                if 1 <= idx <= len(task_ids):
                    return complete_task(self.supabase, task_ids[idx - 1])
            return "Reply with a number from your task list to mark it done."
        if intent_name == "calorie_log":
            reply, new_state = log_calorie_text(self.supabase, self.openai, user, message)
            self.supabase.upsert_state(user["id"], phone_number, new_state.get("context"), new_state.get("data", {}))
            return reply
        if intent_name == "calorie_summary":
            start_iso, end_iso = day_range_utc(user.get("timezone", "UTC"))
            return daily_summary(self.supabase, user, start_iso, end_iso)
        if intent_name == "calorie_goal":
            return update_goal(self.supabase, user, message)
        if intent_name == "help":
            return self._help_text()

        return "I can help with pomodoro, tasks, and calories. Send /help for commands."

    def _handle_command(self, user: dict, phone_number: str, message: str) -> Optional[str]:
        lowered = message.lower()
        if lowered in {"/help", "help"}:
            return self._help_text()
        if lowered.startswith("/onboarding"):
            reply, new_state = handle_onboarding(self.supabase, user, phone_number, "/onboarding")
            self.supabase.upsert_state(user["id"], phone_number, new_state.get("context"), new_state.get("data", {}))
            return reply
        if lowered.startswith("start"):
            return start_pomodoro(self.supabase, user, message)
        if lowered.startswith("stop"):
            reply, new_state = stop_pomodoro(self.supabase, user)
            self.supabase.upsert_state(user["id"], phone_number, new_state.get("context"), new_state.get("data", {}))
            return reply
        if lowered.startswith("stats"):
            start_iso, end_iso = day_range_utc(user.get("timezone", "UTC"))
            return get_stats(self.supabase, user, start_iso, end_iso)
        if lowered.startswith("tasks"):
            reply, new_state = list_tasks(self.supabase, user)
            self.supabase.upsert_state(user["id"], phone_number, new_state.get("context"), new_state.get("data", {}))
            return reply
        if lowered.startswith("done"):
            idx = parse_task_completion(message)
            if not idx:
                return "Reply with a number to mark a task done (e.g. 'done 1')."
            if not user:
                return "No tasks found."
            state = self.supabase.get_state(user["id"])
            task_ids = (state or {}).get("context_data", {}).get("task_ids", [])
            if 1 <= idx <= len(task_ids):
                return complete_task(self.supabase, task_ids[idx - 1])
            return "That number doesn't match your current task list."
        if lowered.startswith("calories"):
            start_iso, end_iso = day_range_utc(user.get("timezone", "UTC"))
            return daily_summary(self.supabase, user, start_iso, end_iso)
        if lowered.startswith("goal"):
            return update_goal(self.supabase, user, message)
        return None

    def _help_text(self) -> str:
        return (
            "Commands:\n"
            "start — start a pomodoro\n"
            "start 45 10 — custom work/break\n"
            "stop — stop current pomodoro\n"
            "stats — today's focus summary\n"
            "tasks — list tasks\n"
            "done 1 — complete a task\n"
            "calories — daily calorie summary\n"
            "goal 2000 — set calorie goal\n"
            "/onboarding — re-run onboarding\n"
            "/help — show this help"
        )
