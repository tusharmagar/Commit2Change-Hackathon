from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from .config import settings


@dataclass
class MealEstimate:
    meal_name: str
    calories: int | None
    protein: int | None
    carbs: int | None
    fat: int | None
    notes: str | None
    follow_up: str | None = None


def _extract_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found in model output")
    return json.loads(match.group(0))


def analyze_meal_image(image_data_url: str, preferences: str) -> MealEstimate:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    prompt = (
        "You are a nutrition assistant. Estimate calories and macros from the image. "
        "Return JSON with keys: meal_name, calories, protein, carbs, fat, notes, follow_up. "
        "If you need clarification, set follow_up to a short question and leave estimates null. "
        f"User preferences: {preferences}"
    )

    response = client.responses.create(
        model=settings.OPENAI_VISION_MODEL,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": image_data_url},
                ],
            }
        ],
    )

    data = _extract_json(response.output_text)
    return MealEstimate(
        meal_name=data.get("meal_name") or "Meal",
        calories=data.get("calories"),
        protein=data.get("protein"),
        carbs=data.get("carbs"),
        fat=data.get("fat"),
        notes=data.get("notes"),
        follow_up=data.get("follow_up"),
    )
