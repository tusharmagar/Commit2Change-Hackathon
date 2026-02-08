from __future__ import annotations

import base64

import httpx
from twilio.rest import Client

from config import settings


class TwilioService:
    def __init__(self) -> None:
        self.client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    def _format_to(self, phone_number: str) -> str:
        if phone_number.startswith("whatsapp:"):
            return phone_number
        return f"whatsapp:{phone_number}"

    def _format_from(self, phone_number: str) -> str:
        if phone_number.startswith("whatsapp:"):
            return phone_number
        return f"whatsapp:{phone_number}"

    def send_message(self, phone_number: str, body: str, media_url: str | None = None) -> None:
        payload = {
            "from_": self._format_from(settings.TWILIO_WHATSAPP_NUMBER),
            "to": self._format_to(phone_number),
            "body": body,
        }
        if media_url:
            payload["media_url"] = [media_url]
        self.client.messages.create(**payload)

    async def download_media_data_url(self, media_url: str) -> str:
        auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        async with httpx.AsyncClient(auth=auth, follow_redirects=True, timeout=30) as client:
            resp = await client.get(media_url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/jpeg")
            data = resp.content
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:{content_type};base64,{b64}"
