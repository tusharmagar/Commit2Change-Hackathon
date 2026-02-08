from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4.1-mini"
    OPENAI_VISION_MODEL: str = "gpt-4.1-mini"

    # Twilio
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_NUMBER: str

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # Notion MCP
    NOTION_MCP_URL: str = "https://mcp.notion.com/mcp"
    NOTION_OAUTH_STORAGE: str = "data/notion_oauth.json"
    NOTION_TOMATOSE_PAGE_NAME: str = "Tomatose!"
    NOTION_DAILY_JOURNAL_DB_NAME: str = "Daily Journal"
    NOTION_TASKS_DB_NAME: str = "Tasks"
    NOTION_CALORIE_DB_NAME: str = "Calorie Tracker"

    NOTION_DAILY_JOURNAL_DB_ID: str | None = None
    NOTION_TASKS_DB_ID: str | None = None
    NOTION_CALORIE_DB_ID: str | None = None

    NOTION_TASK_TITLE_PROP: str = "Name"
    NOTION_TASK_DUE_PROP: str = "Due"
    NOTION_TASK_PRIORITY_PROP: str = "Priority"
    NOTION_TASK_STATUS_PROP: str = "Status"
    NOTION_TASK_SOURCE_PROP: str = "Source"
    NOTION_TASK_RAW_PROP: str = "Raw"

    NOTION_JOURNAL_DATE_PROP: str = "Date"
    NOTION_JOURNAL_TEXT_PROP: str = "Notes"

    NOTION_CAL_TITLE_PROP: str = "Meal"
    NOTION_CAL_DATE_PROP: str = "Date"
    NOTION_CAL_CALORIES_PROP: str = "Calories"
    NOTION_CAL_PROTEIN_PROP: str = "Protein"
    NOTION_CAL_CARBS_PROP: str = "Carbs"
    NOTION_CAL_FAT_PROP: str = "Fat"
    NOTION_CAL_NOTES_PROP: str = "Notes"

    DATA_DIR: str = "data"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


def data_path(*parts: str) -> Path:
    base = Path(settings.DATA_DIR)
    base.mkdir(parents=True, exist_ok=True)
    return base.joinpath(*parts)
