-- =============================================================
-- Safe Space Chat Memory — Supabase Schema
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New Query)
-- =============================================================

-- 1. Main chat messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    guest_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_chat_messages_guest_id ON chat_messages(guest_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);

-- 3. Enable Row Level Security (blocks direct anon access, service role bypasses)
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- 4. Auto-cleanup: delete messages older than 7 days
--    First enable pg_cron extension in Supabase Dashboard:
--    Dashboard → Database → Extensions → search "pg_cron" → Enable
--
--    Then uncomment and run this:
-- SELECT cron.schedule(
--   'cleanup-old-chat-messages',
--   '0 3 * * *',
--   $$DELETE FROM chat_messages WHERE created_at < NOW() - INTERVAL '7 days'$$
-- );

-- =============================================================
-- Onboarding & User Context Schema
-- =============================================================

CREATE TABLE IF NOT EXISTS user_context (
  guest_id             TEXT PRIMARY KEY,
  path                 TEXT DEFAULT 'deep',
  q1_situation         TEXT,
  q2_duration          TEXT,
  q3_root_cause        TEXT,
  q4_daily_impact      TEXT[],
  q5_support_need      TEXT,
  first_name           TEXT,
  session_msg_count    INT DEFAULT 0,
  is_locked            BOOLEAN DEFAULT FALSE,
  unlock_at            TIMESTAMPTZ,
  future_note          TEXT,
  future_note_created  TIMESTAMPTZ,
  created_at           TIMESTAMPTZ DEFAULT NOW(),
  updated_at           TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE user_context ENABLE ROW LEVEL SECURITY;
GRANT ALL ON user_context TO service_role;

-- =============================================================
-- E2EE: End-to-End Encryption Schema
-- Run this in Supabase SQL Editor AFTER the tables above exist
-- =============================================================

-- 1. Add opt-in column to user_context table
ALTER TABLE user_context
ADD COLUMN IF NOT EXISTS allow_training BOOLEAN DEFAULT FALSE;

-- 2. Create encrypted messages table (E2EE - developer CANNOT read)
CREATE TABLE IF NOT EXISTS chat_messages_encrypted (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    guest_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    encrypted_content TEXT NOT NULL,  -- JSON string: {iv: [], data: [], timestamp: N}
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cme_guest_id ON chat_messages_encrypted(guest_id);
CREATE INDEX IF NOT EXISTS idx_cme_created_at ON chat_messages_encrypted(created_at);
ALTER TABLE chat_messages_encrypted ENABLE ROW LEVEL SECURITY;

-- 3. Create training data table (opt-in ONLY - developer CAN read)
CREATE TABLE IF NOT EXISTS training_data (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    guest_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_training_guest_id ON training_data(guest_id);
ALTER TABLE training_data ENABLE ROW LEVEL SECURITY;

-- 4. Auto-cleanup: delete encrypted messages older than 7 days
--    (Requires pg_cron extension — enable in Dashboard → Database → Extensions)
-- SELECT cron.schedule(
--   'cleanup-encrypted-messages',
--   '0 3 * * *',
--   $$DELETE FROM chat_messages_encrypted WHERE created_at < NOW() - INTERVAL '7 days'$$
-- );

-- 5. Auto-cleanup: delete training data older than 30 days
-- SELECT cron.schedule(
--   'cleanup-training-data',
--   '0 4 * * *',
--   $$DELETE FROM training_data WHERE created_at < NOW() - INTERVAL '30 days'$$
-- );
