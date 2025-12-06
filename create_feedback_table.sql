-- Create bot_feedback table for anonymous feedback system
-- Run this in Supabase SQL Editor if migration didn't run automatically

-- Create the table
CREATE TABLE IF NOT EXISTS bot_feedback (
    id BIGSERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    admin_notes TEXT DEFAULT '',
    reviewed_by_id BIGINT REFERENCES bot_user(id) ON DELETE SET NULL,
    user_id BIGINT NOT NULL REFERENCES bot_user(id) ON DELETE CASCADE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS bot_feedback_status_idx ON bot_feedback(status);
CREATE INDEX IF NOT EXISTS bot_feedback_created_at_idx ON bot_feedback(created_at);
CREATE INDEX IF NOT EXISTS bot_feedback_reviewed_by_id_idx ON bot_feedback(reviewed_by_id);
CREATE INDEX IF NOT EXISTS bot_feedback_user_id_idx ON bot_feedback(user_id);

-- Add to Django migration history (so Django knows it's been applied)
INSERT INTO django_migrations (app, name, applied)
VALUES ('bot', '0004_feedback', NOW())
ON CONFLICT DO NOTHING;

-- Verify the table was created
SELECT 
    'bot_feedback table created successfully!' as message,
    COUNT(*) as feedback_count 
FROM bot_feedback;
