from __future__ import annotations

import re
from typing import Tuple

from services.opik_service import track
from services.supabase_service import SupabaseService


@track(name="onboarding_step")
def handle_onboarding(
    supabase: SupabaseService,
    user: dict,
    phone_number: str,
    message: str,
) -> Tuple[str, dict]:
    step = user.get("onboarding_step") or "welcome"

    if message.strip().lower() == "/onboarding":
        step = "welcome"
        user = supabase.update_user(user["id"], {"onboarding_step": "welcome", "onboarding_complete": False})

    if step == "welcome":
        supabase.update_user(user["id"], {"onboarding_step": "name", "onboarding_complete": False})
        text = (
            "Hey! I'm Dash — your WhatsApp productivity copilot.\n\n"
            "I can help you:\n"
            "• ⏱ Run focus sessions (Pomodoro)\n"
            "• ✅ Capture tasks fast\n"
            "• 🍎 Log meals & calories\n\n"
            "Let's get you set up. What's your name?"
        )
        return text, {"context": "onboarding"}

    if step == "name":
        name = _extract_name(message)
        supabase.update_user(user["id"], {"name": name, "onboarding_step": "features"})
        text = (
            f"Nice to meet you, {name}!\n\n"
            "Which features do you want to use?\n"
            "1️⃣ Focus (Pomodoro)\n"
            "2️⃣ Tasks\n"
            "3️⃣ Calories\n\n"
            "Reply with numbers (e.g. 1 2 3 for all)."
        )
        return text, {"context": "onboarding"}

    if step == "features":
        features = _parse_features(message)
        if not features:
            return "Please reply with numbers like 1 2 3 (example: 1 3).", {"context": "onboarding"}
        supabase.update_user(user["id"], {"features_enabled": features, "onboarding_step": "pomodoro_prefs"})
        if "pomodoro" in features:
            text = (
                "What's your default focus cycle?\n"
                "Example: 45 10 (work/break)\n"
                "Or reply 'ok' to use 25/5."
            )
            return text, {"context": "onboarding"}
        if "calories" in features:
            supabase.update_user(user["id"], {"onboarding_step": "calorie_goal"})
            return (
                "What's your daily calorie goal?\n"
                "Example: 2000\n"
                "Or reply 'skip' to set it later."
            ), {"context": "onboarding"}
        return _finish_onboarding(supabase, user)

    if step == "pomodoro_prefs":
        work, rest = _parse_pomodoro_prefs(message)
        updates = {"default_work_minutes": work, "default_break_minutes": rest}
        user = supabase.update_user(user["id"], updates)
        features = user.get("features_enabled") or []
        if "calories" in features:
            supabase.update_user(user["id"], {"onboarding_step": "calorie_goal"})
            return (
                "What's your daily calorie goal?\n"
                "Example: 2000\n"
                "Or reply 'skip' to set it later."
            ), {"context": "onboarding"}
        return _finish_onboarding(supabase, user)

    if step == "calorie_goal":
        goal = _parse_goal(message)
        if goal is not None:
            supabase.update_user(user["id"], {"daily_calorie_goal": goal})
        return _finish_onboarding(supabase, user)

    return _finish_onboarding(supabase, user)


def _finish_onboarding(supabase: SupabaseService, user: dict) -> Tuple[str, dict]:
    supabase.update_user(user["id"], {"onboarding_complete": True, "onboarding_step": "done"})
    text = (
        "You're all set!\n\n"
        "Quick starts:\n"
        "• start (or start 45 10)\n"
        "• tasks\n"
        "• calories\n\n"
        "Send /help anytime."
    )
    return text, {"context": "idle"}


def _extract_name(message: str) -> str:
    lowered = message.strip()
    match = re.search(r"name is ([A-Za-z][A-Za-z\s'-]+)", lowered, re.IGNORECASE)
    if match:
        return match.group(1).strip().title()
    return message.strip().title()


def _parse_features(message: str) -> list[str]:
    tokens = re.findall(r"[123]", message)
    mapping = {"1": "pomodoro", "2": "tasks", "3": "calories"}
    features = [mapping[token] for token in tokens]
    return list(dict.fromkeys(features))


def _parse_pomodoro_prefs(message: str) -> tuple[int, int]:
    if message.strip().lower() in {"ok", "okay", "default"}:
        return 25, 5
    numbers = [int(n) for n in re.findall(r"\d+", message)]
    if not numbers:
        return 25, 5
    if len(numbers) == 1:
        return numbers[0], 5
    return numbers[0], numbers[1]


def _parse_goal(message: str) -> int | None:
    if message.strip().lower() in {"skip", "later", "no"}:
        return None
    match = re.search(r"\d+", message)
    if not match:
        return None
    return int(match.group(0))
