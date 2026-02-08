-- Users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number TEXT UNIQUE NOT NULL,
    name TEXT,
    timezone TEXT DEFAULT 'UTC',
    onboarding_complete BOOLEAN DEFAULT FALSE,
    onboarding_step TEXT DEFAULT 'welcome',
    features_enabled TEXT[] DEFAULT '{}',
    default_work_minutes INTEGER DEFAULT 25,
    default_break_minutes INTEGER DEFAULT 5,
    daily_calorie_goal INTEGER,
    dietary_preferences TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pomodoro sessions
CREATE TABLE IF NOT EXISTS pomodoro_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    session_type TEXT NOT NULL, -- 'work' or 'break'
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    planned_duration_minutes INTEGER,
    what_did_you_do TEXT,
    status TEXT DEFAULT 'active', -- 'active', 'completed', 'cancelled'
    is_backfill BOOLEAN DEFAULT FALSE,
    cycle_work_minutes INTEGER,
    cycle_break_minutes INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tasks
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    title TEXT NOT NULL,
    description TEXT,
    raw_message TEXT,
    reminder_time TIMESTAMPTZ,
    reminder_sent BOOLEAN DEFAULT FALSE,
    completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Calorie logs
CREATE TABLE IF NOT EXISTS calorie_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    meal_description TEXT,
    image_url TEXT,
    calories INTEGER,
    protein_g FLOAT,
    carbs_g FLOAT,
    fat_g FLOAT,
    fiber_g FLOAT,
    confirmed BOOLEAN DEFAULT FALSE,
    logged_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conversation state
CREATE TABLE IF NOT EXISTS conversation_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    phone_number TEXT NOT NULL,
    current_context TEXT,
    context_data JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'conversation_state_user_id_key'
    ) THEN
        ALTER TABLE conversation_state
        ADD CONSTRAINT conversation_state_user_id_key UNIQUE (user_id);
    END IF;
END$$;
