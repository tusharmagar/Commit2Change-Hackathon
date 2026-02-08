# Tomatose WhatsApp Bot

WhatsApp chatbot that logs pomodoro sessions, tasks, and meals into a Notion workspace using Notion MCP.

## Setup

1. Create a virtualenv and install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Create `.env` from `.env.example` and fill in values.

3. Authenticate Notion MCP (one-time):

```bash
python scripts/notion_oauth.py
```

4. Run the server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5. Configure Twilio WhatsApp webhook:

Set the incoming webhook to:

```
{PUBLIC_BASE_URL}/webhooks/twilio/whatsapp
```

## Notion setup

The bot looks for a Notion page called `Tomatose!` and expects three child databases:

- `Daily Journal`
- `Tasks`
- `Calorie Tracker`

If auto-discovery fails, set `NOTION_*_DB_ID` in `.env`.

Property names can be customized via `.env` if your schema differs.

## Notes

- Pomodoro cycles keep running until you send `stop`.
- Meal logging uses an image → JSON estimate via OpenAI vision.
- User memory and preferences are stored locally under `data/`.
