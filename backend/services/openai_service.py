from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import dateparser
from openai import OpenAI

from config import settings

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


class OpenAIService:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def _load_prompt(self, filename: str) -> str:
        return (PROMPT_DIR / filename).read_text()

    def _chat_json(self, system_prompt: str, user_content: Any) -> dict:
        response = self.client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def classify_intent(self, message: str, context: str) -> dict:
        prompt = self._load_prompt("intent_classifier.txt")
        user_payload = f"Context: {context}\nMessage: {message}"
        return self._chat_json(prompt, user_payload)

    def extract_task(self, message: str, timezone: str) -> dict:
        prompt = self._load_prompt("task_extractor.txt")
        data = self._chat_json(prompt, f"Timezone: {timezone}\nMessage: {message}")
        reminder = data.get("reminder_time")
        data["reminder_time"] = self._parse_datetime(reminder, timezone, prefer="future")
        return data

    def parse_backfill(self, message: str, timezone: str) -> dict:
        prompt = self._load_prompt("backfill_parser.txt")
        data = self._chat_json(prompt, f"Timezone: {timezone}\nMessage: {message}")
        data["start_time"] = self._parse_datetime(data.get("start_time"), timezone, prefer="past")
        data["end_time"] = self._parse_datetime(data.get("end_time"), timezone, prefer="past")
        return data

    def estimate_calories_text(self, description: str, preferences: str = "") -> dict:
        prompt = self._load_prompt("calorie_estimator.txt")
        user_payload = f"Description: {description}\nPreferences: {preferences}"
        return self._chat_json(prompt, user_payload)

    def estimate_calories_image(self, image_data_url: str, preferences: str = "") -> dict:
        prompt = self._load_prompt("calorie_estimator.txt")
        response = self.client.chat.completions.create(
            model=settings.OPENAI_VISION_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Preferences: {preferences}"},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                },
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def refine_calorie_estimate(self, existing_estimate: dict, correction: str, preferences: str = "") -> dict:
        prompt = self._load_prompt("calorie_refiner.txt")
        user_payload = {
            "existing_estimate": existing_estimate,
            "correction": correction,
            "preferences": preferences,
        }
        return self._chat_json(prompt, json.dumps(user_payload))

    def _parse_datetime(self, value: str | None, timezone: str, prefer: str) -> datetime | None:
        if not value:
            return None
        settings_parser = {
            "TIMEZONE": timezone,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": prefer,
        }
        parsed = dateparser.parse(value, settings=settings_parser)
        if not parsed:
            return None
        return parsed
