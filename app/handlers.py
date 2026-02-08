from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

import dateparser
from tzlocal import get_localzone

from .chains import (
    build_intent_chain,
    build_llm,
    build_pomodoro_chain,
    build_preference_chain,
    build_task_chain,
    today_str,
)
from .config import settings
from .memory import UserPreferences, history_for_user
from .notion import NotionWorkspace
from .openai_client import analyze_meal_image
from .pomodoro import PomodoroManager
from .state import StateStore
from .twilio_client import TwilioClient


@dataclass
class IncomingMessage:
    from_number: str
    body: str
    media_urls: list[str]


class MessageHandler:
    def __init__(self) -> None:
        self.twilio = TwilioClient()
        self.state_store = StateStore()
        self.pomodoro = PomodoroManager(self.twilio, self.state_store)
        self.notion = NotionWorkspace()

        llm = build_llm(settings.OPENAI_MODEL, settings.OPENAI_API_KEY)
        self.intent_chain = build_intent_chain(llm)
        self.task_chain = build_task_chain(llm)
        self.pomodoro_chain = build_pomodoro_chain(llm)
        self.pref_chain = build_preference_chain(llm)

    async def handle(self, message: IncomingMessage) -> str:
        user_id = message.from_number
        state = self.state_store.load(user_id)
        prefs = UserPreferences.load(user_id)

        if state.pending == "session_note":
            note = message.body.strip()
            if note:
                await self.notion.append_journal_entry(note, datetime.now())
                response = "Logged your session note."
            else:
                response = "No note saved."
            state.pending = None
            state.pending_payload = None
            self.state_store.save(user_id, state)
            self._remember(user_id, message.body, response)
            return response

        if state.pending == "meal_followup":
            follow = message.body.strip()
            payload = state.pending_payload or {}
            notes = payload.get("notes")
            combined = f"{notes}\nFollow-up: {follow}" if notes else f"Follow-up: {follow}"
            await self.notion.create_calorie_entry(
                meal=payload.get("meal_name", "Meal"),
                calories=payload.get("calories"),
                protein=payload.get("protein"),
                carbs=payload.get("carbs"),
                fat=payload.get("fat"),
                notes=combined,
                entry_date=datetime.now(),
            )
            state.pending = None
            state.pending_payload = None
            self.state_store.save(user_id, state)
            response = "Logged the meal with your details."
            self._remember(user_id, message.body, response)
            return response

        if message.media_urls:
            image_url = message.media_urls[0]
            data_url = await self.twilio.download_media_data_url(image_url)
            estimate = analyze_meal_image(data_url, prefs.summary())
            if estimate.follow_up:
                state.pending = "meal_followup"
                state.pending_payload = {
                    "meal_name": estimate.meal_name,
                    "calories": estimate.calories,
                    "protein": estimate.protein,
                    "carbs": estimate.carbs,
                    "fat": estimate.fat,
                    "notes": estimate.notes,
                }
                self.state_store.save(user_id, state)
                response = estimate.follow_up
            else:
                await self.notion.create_calorie_entry(
                    meal=estimate.meal_name,
                    calories=estimate.calories,
                    protein=estimate.protein,
                    carbs=estimate.carbs,
                    fat=estimate.fat,
                    notes=estimate.notes,
                    entry_date=datetime.now(),
                )
                response = "Logged your meal in Notion."
            self._remember(user_id, message.body, response)
            return response

        intent = await self.intent_chain.ainvoke(
            {
                "message": message.body,
                "preferences": prefs.summary(),
                "now": datetime.now().isoformat(),
            }
        )

        if intent.intent == "pomodoro_start":
            config = await self.pomodoro_chain.ainvoke({"message": message.body})
            await self.pomodoro.start(user_id, config.work_minutes, config.break_minutes)
            prefs.default_pomodoro = f"{config.work_minutes}/{config.break_minutes}"
            prefs.save(user_id)
            response = f"Started {config.work_minutes}/{config.break_minutes} pomodoro. Say 'stop' to end."
        elif intent.intent == "pomodoro_stop":
            await self.pomodoro.stop(user_id)
            response = "Stopped the pomodoro."
        elif intent.intent == "task":
            task = await self.task_chain.ainvoke({"message": message.body, "today": today_str()})
            due_date = normalize_due_date(task.due_date)
            await self.notion.create_task(task.title, due_date, task.priority, message.body)
            response = "Task saved to Notion."
        elif intent.intent == "journal_note":
            await self.notion.append_journal_entry(message.body, datetime.now())
            response = "Added to your Daily Journal."
        elif intent.intent == "preference":
            update = await self.pref_chain.ainvoke({"message": message.body})
            apply_pref_update(prefs, update)
            prefs.save(user_id)
            response = "Got it. I’ll remember that preference."
        else:
            response = (
                "I can log tasks, start a pomodoro, or track meals. "
                "Try: '45 min work / 15 min break', 'Call the bank tomorrow', or send a food photo."
            )

        self._remember(user_id, message.body, response)
        return response

    def _remember(self, user_id: str, user_text: str, assistant_text: str) -> None:
        history = history_for_user(user_id)
        history.add_user_message(user_text)
        history.add_ai_message(assistant_text)


def normalize_due_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    if "T" in date_str:
        return date_str
    local_tz = get_localzone()
    parsed = dateparser.parse(
        date_str,
        settings={"RELATIVE_BASE": datetime.now(tz=local_tz), "RETURN_AS_TIMEZONE_AWARE": True},
    )
    if not parsed:
        return date_str
    return parsed.isoformat()


def apply_pref_update(prefs: UserPreferences, update: object) -> None:
    for field in ["default_pomodoro", "calorie_units", "dietary_preferences", "task_style"]:
        value = getattr(update, field, None)
        if value:
            setattr(prefs, field, value)
