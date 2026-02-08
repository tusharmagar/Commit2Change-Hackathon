from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse

from config import settings
from handlers.dashboard import build_day_sections, normalize_phone_number, render_dashboard, render_login
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


@app.get("/dashboard")
async def dashboard_login() -> HTMLResponse:
    return HTMLResponse(render_login())


@app.get("/dashboard/view")
async def dashboard_view(name: str = "", phone: str = "", tz: str = "", days: int = 7) -> HTMLResponse:
    phone_clean = normalize_phone_number(phone)
    if not phone_clean:
        return HTMLResponse(render_login("Please enter a valid phone number."))
    supabase = SupabaseService()
    user = supabase.get_user_by_phone(phone_clean)
    if not user:
        user = supabase.create_user(phone_clean)
    updates = {}
    if name and (user.get("name") != name):
        updates["name"] = name
    if tz and (user.get("timezone") != tz):
        updates["timezone"] = tz
    if updates:
        user = supabase.update_user(user["id"], updates)
    safe_days = max(1, min(days, 14))
    sections = build_day_sections(supabase, user, safe_days)
    return HTMLResponse(render_dashboard(user, sections))


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
