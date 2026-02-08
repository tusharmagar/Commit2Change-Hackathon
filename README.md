# Tomatose!

[Demo video](https://youtu.be/UAJfhZ6YaJQ)

Tomatose! is a WhatsApp productivity copilot that turns quick texts (and meal photos) into a clean, day-wise dashboard.

## What You Can Do
- ⏱ Pomodoro that keeps cycling until you say `stop` (with lightweight “what did you do?” journaling)
- ✅ Text-to-task capture + reminders
- 🍎 Meal logging from text or images (estimate → confirm → saved)
- 📊 Day-wise dashboard for focus, tasks, and calories

## Try It
- WhatsApp: say `start 25 5`, `stop`, `tasks`, `done 1`, `calories`, `goal 2000`, `/help`
- Dashboard: open `/dashboard` on the deployed URL and log in with your name + WhatsApp number

## Repo Notes
- Backend: FastAPI + Twilio + Supabase + OpenAI
- Observability: Opik traces grouped by user + day
- Full spec/roadmap: `whatsapp-productivity-bot-plan.md`

## Run Locally (Optional)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

If you’re wiring Twilio locally:
```bash
ngrok http 8000
```
