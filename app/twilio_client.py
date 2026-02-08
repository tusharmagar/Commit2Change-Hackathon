from __future__ import annotations

import base64

import httpx
from twilio.rest import Client

from .config import settings


class TwilioClient:
    def __init__(self) -> None:
        self._client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    async def send_whatsapp_message(self, to_number: str, message: str, media_url: str | None = None) -> None:
        params = {
            "from_": f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}",
            "to": f"whatsapp:{to_number}",
            "body": message,
        }
        if media_url:
            params["media_url"] = [media_url]
        # Twilio client is sync; run in thread if needed
        self._client.messages.create(**params)

    async def download_media_as_base64(self, media_url: str) -> tuple[str, bytes]:
        auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        async with httpx.AsyncClient(auth=auth, timeout=30, follow_redirects=True) as client:
            response = await client.get(media_url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "image/jpeg")
            data = response.content
        b64 = base64.b64encode(data).decode("utf-8")
        return content_type, data

    async def download_media_data_url(self, media_url: str) -> str:
        content_type, data = await self.download_media_as_base64(media_url)
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:{content_type};base64,{b64}"
