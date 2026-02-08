from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict

from .config import data_path


class JsonFileChatMessageHistory(BaseChatMessageHistory):
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.messages: list[BaseMessage] = []
        self._load()

    def _load(self) -> None:
        if not self.file_path.exists():
            self.messages = []
            return
        try:
            payload = json.loads(self.file_path.read_text())
            self.messages = messages_from_dict(payload)
        except Exception:
            self.messages = []

    def _save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(json.dumps(messages_to_dict(self.messages), indent=2))

    def add_message(self, message: BaseMessage) -> None:
        self.messages.append(message)
        self._save()

    def clear(self) -> None:
        self.messages = []
        self._save()


@dataclass
class UserPreferences:
    default_pomodoro: str | None = None
    calorie_units: str | None = None
    dietary_preferences: str | None = None
    task_style: str | None = None
    other: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, user_id: str) -> "UserPreferences":
        path = data_path("prefs", f"{user_id}.json")
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text())
            return cls(**data)
        except Exception:
            return cls()

    def save(self, user_id: str) -> None:
        path = data_path("prefs", f"{user_id}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, indent=2))

    def summary(self) -> str:
        parts = []
        if self.default_pomodoro:
            parts.append(f"default pomodoro: {self.default_pomodoro}")
        if self.calorie_units:
            parts.append(f"calorie units: {self.calorie_units}")
        if self.dietary_preferences:
            parts.append(f"dietary prefs: {self.dietary_preferences}")
        if self.task_style:
            parts.append(f"task style: {self.task_style}")
        if self.other:
            parts.append("other preferences stored")
        return "; ".join(parts) if parts else "none"


def history_for_user(user_id: str) -> JsonFileChatMessageHistory:
    return JsonFileChatMessageHistory(data_path("history", f"{user_id}.json"))
