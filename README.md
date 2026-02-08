# WhatsApp Productivity Bot

Backend-first rebuild aligned with `whatsapp-productivity-bot-plan.md`.

## Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with your credentials, then run:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Supabase

1. Create a Supabase project
2. Run `scripts/setup_supabase.sql` in the SQL editor
3. Copy `SUPABASE_URL` and `SUPABASE_SECRET_KEY` into `.env`

## Twilio Webhook

Set your WhatsApp webhook to:

```
https://YOUR_PUBLIC_URL/webhook
```

Use ngrok during local development:

```bash
ngrok http 8000
```

## Notes

- Frontend is deferred. Backend-only for now.
- See `whatsapp-productivity-bot-plan.md` for the full spec and roadmap.
