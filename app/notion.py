from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .config import settings
from .notion_mcp import NotionMCPClient


def _coerce_json(result: Any) -> Any:
    if hasattr(result, "content"):
        content = result.content
    elif isinstance(result, dict) and "content" in result:
        content = result["content"]
    else:
        return result

    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                if "json" in item:
                    return item["json"]
                if "text" in item:
                    try:
                        return json.loads(item["text"])
                    except Exception:
                        continue
        return content
    return content


def _first_title(props: dict[str, Any]) -> str | None:
    if not props:
        return None
    title_prop = next(iter(props.values()), None)
    if not title_prop:
        return None
    if isinstance(title_prop, dict) and "title" in title_prop:
        text = title_prop["title"]
        if text and isinstance(text, list):
            return text[0].get("plain_text") or text[0].get("text", {}).get("content")
    return None


@dataclass
class NotionDatabases:
    daily_journal: str
    tasks: str
    calories: str


class NotionWorkspace:
    def __init__(self) -> None:
        self.client = NotionMCPClient()
        self._db_cache: NotionDatabases | None = None

    async def ensure_databases(self) -> NotionDatabases:
        if self._db_cache:
            return self._db_cache

        if settings.NOTION_DAILY_JOURNAL_DB_ID and settings.NOTION_TASKS_DB_ID and settings.NOTION_CALORIE_DB_ID:
            self._db_cache = NotionDatabases(
                daily_journal=settings.NOTION_DAILY_JOURNAL_DB_ID,
                tasks=settings.NOTION_TASKS_DB_ID,
                calories=settings.NOTION_CALORIE_DB_ID,
            )
            return self._db_cache

        search_result = await self.client.call_tool(
            "notion-search",
            {"query": settings.NOTION_TOMATOSE_PAGE_NAME},
        )
        search_json = _coerce_json(search_result)
        page_url = None
        for item in search_json.get("results", []):
            title = item.get("title") or item.get("name")
            if title == settings.NOTION_TOMATOSE_PAGE_NAME:
                page_url = item.get("url")
                break
        if not page_url:
            raise RuntimeError(
                "Could not find Tomatose! page. Set NOTION_*_DB_ID env vars manually."
            )

        fetch_result = await self.client.call_tool(
            "notion-fetch",
            {"url": page_url},
        )
        fetch_json = _coerce_json(fetch_result)

        db_map: dict[str, str] = {}
        for block in fetch_json.get("blocks", []):
            if block.get("type") == "child_database":
                name = block.get("child_database", {}).get("title")
                db_id = block.get("id")
                if name and db_id:
                    db_map[name] = db_id

        missing = [
            name
            for name in [
                settings.NOTION_DAILY_JOURNAL_DB_NAME,
                settings.NOTION_TASKS_DB_NAME,
                settings.NOTION_CALORIE_DB_NAME,
            ]
            if name not in db_map
        ]
        if missing:
            raise RuntimeError(
                f"Missing databases under Tomatose!: {', '.join(missing)}. Set NOTION_*_DB_ID env vars."
            )

        self._db_cache = NotionDatabases(
            daily_journal=db_map[settings.NOTION_DAILY_JOURNAL_DB_NAME],
            tasks=db_map[settings.NOTION_TASKS_DB_NAME],
            calories=db_map[settings.NOTION_CALORIE_DB_NAME],
        )
        return self._db_cache

    async def create_task(
        self,
        title: str,
        due_date: str | None,
        priority: str | None,
        raw_text: str,
    ) -> Any:
        dbs = await self.ensure_databases()
        props: dict[str, Any] = {
            settings.NOTION_TASK_TITLE_PROP: {"title": [{"text": {"content": title}}]},
            settings.NOTION_TASK_SOURCE_PROP: {"select": {"name": "WhatsApp"}},
            settings.NOTION_TASK_RAW_PROP: {"rich_text": [{"text": {"content": raw_text}}]},
        }
        if due_date:
            props[settings.NOTION_TASK_DUE_PROP] = {"date": {"start": due_date}}
        if priority:
            props[settings.NOTION_TASK_PRIORITY_PROP] = {"select": {"name": priority.capitalize()}}

        payload = {
            "pages": [
                {
                    "parent": {"database_id": dbs.tasks},
                    "properties": props,
                }
            ]
        }
        return await self.client.call_tool("notion-create-pages", payload)

    async def append_journal_entry(self, text: str, entry_date: datetime) -> Any:
        dbs = await self.ensure_databases()
        props: dict[str, Any] = {
            settings.NOTION_JOURNAL_DATE_PROP: {"date": {"start": entry_date.date().isoformat()}},
            settings.NOTION_JOURNAL_TEXT_PROP: {"rich_text": [{"text": {"content": text}}]},
        }
        payload = {
            "pages": [
                {
                    "parent": {"database_id": dbs.daily_journal},
                    "properties": props,
                }
            ]
        }
        return await self.client.call_tool("notion-create-pages", payload)

    async def create_calorie_entry(
        self,
        meal: str,
        calories: int | None,
        protein: int | None,
        carbs: int | None,
        fat: int | None,
        notes: str | None,
        entry_date: datetime,
    ) -> Any:
        dbs = await self.ensure_databases()
        props: dict[str, Any] = {
            settings.NOTION_CAL_TITLE_PROP: {"title": [{"text": {"content": meal}}]},
            settings.NOTION_CAL_DATE_PROP: {"date": {"start": entry_date.date().isoformat()}},
        }
        if calories is not None:
            props[settings.NOTION_CAL_CALORIES_PROP] = {"number": calories}
        if protein is not None:
            props[settings.NOTION_CAL_PROTEIN_PROP] = {"number": protein}
        if carbs is not None:
            props[settings.NOTION_CAL_CARBS_PROP] = {"number": carbs}
        if fat is not None:
            props[settings.NOTION_CAL_FAT_PROP] = {"number": fat}
        if notes:
            props[settings.NOTION_CAL_NOTES_PROP] = {"rich_text": [{"text": {"content": notes}}]}

        payload = {
            "pages": [
                {
                    "parent": {"database_id": dbs.calories},
                    "properties": props,
                }
            ]
        }
        return await self.client.call_tool("notion-create-pages", payload)
