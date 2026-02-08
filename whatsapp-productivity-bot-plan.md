# WhatsApp Productivity Bot — Build Plan

**Hackathon:** Commit to Change: An AI Agents Hackathon (Encode Club × Comet)
**Prize targets:** Productivity & Work Habits ($5k) · Health, Fitness & Wellness ($5k) · Best Use of Opik ($5k)
**Judging criteria:** Functionality · Real-world relevance · Use of LLMs/Agents · Evaluation & observability · Goal alignment

---

## 1. Architecture Overview

```
                                    ┌─────────────────────────────────────────┐
                                    │          RAILWAY (always-on)            │
┌─────────────┐   Webhook (POST)    │  ┌──────────────────────────────────┐  │
│   WhatsApp   │ ──────────────────▶│  │        FastAPI Server            │  │
│   (Twilio)   │ ◀─────────────────│  │                                  │  │
└─────────────┘   TwiML Response    │  │  ┌────────────┐                 │  │
                                    │  │  │  Router /   │                 │  │
                                    │  │  │  Intent     │                 │  │
                                    │  │  │  Classifier │                 │  │
                                    │  │  └─────┬──────┘                 │  │
                                    │  │        │                        │  │
                                    │  │  ┌─────┼──────────────┐        │  │
                                    │  │  │     │              │        │  │
                                    │  │  ▼     ▼              ▼        │  │
                                    │  │ Pomo  Tasks        Calories    │  │
                                    │  │                                │  │
                                    │  │  ┌────────────────────────┐   │  │
                                    │  │  │   Timer Loop (30s poll)│   │  │
                                    │  │  │   Checks for expired   │   │  │
                                    │  │  │   timers & reminders   │   │  │
                                    │  │  └────────────────────────┘   │  │
                                    │  └──────────────┬───────────────┘  │
                                    └─────────────────┼──────────────────┘
                                                      │
                           ┌──────────────────────────┼──────────────────┐
                           │                          │                  │
                    ┌──────▼──────┐           ┌───────▼───────┐  ┌──────▼──────┐
                    │  OpenAI     │           │   Supabase    │  │    Opik     │
                    │  GPT-4o    │           │  (PostgreSQL) │  │  (Comet)    │
                    │  NLP +     │           │  Source of    │  │  Traces +   │
                    │  Vision    │           │  truth        │  │  Evals      │
                    └─────────────┘           └───────┬───────┘  └─────────────┘
                                                      │
                                                      │ reads directly
                                                      ▼
                                    ┌─────────────────────────────────────┐
                                    │        VERCEL (later)              │
                                    │  ┌──────────────────────────────┐  │
                                    │  │    Next.js Dashboard (later) │  │
                                    │  │    - Today's Pomodoro log     │  │
                                    │  │    - Task list                │  │
                                    │  │    - Calorie summary          │  │
                                    │  │    yourbot.vercel.app         │  │
                                    │  └──────────────────────────────┘  │
                                    └─────────────────────────────────────┘
```

---

## 2. Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Messaging | Twilio WhatsApp Sandbox → Production | Simple webhook model, good Python SDK, sandbox for testing |
| Backend | Python + FastAPI | Lightweight, fast to build, async-friendly, full Opik Python SDK support |
| Backend Hosting | **Railway** (free $5/mo credit) | Always-on server — timers and background polling stay alive. Simple GitHub deploy. No cold starts. |
| Frontend | **Next.js dashboard on Vercel** (later) | Clean UI pulling straight from Supabase. Deferred until backend is complete. |
| LLM | OpenAI GPT-4o | Strong vision for food photos, structured output, reliable |
| Database | Supabase (PostgreSQL) | Free tier, no rate limits, relational. Shared data layer between backend + frontend. |
| Observability | Opik (Comet) | @track decorators on all LLM calls, traces, evals — needed for prize |
| Timer/Reminders | DB polling loop (30s interval) | Store `timer_end_time` in Supabase, poll for expired timers. State lives in the DB so it survives server restarts. |
| Tunneling (dev) | ngrok | Expose local FastAPI server for Twilio webhook during development |

---

## 3. Database Schema (Supabase)

### `users` table
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number TEXT UNIQUE NOT NULL,        -- WhatsApp number (E.164 format)
    name TEXT,
    timezone TEXT DEFAULT 'UTC',
    -- Onboarding state
    onboarding_complete BOOLEAN DEFAULT FALSE,
    onboarding_step TEXT DEFAULT 'welcome',   -- welcome, name, goals, pomodoro_prefs, calorie_prefs, done
    -- Feature preferences
    features_enabled TEXT[] DEFAULT '{}',      -- ['pomodoro', 'tasks', 'calories']
    -- Pomodoro defaults
    default_work_minutes INTEGER DEFAULT 25,
    default_break_minutes INTEGER DEFAULT 5,
    -- Calorie preferences
    daily_calorie_goal INTEGER,
    dietary_preferences TEXT,
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `pomodoro_sessions` table
```sql
CREATE TABLE pomodoro_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    session_type TEXT NOT NULL,               -- 'work' or 'break'
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    planned_duration_minutes INTEGER,
    what_did_you_do TEXT,                     -- filled by user after work period
    status TEXT DEFAULT 'active',             -- 'active', 'completed', 'cancelled'
    -- For backfilling past sessions
    is_backfill BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `tasks` table
```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    title TEXT NOT NULL,
    description TEXT,
    raw_message TEXT,                          -- original WhatsApp message that created this
    reminder_time TIMESTAMPTZ,                -- optional — if user said "remind me at 9pm"
    reminder_sent BOOLEAN DEFAULT FALSE,
    completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `calorie_logs` table
```sql
CREATE TABLE calorie_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    meal_description TEXT,
    image_url TEXT,                            -- Twilio media URL or stored URL
    calories INTEGER,
    protein_g FLOAT,
    carbs_g FLOAT,
    fat_g FLOAT,
    fiber_g FLOAT,
    confirmed BOOLEAN DEFAULT FALSE,          -- user confirmed the estimate
    logged_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### `conversation_state` table
```sql
CREATE TABLE conversation_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    phone_number TEXT NOT NULL,
    current_context TEXT,                      -- 'idle', 'onboarding', 'pomodoro_active', 'awaiting_pomodoro_summary', 'awaiting_calorie_confirm', etc.
    context_data JSONB DEFAULT '{}',           -- flexible state storage (e.g. pending calorie estimate to confirm)
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 4. Frontend Dashboard (Later)

**Status:** Deferred / out of scope for the current backend-first build. We will revisit after the core WhatsApp bot is stable.

A simple, clean Next.js app hosted on Vercel's free tier. Reads directly from Supabase in real-time — no sync jobs needed. Judges (and users) visit `yourbot.vercel.app` to see their data once the frontend is reintroduced.

### Tech: Next.js + Supabase JS client + Tailwind CSS

### Pages / Views

**`/` — Landing / Login**
- Simple page: "Enter your WhatsApp number to view your dashboard"
- Looks up the user by phone number in Supabase (no password — this is a demo)
- Redirects to `/dashboard`

**`/dashboard` — Main Dashboard (3 panels)**

**Panel 1: Today's Focus Log (Pomodoro)**
| What shows | Source |
|------------|--------|
| Timeline of today's sessions | `pomodoro_sessions` WHERE date = today |
| What I did (description) | `what_did_you_do` column |
| Duration per session | Calculated from `start_time` / `end_time` |
| Total focus time today | Sum of work sessions |
| Visual progress bar | Hours focused vs. a reasonable daily target |

**Panel 2: Task List**
| What shows | Source |
|------------|--------|
| Incomplete tasks (top) | `tasks` WHERE completed = false, ordered by created_at |
| Completed tasks (collapsed) | `tasks` WHERE completed = true |
| Reminder time (if set) | `reminder_time` column |
| When it was added | `created_at` column |

**Panel 3: Calorie Tracker**
| What shows | Source |
|------------|--------|
| Today's meals with cal/macros | `calorie_logs` WHERE date = today |
| Running total vs. daily goal | Sum of calories vs. `users.daily_calorie_goal` |
| Macro breakdown (protein/carbs/fat) | Sum of each macro column |
| Visual ring chart for calories remaining | Simple donut/ring chart |

### Why this works well
- No sync jobs to build or maintain — reads directly from Supabase
- Real-time data — page always shows the latest
- Polished, custom-branded UI for the hackathon demo
- Clean URL: `yourbot.vercel.app` looks professional for judges
- Free hosting on Vercel with zero config

---

## 5. Feature Specifications

### 5.1 Onboarding (Auto-triggered)

**Trigger:** First message ever from a new phone number.
**Also available:** `/onboarding` command to re-run it later.

**Flow:**
1. **Welcome:** "Hey! 👋 I'm your productivity buddy on WhatsApp. I can help you with 3 things: ⏱ Focus tracking (Pomodoro timer), ✅ Task management, and 🍎 Calorie tracking. Let's set you up! What's your name?"
2. **Name:** User replies with name → store it. "Nice to meet you, {name}! Which features do you want to use? Reply with the numbers: 1️⃣ Focus timer  2️⃣ Tasks  3️⃣ Calorie tracking  (e.g. reply '1 2 3' for all)"
3. **Feature selection** → store features_enabled.
4. **If pomodoro selected:** "How long do you like to focus for? (default: 25 min work, 5 min break). Reply like '45 10' for 45min work and 10min break, or just 'ok' for defaults."
5. **If calories selected:** "What's your daily calorie goal? (e.g. 2000). Or reply 'skip' to set it later."
6. **Done:** "You're all set! Here's what you can do: [summary of commands]. Just start chatting!"

**Key design:** The LLM handles conversational responses, so the user doesn't have to reply in exact formats. "My name is Tushar" or just "Tushar" both work.

### 5.2 Pomodoro Timer

**Starting a session:**
- User sends: `start` or `start 45 10` or `start 30` (30 work, default break)
- Bot responds: "⏱ Focus session started! 25 minutes of work time. I'll let you know when it's time for a break. Get after it!"
- `timer_end_time` is stored in the DB. The background polling loop (every 30s) picks it up when it expires and sends the notification.

**When work period ends:**
- Bot sends: "⏱ Time's up! Take a 5-minute break. Quick question — what did you work on during this session?"
- User replies with description → stored in `what_did_you_do`
- If user doesn't reply within 2 minutes, bot sends a gentle nudge
- After break ends: "Break's over! Ready for another round? Send 'start' to go again."

**Stopping a session:**
- User sends: `stop`
- Bot responds: "Session stopped. You focused for X minutes. What were you working on?" (asks for summary before closing)

**Backfilling past sessions:**
- User sends something like: "I worked on the presentation from 2pm to 4pm"
- LLM extracts: time range + description → creates a backfill pomodoro_session
- Bot confirms: "Got it! Logged 2 hours of work on 'presentation' from 2:00 PM to 4:00 PM."

**Stats:**
- `stats` → "Today you've focused for X hours across Y sessions. Here's what you did: [list]"

### 5.3 Task Management

**Adding tasks — multiple ways:**
1. **With context:** "Remind me at 9pm that I have a dentist appointment" → LLM extracts title + reminder_time
2. **Simple drop:** "Research quantum computing" → creates task with title, no reminder
3. **Zero context:** User sends random text like "groceries" → LLM decides it's a task, creates it with title "Groceries"
4. **Smart detection:** The intent classifier determines if a message is a task vs. conversation vs. other feature

**Viewing tasks:**
- `tasks` → shows incomplete tasks as a numbered list
- Bot sends: "Your tasks: 1. Dentist appointment (reminder: 9 PM) 2. Research quantum computing 3. Groceries — Reply with a number to mark it done!"

**Completing tasks:**
- User replies with number (e.g. "1" or "done 1") → marks task complete
- Bot: "✅ 'Dentist appointment' marked done!"

**Reminders:**
- The same background polling loop checks for tasks with `reminder_time` approaching
- Sends WhatsApp message: "⏰ Reminder: Dentist appointment"

### 5.4 Calorie Tracker

**Photo-based logging:**
1. User sends a photo of food
2. GPT-4o vision analyzes the image
3. Bot responds: "That looks like grilled chicken with rice and salad! Here's my estimate: 🔥 520 cal | 🥩 38g protein | 🍞 45g carbs | 🧈 18g fat — Does this look right? Reply 'yes' or tell me what to adjust."
4. User confirms → stored in calorie_logs
5. User adjusts: "It was more like 600 cal" → updates and stores

**Text-based logging:**
- "I had 2 eggs and toast for breakfast" → LLM estimates calories/macros → same confirm flow

**Daily summary:**
- `calories` → "Today's intake: 🔥 1,450 / 2,000 cal | 🥩 95g protein | 🍞 120g carbs | 🧈 65g fat — You have 550 calories remaining!"

### 5.5 Commands Reference

| Command | Action |
|---------|--------|
| `start` | Start a Pomodoro focus session (default times) |
| `start 45 10` | Start with custom work/break minutes |
| `stop` | Stop current Pomodoro session |
| `stats` | Today's focus time summary |
| `tasks` | View incomplete tasks |
| `done 1` | Complete task #1 |
| `calories` | Today's calorie summary |
| `goal 2000` | Set/update daily calorie goal |
| `/onboarding` | Re-run the onboarding flow |
| `/help` | Show all commands |
| _(any text)_ | Smart routing — LLM figures out if it's a task, conversation, or feature command |

**Design principle:** Commands are *optional*. Users can just talk naturally. "Start my timer", "what are my tasks", "how many calories today" all work through the LLM intent classifier.

---

## 6. Intent Classification & Message Routing

Every incoming message goes through this pipeline:

```
Incoming message
      │
      ▼
┌─────────────────┐
│ Is user in the   │──── YES ──▶ Route to current context handler
│ middle of a flow?│            (e.g. awaiting calorie confirmation)
└────────┬────────┘
         │ NO
         ▼
┌─────────────────┐
│ Is it a known    │──── YES ──▶ Route directly to feature handler
│ command?         │            (start, stop, tasks, calories, etc.)
│ (keyword match)  │
└────────┬────────┘
         │ NO
         ▼
┌─────────────────┐
│ LLM Intent       │──── Classifies into: pomodoro, task, calorie,
│ Classifier       │     general_chat, backfill, unknown
│ (GPT-4o)         │
└────────┬────────┘
         │
         ▼
   Route to appropriate handler
```

The keyword matcher catches obvious commands cheaply (no LLM call needed). The LLM classifier handles ambiguous natural language.

---

## 7. Opik Integration (Observability)

This is critical for the Best Use of Opik prize. Every meaningful function gets traced.

```python
import opik

# Configure Opik — use Comet cloud (free tier)
opik.configure(api_key="YOUR_OPIK_API_KEY")

@opik.track(name="message_router")
def route_message(phone_number: str, message: str, media_url: str = None) -> dict:
    """Main entry point — traces the full message handling pipeline."""
    ...

@opik.track(name="intent_classification")
def classify_intent(message: str, conversation_context: str) -> str:
    """LLM classifies message intent. Traces input/output for evaluation."""
    ...

@opik.track(name="onboarding_step")
def handle_onboarding(user: dict, message: str, step: str) -> str:
    """Handles each onboarding step. Traces the conversation flow."""
    ...

@opik.track(name="pomodoro_handler")
def handle_pomodoro(user: dict, message: str, action: str) -> str:
    """Pomodoro operations. Traces timer start/stop/summary."""
    ...

@opik.track(name="task_extraction")
def extract_task(message: str) -> dict:
    """LLM extracts task details from natural language."""
    ...

@opik.track(name="calorie_estimation")
def estimate_calories(image_url: str = None, description: str = None) -> dict:
    """GPT-4o vision estimates calories. Traces accuracy."""
    ...

@opik.track(name="backfill_parser")
def parse_backfill(message: str) -> dict:
    """LLM parses backfill request (time range + description)."""
    ...
```

**What this gives you for the demo:**
- Full trace visualization of every user interaction
- See exactly which LLM calls were made, what prompts were sent, what came back
- Track token usage and latency per feature
- Identify where the model struggles (e.g. intent misclassification, bad calorie estimates)
- Evaluation metrics over time

---

## 8. Project Structure (Monorepo)

```
whatsapp-productivity-bot/
│
├── backend/                        # FastAPI app — deployed to Railway
│   ├── main.py                     # FastAPI app, webhook endpoint, timer polling loop
│   ├── config.py                   # Environment variables, API keys
│   ├── requirements.txt
│   ├── Procfile                    # For Railway: web: uvicorn main:app --host 0.0.0.0 --port $PORT
│   ├── .env                        # API keys (gitignored)
│   ├── .env.example                # Template for API keys
│   │
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── router.py               # Message routing + intent classification
│   │   ├── onboarding.py           # Onboarding flow
│   │   ├── pomodoro.py             # Pomodoro timer logic
│   │   ├── tasks.py                # Task management
│   │   └── calories.py             # Calorie tracking
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── openai_service.py       # OpenAI API calls (chat + vision)
│   │   ├── twilio_service.py       # Twilio message sending
│   │   ├── supabase_service.py     # Database operations
│   │   └── timer_service.py        # Background polling loop for timers + reminders
│   │
│   └── prompts/
│       ├── intent_classifier.txt   # System prompt for intent classification
│       ├── task_extractor.txt      # System prompt for task extraction
│       ├── calorie_estimator.txt   # System prompt for calorie estimation
│       └── onboarding.txt          # System prompt for conversational onboarding
│
├── frontend/                       # Next.js app — deployed to Vercel (later)
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   ├── .env.local                  # NEXT_PUBLIC_SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY (later)
│   │
│   ├── app/
│   │   ├── layout.tsx              # Root layout with Tailwind
│   │   ├── page.tsx                # Landing page — enter phone number
│   │   └── dashboard/
│   │       └── page.tsx            # Main dashboard (3 panels: pomodoro, tasks, calories)
│   │
│   ├── components/
│   │   ├── PomodoroLog.tsx         # Today's focus sessions timeline
│   │   ├── TaskList.tsx            # Task list with completion toggles
│   │   └── CalorieTracker.tsx      # Calorie summary with macro breakdown
│   │
│   └── lib/
│       └── supabase.ts             # Supabase client setup (later)
│
├── scripts/
│   └── setup_supabase.sql          # SQL to create all tables
│
└── README.md
```

---

## 9. Setup Instructions

### 9.1 Supabase Setup (5 minutes)

1. Go to https://supabase.com and sign up (free, use GitHub login)
2. Click "New Project" → name it `whatsapp-bot` → choose a region close to you → set a database password (save it!)
3. Wait ~2 minutes for the project to provision
4. Go to **Settings → API → API Keys (new keys)** in the sidebar
5. Copy these values (I'll need them as environment variables):
   - **Project URL** — looks like `https://abcdefgh.supabase.co`
   - **Secret key** — starts with `sb_secret_...` (server-only, full access)
   - Note: `anon` and `service_role` are legacy JWT keys and are not recommended for new work.
   - For the future frontend, the **publishable key** (`sb_publishable_...`) lives on the same page (see 9.6).
6. Go to **SQL Editor** in the sidebar → click "New Query"
7. Paste the SQL from `scripts/setup_supabase.sql` (I'll generate this) → click "Run"
8. Done! Your tables are created.

**What I need from you:**
- Project URL
- Secret key (server-only)

### 9.2 Twilio WhatsApp Sandbox (10 minutes)

1. Log into your Twilio console at https://console.twilio.com
2. Go to **Messaging → Try it out → Send a WhatsApp message**
3. You'll see a sandbox number and a join code (like "join apple-tree")
4. On your phone, send that join code to the sandbox number via WhatsApp
5. Once connected, go to **Messaging → Settings → WhatsApp Sandbox Settings**
6. In "When a message comes in" → paste your webhook URL (we'll set this up with ngrok)
7. Set method to **POST**
8. Save

**What I need from you:**
- Twilio Account SID (from dashboard)
- Twilio Auth Token (from dashboard)
- The sandbox WhatsApp number

### 9.3 ngrok Setup (for local development, 3 minutes)

1. Go to https://ngrok.com and sign up (free)
2. Download and install ngrok
3. Run: `ngrok config add-authtoken YOUR_TOKEN`
4. Run: `ngrok http 8000` (this will expose your local FastAPI server)
5. Copy the `https://...ngrok-free.app` URL
6. Paste it into Twilio sandbox settings as: `https://YOUR-URL.ngrok-free.app/webhook`

### 9.4 Environment Variables

**Backend `.env` file (in `backend/`):**

```env
# Twilio
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# OpenAI
OPENAI_API_KEY=your_openai_key

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=sb_secret_your_secret_key

# Opik
OPIK_API_KEY=your_opik_api_key
OPIK_PROJECT_NAME=whatsapp-productivity-bot

# App
APP_ENV=development
```

Note: The backend uses the **secret key** (server-only). Frontend env vars are documented in the **Frontend Hosting (Later)** section.

### 9.5 Backend Hosting on Railway (5 minutes)

Railway gives you a free $5/month credit — more than enough for a hackathon demo. The server stays on 24/7 (no cold starts), which is critical for the Pomodoro timer polling loop.

1. Go to https://railway.app → sign up with GitHub (free)
2. Click **"New Project"** → **"Deploy from GitHub Repo"**
3. Select your repo → Railway will auto-detect the `backend/` folder (or you set the root directory to `backend/`)
4. Go to **Settings** for the service:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Go to **Variables** tab → add all the env vars from the backend `.env` above
6. Railway auto-generates a public URL like `your-app-production.up.railway.app`
7. Copy that URL → go to Twilio sandbox settings → set webhook to: `https://your-app-production.up.railway.app/webhook`

**What I need from you:**
- Just sign up at railway.app and connect your GitHub — I'll handle the config

### 9.6 Frontend Hosting on Vercel (Later / Out of scope for now)

This section is deferred until the backend is stable. Keep it here for when we reintroduce the dashboard.

1. Go to https://vercel.com → sign up with GitHub (free)
2. Click **"Add New Project"** → import your GitHub repo
3. Set **Root Directory** to `frontend`
4. Vercel auto-detects Next.js — no config needed
5. Go to **Settings → Environment Variables** → add:
   - `NEXT_PUBLIC_SUPABASE_URL` = your Supabase project URL
   - `SUPABASE_PUBLISHABLE_KEY` = your Supabase publishable key (`sb_publishable_...`)
6. Click **Deploy**
7. You get a clean URL like `yourbot.vercel.app` — this is what judges visit

**What I need from you:**
- Just sign up at vercel.com and connect your GitHub — I'll handle the Next.js setup

---

## 10. Build Order (Step by Step)

**Process rule:** Stop and review after each step. Each step must be working before moving to the next.

### Phase 1: Foundation (Day 1)
1. Set up monorepo structure (`backend/` now, `frontend/` later) and virtual environment
2. Create FastAPI app with `/webhook` endpoint
3. Set up Supabase tables (run `setup_supabase.sql`)
4. Create basic message receive → echo response (verify Twilio webhook works via ngrok)
5. Configure Opik tracing on the webhook handler
6. Set up ngrok for local development

### Phase 2: Core User Management (Day 1-2)
7. Implement user lookup by phone number
8. Build the onboarding flow (multi-step conversation)
9. Store user preferences in Supabase
10. Add conversation state management

### Phase 3: Pomodoro Timer (Day 2-3)
11. Implement `start` command → create session with `timer_end_time` in DB
12. Build the background polling loop (30s interval) that checks for expired timers and sends Twilio messages
13. Handle "what did you do" follow-up after work period
14. Implement `stop` command
15. Implement backfill parsing ("I worked on X from 2-4pm")
16. Implement `stats` command

### Phase 4: Task Management (Day 3)
17. Implement task extraction from natural language (LLM)
18. Implement simple task adding (just drop text)
19. Implement `tasks` list view
20. Implement task completion (`done 1`)
21. Add reminder checking to the same polling loop (tasks with `reminder_time` approaching)

### Phase 5: Calorie Tracking (Day 3-4)
22. Implement image receiving from Twilio (media URLs)
23. Build GPT-4o vision calorie estimation
24. Implement confirmation flow (yes/adjust)
25. Implement text-based calorie logging
26. Implement `calories` daily summary
27. Implement `goal` command

### Phase 6: Intent Classification & Smart Routing (Day 4)
28. Build the keyword command matcher
29. Build the LLM intent classifier
30. Wire up the full routing pipeline
31. Handle edge cases (ambiguous messages, multiple intents)

### Phase 7: Vercel Dashboard (Later / Out of scope)
**Later / Out of scope for now**
32. Scaffold Next.js app with Tailwind CSS
33. Set up Supabase JS client (`@supabase/supabase-js`)
34. Build landing page — phone number login
35. Build Pomodoro Log panel (today's sessions timeline)
36. Build Task List panel (incomplete + completed)
37. Build Calorie Tracker panel (meals + macro summary + ring chart)
38. Deploy to Vercel

### Phase 8: Opik Observability Polish (Day 5)
39. Ensure @track decorators on ALL LLM calls
40. Add custom metadata to traces (user_id, feature, intent)
41. Set up evaluation metrics (intent accuracy, calorie estimation quality)
42. Create Opik dashboard views for the demo
43. Test trace visualization end-to-end

### Phase 9: Production & Demo (Day 5-6)
44. Deploy backend to Railway
45. Update Twilio webhook to Railway production URL
46. Test full flow with real WhatsApp messages end-to-end
47. Prepare demo video / screenshots
48. Write submission README

---

## 11. Tests & Validation Scenarios

- Webhook returns valid TwiML on inbound WhatsApp messages.
- Task capture writes a row to `tasks` with the original `raw_message`.
- Pomodoro start/stop creates and updates `pomodoro_sessions` correctly and survives a server restart.
- Meal image → estimate → insert into `calorie_logs` (with follow-up if needed).

---

## 12. Key LLM Prompts (Drafts)

### Intent Classifier
```
You are a message router for a WhatsApp productivity bot. Classify the user's message into exactly one category:

- "pomodoro_start": User wants to start a focus/work session
- "pomodoro_stop": User wants to stop their current session
- "pomodoro_stats": User wants to see their focus time stats
- "pomodoro_backfill": User is describing work they did in the past (mentions specific times)
- "task_add": User is dropping a task, reminder, or to-do item
- "task_list": User wants to see their tasks
- "task_complete": User wants to mark a task as done
- "calorie_log": User is describing food they ate (text-based)
- "calorie_summary": User wants to see their calorie intake
- "calorie_goal": User wants to set/update their calorie goal
- "general_chat": User is chatting, asking questions, or saying something that doesn't fit above
- "help": User wants to know what commands are available

Context about the user:
- Name: {user_name}
- Active features: {features_enabled}
- Current state: {current_context}

User message: "{message}"

Respond with JSON: {"intent": "category_name", "confidence": 0.0-1.0}
```

### Calorie Estimator (Vision)
```
You are a nutritionist AI. Analyze this food image and estimate:
1. What the food items are
2. Approximate portion sizes
3. Calorie count
4. Macronutrient breakdown (protein, carbs, fat, fiber in grams)

Be reasonable with estimates — slightly overestimate rather than underestimate.
If you can't identify the food clearly, ask the user to describe it.

Respond with JSON:
{
    "description": "Brief description of the food",
    "calories": 000,
    "protein_g": 00.0,
    "carbs_g": 00.0,
    "fat_g": 00.0,
    "fiber_g": 00.0,
    "confidence": "high/medium/low",
    "notes": "Any caveats about the estimate"
}
```

### Task Extractor
```
Extract task details from this WhatsApp message. The user is quickly dropping tasks into their to-do list.

Rules:
- Create a clean, concise task title (even if the message is messy)
- Extract a reminder time if mentioned (convert to ISO 8601)
- If no specific time is mentioned, set reminder_time to null
- If the message is very vague (single word like "groceries"), make it a simple task

User message: "{message}"
Current date/time: {current_datetime}
User timezone: {timezone}

Respond with JSON:
{
    "title": "Clean task title",
    "description": "Any additional context, or null",
    "reminder_time": "ISO 8601 datetime or null",
    "raw_interpretation": "How you understood the message"
}
```

---

## 13. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Twilio sandbox limits (only pre-joined numbers) | For hackathon demo, have judges join sandbox. For public demo, apply for Twilio production approval. |
| Timer polling misses an expiry | 30s polling interval means worst case a notification is 30s late. Acceptable for this use case. |
| Railway $5 credit runs out | Very unlikely for a hackathon demo. FastAPI + polling is extremely lightweight. Monitor usage in Railway dashboard. |
| GPT-4o calorie estimates are inaccurate | Add confidence levels, always ask for confirmation, allow easy adjustment. |
| Supabase free tier limits | 500MB storage, 2GB bandwidth — more than enough for a hackathon with dozens of users. |
| Multiple users in same Pomodoro state | conversation_state table tracks per-user context. All handlers are user-scoped. |

---

## 14. Demo Strategy for Judges

**Show the full loop:**
1. Send a WhatsApp message to the bot → onboarding happens
2. Start a Pomodoro timer → get notified when done → fill in summary
3. Drop a few tasks → view the list → mark one done
4. Send a food photo → get calorie estimate → confirm
5. Ask for daily summary
6. **Open `yourbot.vercel.app`** → show the live dashboard updating in real-time with all the data from the WhatsApp session
7. **Switch to Opik** → show the traces, every LLM call, evaluation metrics

**Three screens, one story:** WhatsApp (the input) → Vercel dashboard (the output) → Opik (the observability). Clean narrative for a demo.

**This hits all judging criteria:**
- ✅ Functionality (three working features)
- ✅ Real-world relevance (people actually need this)
- ✅ Use of LLMs/Agents (intent classification, vision, NLP extraction)
- ✅ Evaluation & observability (Opik traces + dashboard)
- ✅ Goal alignment (productivity + health tracking)
