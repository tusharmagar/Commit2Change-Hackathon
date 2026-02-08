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
        "Tell me the calories you want me to log (e.g. '600 cal'), or reply 'yes' to confirm.",
        {"context": "awaiting_calorie_confirm", "data": pending},
    )


def daily_summary(supabase: SupabaseService, user: dict, start_iso: str, end_iso: str) -> str:
    logs = supabase.list_today_calories(user["id"], start_iso, end_iso)
    if not logs:
        return "No meals logged today yet."
    total_cal = sum([log.get("calories") or 0 for log in logs])
    protein = sum([log.get("protein_g") or 0 for log in logs])
    carbs = sum([log.get("carbs_g") or 0 for log in logs])
    fat = sum([log.get("fat_g") or 0 for log in logs])
    goal = user.get("daily_calorie_goal")
    if goal:
        remaining = goal - total_cal
        return (
            f"Today's intake: 🔥 {total_cal} / {goal} cal | 🥩 {int(protein)}g protein | "
            f"🍞 {int(carbs)}g carbs | 🧈 {int(fat)}g fat — You have {remaining} calories remaining!"
        )
    return (
        f"Today's intake: 🔥 {total_cal} cal | 🥩 {int(protein)}g protein | "
        f"🍞 {int(carbs)}g carbs | 🧈 {int(fat)}g fat"
    )


def update_goal(supabase: SupabaseService, user: dict, message: str) -> str:
    value = _extract_number(message)
    if not value:
        return "Please provide a number, like 'goal 2000'."
    supabase.update_user(user["id"], {"daily_calorie_goal": value})
    return f"Daily calorie goal set to {value}."


def _build_confirmation_message(estimate: dict) -> Tuple[str, dict]:
    text = (
        f"That looks like {estimate.get('description', 'a meal')}! Here's my estimate: "
        f"🔥 {estimate.get('calories')} cal | 🥩 {estimate.get('protein_g')}g protein | "
        f"🍞 {estimate.get('carbs_g')}g carbs | 🧈 {estimate.get('fat_g')}g fat — "
        "Does this look right? Reply 'yes' or tell me what to adjust."
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
    return "Logged your meal.", {"context": "idle", "data": {}}


def _extract_number(message: str) -> int | None:
    match = re.search(r"\d+", message)
    if not match:
        return None
    return int(match.group(0))
