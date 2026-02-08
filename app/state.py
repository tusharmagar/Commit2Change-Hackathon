from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import data_path


@dataclass
class PomodoroState:
    work_minutes: int
    break_minutes: int
    is_work: bool = True


@dataclass
class UserState:
    pending: str | None = None
    pending_payload: dict[str, Any] | None = None
    pomodoro: PomodoroState | None = None


class StateStore:
    def __init__(self) -> None:
        self.base = data_path("state")
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: str) -> Path:
        return self.base / f"{user_id}.json"

    def load(self, user_id: str) -> UserState:
        path = self._path(user_id)
        if not path.exists():
            return UserState()
        try:
            data = json.loads(path.read_text())
        except Exception:
            return UserState()

        pomodoro = None
        if data.get("pomodoro"):
            pomodoro = PomodoroState(**data["pomodoro"])
        return UserState(
            pending=data.get("pending"),
            pending_payload=data.get("pending_payload"),
            pomodoro=pomodoro,
        )

    def save(self, user_id: str, state: UserState) -> None:
        path = self._path(user_id)
        payload: dict[str, Any] = {
            "pending": state.pending,
            "pending_payload": state.pending_payload,
            "pomodoro": None,
        }
        if state.pomodoro:
            payload["pomodoro"] = {
                "work_minutes": state.pomodoro.work_minutes,
                "break_minutes": state.pomodoro.break_minutes,
                "is_work": state.pomodoro.is_work,
            }
        path.write_text(json.dumps(payload, indent=2))
