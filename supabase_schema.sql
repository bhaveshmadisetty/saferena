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
