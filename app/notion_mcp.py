from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .config import settings


@dataclass
class OAuthState:
    client_id: str
    token_endpoint: str
    access_token: str
    refresh_token: str | None
    expires_at: float

    @classmethod
    def load(cls, path: Path) -> "OAuthState":
        data = json.loads(path.read_text())
        return cls(
            client_id=data["client_id"],
            token_endpoint=data["token_endpoint"],
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=data["expires_at"],
        )

    def save(self, path: Path) -> None:
        payload = {
            "client_id": self.client_id,
            "token_endpoint": self.token_endpoint,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))


class OAuthTokenManager:
    def __init__(self, storage_path: str):
        self.path = Path(storage_path)

    def load(self) -> OAuthState:
        if not self.path.exists():
            raise RuntimeError(
                "Notion OAuth state not found. Run scripts/notion_oauth.py to authenticate."
            )
        return OAuthState.load(self.path)

    async def refresh_if_needed(self, state: OAuthState) -> OAuthState:
        now = time.time()
        if state.expires_at - now > 300:
            return state
        if not state.refresh_token:
            raise RuntimeError("Access token expired and no refresh token is available.")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                state.token_endpoint,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": state.refresh_token,
                    "client_id": state.client_id,
                },
            )
            resp.raise_for_status()
            payload = resp.json()
        state.access_token = payload["access_token"]
        state.refresh_token = payload.get("refresh_token", state.refresh_token)
        state.expires_at = now + payload.get("expires_in", 3600)
        state.save(self.path)
        return state


class NotionMCPClient:
    def __init__(self) -> None:
        self.token_manager = OAuthTokenManager(settings.NOTION_OAUTH_STORAGE)

    async def _get_headers(self) -> dict[str, str]:
        state = self.token_manager.load()
        state = await self.token_manager.refresh_if_needed(state)
        return {"Authorization": f"Bearer {state.access_token}"}

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        headers = await self._get_headers()
        async with httpx.AsyncClient(headers=headers, timeout=60) as http_client:
            async with streamable_http_client(settings.NOTION_MCP_URL, http_client=http_client) as (
                read,
                write,
                _,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool(name, arguments)

    async def list_tools(self) -> Any:
        headers = await self._get_headers()
        async with httpx.AsyncClient(headers=headers, timeout=60) as http_client:
            async with streamable_http_client(settings.NOTION_MCP_URL, http_client=http_client) as (
                read,
                write,
                _,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.list_tools()
