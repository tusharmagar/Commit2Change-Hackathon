from __future__ import annotations

import asyncio
from datetime import datetime

from .state import PomodoroState, StateStore
from .twilio_client import TwilioClient


class PomodoroManager:
    def __init__(self, twilio: TwilioClient, state_store: StateStore) -> None:
        self.twilio = twilio
        self.state_store = state_store
        self._tasks: dict[str, asyncio.Task] = {}

    async def start(self, user_id: str, work_minutes: int, break_minutes: int) -> None:
        await self.stop(user_id)
        state = self.state_store.load(user_id)
        state.pomodoro = PomodoroState(work_minutes=work_minutes, break_minutes=break_minutes, is_work=True)
        self.state_store.save(user_id, state)
        task = asyncio.create_task(self._run_loop(user_id))
        self._tasks[user_id] = task

    async def stop(self, user_id: str) -> None:
        task = self._tasks.pop(user_id, None)
        if task:
            task.cancel()
        state = self.state_store.load(user_id)
        state.pomodoro = None
        state.pending = None
        state.pending_payload = None
        self.state_store.save(user_id, state)

    async def _run_loop(self, user_id: str) -> None:
        while True:
            state = self.state_store.load(user_id)
            if not state.pomodoro:
                return
            duration = (
                state.pomodoro.work_minutes
                if state.pomodoro.is_work
                else state.pomodoro.break_minutes
            )
            label = "work" if state.pomodoro.is_work else "break"
            await self.twilio.send_whatsapp_message(user_id, f"Starting {label} for {duration} min.")
            await asyncio.sleep(duration * 60)

            # Transition
            state = self.state_store.load(user_id)
            if not state.pomodoro:
                return
            state.pomodoro.is_work = not state.pomodoro.is_work
            self.state_store.save(user_id, state)

            if not state.pomodoro.is_work:
                # Work finished, ask for a note
                state.pending = "session_note"
                state.pending_payload = {"ended_at": datetime.now().isoformat()}
                self.state_store.save(user_id, state)
                await self.twilio.send_whatsapp_message(
                    user_id,
                    "Break time. What did you work on? (optional)",
                )
            else:
                await self.twilio.send_whatsapp_message(user_id, "Back to work when you're ready.")
