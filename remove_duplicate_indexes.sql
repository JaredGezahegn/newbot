-- ============================================================================
-- Remove Duplicate Indexes (Performance Optimization)
-- ============================================================================
-- This script removes duplicate indexes that Django created automatically.
-- These duplicates don't affect functionality, just waste a bit of space.
-- ============================================================================

-- Drop duplicate index on bot_comment.confession_id
-- Keep: bot_comment_confession_id_a0e9876d (Django's foreign key index)
-- Drop: bot_comment_confess_4df5dc_idx (custom index from Meta.indexes)
DROP INDEX IF EXISTS public.bot_comment_confess_4df5dc_idx;

-- Drop duplicate index on bot_confession.status
-- Keep: bot_confession_status_28011364 (Django's db_index=True)
-- Drop: bot_confess_status_e6a49d_idx (custom index from Meta.indexes)
DROP INDEX IF EXISTS public.bot_confess_status_e6a49d_idx;

-- ============================================================================
-- Done! Duplicate indexes removed.
-- ============================================================================
