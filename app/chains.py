from __future__ import annotations

from datetime import datetime
from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class MessageIntent(BaseModel):
    intent: Literal[
        "task",
        "pomodoro_start",
        "pomodoro_stop",
        "journal_note",
        "preference",
        "other",
    ]
    confidence: float = Field(ge=0.0, le=1.0, default=0.6)
    reason: str | None = None


class TaskExtraction(BaseModel):
    title: str
    due_date: str | None = Field(
        default=None,
        description="ISO date or datetime if explicitly provided, otherwise null",
    )
    priority: Literal["low", "medium", "high"] | None = None


class PomodoroConfig(BaseModel):
    work_minutes: int = Field(ge=5, le=240)
    break_minutes: int = Field(ge=3, le=120)


class PreferenceUpdate(BaseModel):
    default_pomodoro: str | None = None
    calorie_units: str | None = None
    dietary_preferences: str | None = None
    task_style: str | None = None


def build_llm(model: str, api_key: str) -> ChatOpenAI:
    return ChatOpenAI(model=model, temperature=0, api_key=api_key)


def build_intent_chain(llm: ChatOpenAI):
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are a strict router for a WhatsApp productivity assistant.
Classify the user's message into one intent.

Intents:
- task: user wants to capture a task
- pomodoro_start: user wants to start a focus timer or cycle
- pomodoro_stop: user wants to stop an active timer
- journal_note: user wants to log a quick note about what they did
- preference: user is stating a preference to remember
- other: anything else

Rules:
- If the message contains 'stop' or 'cancel' and refers to a timer, choose pomodoro_stop.
- If the message includes durations like '25 min/5 min' or 'pomodoro', choose pomodoro_start.
- If the message is a simple imperative like 'call the bank', choose task.
- If the message says 'remember' or 'my preference' choose preference.

Return only structured output.
""",
            ),
            ("human", "Message: {message}\nPreferences: {preferences}\nNow: {now}"),
        ]
    )
    return prompt | llm.with_structured_output(MessageIntent)


def build_task_chain(llm: ChatOpenAI):
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
Extract a single task from the user's message.
- If due date is implied, convert it to ISO 8601 in the user's local time.
- If no due date, return null.
- If priority is implied ('urgent', 'high priority'), map to high/medium/low.
Return only structured output.
""",
            ),
            ("human", "Message: {message}\nToday: {today}"),
        ]
    )
    return prompt | llm.with_structured_output(TaskExtraction)


def build_pomodoro_chain(llm: ChatOpenAI):
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
Extract a pomodoro configuration from the user's message.
If the user gives only one duration, use 5 minutes for break.
Return only structured output.
""",
            ),
            ("human", "Message: {message}"),
        ]
    )
    return prompt | llm.with_structured_output(PomodoroConfig)


def build_preference_chain(llm: ChatOpenAI):
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
Extract any preference updates from the message.
If no updates, return null for fields.
Return only structured output.
""",
            ),
            ("human", "Message: {message}"),
        ]
    )
    return prompt | llm.with_structured_output(PreferenceUpdate)


def today_str() -> str:
    return datetime.now().date().isoformat()
