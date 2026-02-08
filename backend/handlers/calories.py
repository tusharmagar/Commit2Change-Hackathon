from __future__ import annotations

import re
from datetime import datetime
from typing import Tuple

from services.openai_service import OpenAIService
from services.opik_service import track
from services.supabase_service import SupabaseService


@track(name="calorie_estimation")
def log_calorie_text(
    supabase: SupabaseService, openai: OpenAIService, user: dict, message: str
) -> Tuple[str, dict]:
    estimate = openai.estimate_calories_text(message, user.get("dietary_preferences", ""))
    return _build_confirmation_message(estimate)


@track(name="calorie_estimation")
def log_calorie_image(
    supabase: SupabaseService,
    openai: OpenAIService,
    user: dict,
    image_data_url: str,
) -> Tuple[str, dict]:
    estimate = openai.estimate_calories_image(image_data_url, user.get("dietary_preferences", ""))
    return _build_confirmation_message(estimate)


def handle_calorie_confirmation(
    supabase: SupabaseService, user: dict, message: str, pending: dict
) -> Tuple[str, dict]:
    lowered = message.strip().lower()
    calories_override = _extract_number(message)
    if lowered in {"yes", "y", "correct", "looks good"}:
        return _save_calorie_log(supabase, user, pending, confirmed=True)
    if calories_override:
        pending["calories"] = calories_override
        return _save_calorie_log(supabase, user, pending, confirmed=True)
    return (
        "Reply 'yes' to log this, or send a new calorie number (e.g. 600) to adjust.",
        {"context": "awaiting_calorie_confirm", "data": pending},
    )


def daily_summary(supabase: SupabaseService, user: dict, start_iso: str, end_iso: str) -> str:
    logs = supabase.list_today_calories(user["id"], start_iso, end_iso)
    if not logs:
        return "No meals logged yet today. Send a photo or a text description to log one."
    total_cal = sum([log.get("calories") or 0 for log in logs])
    protein = sum([log.get("protein_g") or 0 for log in logs])
    carbs = sum([log.get("carbs_g") or 0 for log in logs])
    fat = sum([log.get("fat_g") or 0 for log in logs])
    goal = user.get("daily_calorie_goal")
    if goal:
        remaining = goal - total_cal
        return (
            "Today's intake:\n"
            f"🔥 {total_cal} / {goal} cal\n"
            f"🥩 {int(protein)}g protein | 🍞 {int(carbs)}g carbs | 🧈 {int(fat)}g fat\n"
            f"Remaining: {remaining} cal"
        )
    return (
        "Today's intake:\n"
        f"🔥 {total_cal} cal\n"
        f"🥩 {int(protein)}g protein | 🍞 {int(carbs)}g carbs | 🧈 {int(fat)}g fat"
    )


def update_goal(supabase: SupabaseService, user: dict, message: str) -> str:
    value = _extract_number(message)
    if not value:
        return "Please send a number, like 'goal 2000'."
    supabase.update_user(user["id"], {"daily_calorie_goal": value})
    return f"✅ Daily calorie goal set to {value}."


def _build_confirmation_message(estimate: dict) -> Tuple[str, dict]:
    description = estimate.get("description") or "a meal"
    details = _format_macro_details(estimate)
    details_text = " | ".join(details) if details else "No macros estimate yet."
    text = (
        f"That looks like {description}.\n"
        f"Estimate: {details_text}\n"
        "Reply 'yes' to log, or send a new calorie number to adjust."
    )
    return text, {"context": "awaiting_calorie_confirm", "data": estimate}


def _save_calorie_log(
    supabase: SupabaseService, user: dict, estimate: dict, confirmed: bool
) -> Tuple[str, dict]:
    supabase.insert_calorie_log(
        user_id=user["id"],
        meal_description=estimate.get("description") or "Meal",
        calories=estimate.get("calories"),
        protein_g=estimate.get("protein_g"),
        carbs_g=estimate.get("carbs_g"),
        fat_g=estimate.get("fat_g"),
        fiber_g=estimate.get("fiber_g"),
        confirmed=confirmed,
    )
    description = estimate.get("description") or "Meal"
    details = _format_macro_details(estimate)
    if details:
        return f"✅ Logged: {description}\n" + " | ".join(details), {"context": "idle", "data": {}}
    return f"✅ Logged: {description}.", {"context": "idle", "data": {}}


def _extract_number(message: str) -> int | None:
    match = re.search(r"\d+", message)
    if not match:
        return None
    return int(match.group(0))


def _format_macro_details(estimate: dict) -> list[str]:
    parts: list[str] = []
    calories = estimate.get("calories")
    if calories is not None:
        parts.append(f"🔥 {int(calories)} cal")
    protein = estimate.get("protein_g")
    if protein is not None:
        parts.append(f"🥩 {int(protein)}g protein")
    carbs = estimate.get("carbs_g")
    if carbs is not None:
        parts.append(f"🍞 {int(carbs)}g carbs")
    fat = estimate.get("fat_g")
    if fat is not None:
        parts.append(f"🧈 {int(fat)}g fat")
    fiber = estimate.get("fiber_g")
    if fiber is not None:
        parts.append(f"🌾 {int(fiber)}g fiber")
    return parts
