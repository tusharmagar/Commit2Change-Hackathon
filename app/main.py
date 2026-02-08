from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse

from .handlers import IncomingMessage, MessageHandler

app = FastAPI()
handler = MessageHandler()


@app.get("/")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/webhooks/twilio/whatsapp")
async def twilio_whatsapp(request: Request) -> PlainTextResponse:
    form = await request.form()
    from_raw = form.get("From", "")
    body = form.get("Body", "")
    num_media = int(form.get("NumMedia", "0") or 0)
    media_urls = []
    for idx in range(num_media):
        url = form.get(f"MediaUrl{idx}")
        if url:
            media_urls.append(url)

    from_number = from_raw.replace("whatsapp:", "")
    message = IncomingMessage(from_number=from_number, body=body, media_urls=media_urls)
    reply = await handler.handle(message)

    twiml = MessagingResponse()
    twiml.message(reply)
    return PlainTextResponse(str(twiml), media_type="application/xml")
