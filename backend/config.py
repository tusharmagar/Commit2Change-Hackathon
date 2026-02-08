from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_VISION_MODEL: str = "gpt-4o"

    # Twilio
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_NUMBER: str  # e.g. whatsapp:+14155238886

    # Supabase
    SUPABASE_URL: str
    SUPABASE_SECRET_KEY: str

    # Opik (optional but recommended)
    OPIK_API_KEY: str | None = None
    OPIK_PROJECT_NAME: str = "whatsapp-productivity-bot"

    # App
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    APP_ENV: str = "development"

    # Timer loop
    POMODORO_POLL_SECONDS: int = 30
    POMODORO_NUDGE_SECONDS: int = 120

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @field_validator("SUPABASE_URL")
    @classmethod
    def _validate_supabase_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("SUPABASE_URL must start with https://")
        if ".supabase.co" not in value:
            raise ValueError("SUPABASE_URL should look like https://<project-ref>.supabase.co")
        return value


settings = Settings()
