from __future__ import annotations

import re
from datetime import datetime
from typing import Tuple

from services.openai_service import OpenAIService
from services.opik_service import track
from services.supabase_service import SupabaseService


@track(name="task_extraction")
def add_task(
    supabase: SupabaseService, openai: OpenAIService, user: dict, message: str
) -> str:
    extracted = openai.extract_task(message, user.get("timezone", "UTC"))
    title = extracted.get("title") or message.strip()
    reminder_time = extracted.get("reminder_time")
    supabase.insert_task(user["id"], title, message, reminder_time)
    if reminder_time:
        return f"✅ Task saved. ⏰ Reminder set for {reminder_time.strftime('%-I:%M %p')}."
    return "✅ Task saved."


def list_tasks(supabase: SupabaseService, user: dict) -> Tuple[str, dict]:
    tasks = supabase.list_incomplete_tasks(user["id"])
    if not tasks:
        return "✅ You're all caught up. No open tasks.", {"context": "idle", "data": {}}
    lines = ["Open tasks:"]
    id_map = []
    for idx, task in enumerate(tasks, start=1):
        title = task["title"]
        reminder = task.get("reminder_time")
        if reminder:
            lines.append(f"{idx}. {title} (reminder: {reminder})")
        else:
            lines.append(f"{idx}. {title}")
        id_map.append(task["id"])
    lines.append("Reply with a number to mark one done.")
    return "\n".join(lines), {"context": "awaiting_task_completion", "data": {"task_ids": id_map}}


def complete_task(supabase: SupabaseService, task_id: str) -> str:
    task = supabase.complete_task(task_id)
    return f"✅ '{task['title']}' marked done!"


def parse_task_completion(message: str) -> int | None:
    match = re.search(r"\b(\d+)\b", message)
    if not match:
        return None
    return int(match.group(1))
