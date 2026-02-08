from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse

from config import settings
from handlers.router import MessageRouter
from services.opik_service import configure_opik
from services.supabase_service import SupabaseService
from services.timer_service import TimerService
from services.twilio_service import TwilioService

logging.basicConfig(level=logging.INFO)

app = FastAPI()
router = MessageRouter()


@app.on_event("startup")
async def startup_event() -> None:
    configure_opik()
    # Start background timer loop
    supabase = SupabaseService()
    twilio = TwilioService()
    timer = TimerService(supabase, twilio)
    timer.start()


@app.get("/")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request) -> PlainTextResponse:
    form = await request.form()
    from_number = form.get("From", "")
    body = form.get("Body", "")
    num_media = int(form.get("NumMedia", "0") or 0)
    media_url = None
    if num_media > 0:
        media_url = form.get("MediaUrl0")

    phone_number = from_number.replace("whatsapp:", "")

    reply_text = await router.route(phone_number, body, media_url)

    twiml = MessagingResponse()
    twiml.message(reply_text)
    return PlainTextResponse(str(twiml), media_type="application/xml")
