-- ============================================================================
-- Row Level Security (RLS) Setup for Anonymous Confession Bot
-- ============================================================================
-- This script enables RLS on all public tables and creates policies to:
-- 1. Allow full access for the Django service role (used by the application)
-- 2. Deny direct public access to prevent unauthorized database queries
--
-- IMPORTANT: Run this script in your Supabase SQL Editor
-- ============================================================================

-- ============================================================================
-- Application Tables
-- ============================================================================

-- Table: bot_user (Django User model)
ALTER TABLE public.bot_user ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role has full access to bot_user" ON public.bot_user;
CREATE POLICY "Service role has full access to bot_user" 
ON public.bot_user
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Public has no access to bot_user" ON public.bot_user;
CREATE POLICY "Public has no access to bot_user" 
ON public.bot_user
FOR ALL
TO anon
USING (false);

-- Table: bot_confession
ALTER TABLE public.bot_confession ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role has full access to bot_confession" ON public.bot_confession;
CREATE POLICY "Service role has full access to bot_confession" 
ON public.bot_confession
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Public has no access to bot_confession" ON public.bot_confession;
CREATE POLICY "Public has no access to bot_confession" 
ON public.bot_confession
FOR ALL
TO anon
USING (false);

-- Table: bot_comment
ALTER TABLE public.bot_comment ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role has full access to bot_comment" ON public.bot_comment;
CREATE POLICY "Service role has full access to bot_comment" 
ON public.bot_comment
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Public has no access to bot_comment" ON public.bot_comment;
CREATE POLICY "Public has no access to bot_comment" 
ON public.bot_comment
FOR ALL
TO anon
USING (false);

-- Table: bot_reaction
ALTER TABLE public.bot_reaction ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role has full access to bot_reaction" ON public.bot_reaction;
CREATE POLICY "Service role has full access to bot_reaction" 
ON public.bot_reaction
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Public has no access to bot_reaction" ON public.bot_reaction;
CREATE POLICY "Public has no access to bot_reaction" 
ON public.bot_reaction
FOR ALL
TO anon
USING (false);

-- ============================================================================
-- Django System Tables
-- ============================================================================

-- Table: django_session
ALTER TABLE public.django_session ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role has full access to django_session" ON public.django_session;
CREATE POLICY "Service role has full access to django_session" 
ON public.django_session
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Public has no access to django_session" ON public.django_session;
CREATE POLICY "Public has no access to django_session" 
ON public.django_session
FOR ALL
TO anon
USING (false);

-- Table: django_admin_log
ALTER TABLE public.django_admin_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role has full access to django_admin_log" ON public.django_admin_log;
CREATE POLICY "Service role has full access to django_admin_log" 
ON public.django_admin_log
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Public has no access to django_admin_log" ON public.django_admin_log;
CREATE POLICY "Public has no access to django_admin_log" 
ON public.django_admin_log
FOR ALL
TO anon
USING (false);

-- Table: bot_user_groups (Many-to-Many relationship table)
ALTER TABLE public.bot_user_groups ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role has full access to bot_user_groups" ON public.bot_user_groups;
CREATE POLICY "Service role has full access to bot_user_groups" 
ON public.bot_user_groups
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Public has no access to bot_user_groups" ON public.bot_user_groups;
CREATE POLICY "Public has no access to bot_user_groups" 
ON public.bot_user_groups
FOR ALL
TO anon
USING (false);

-- Table: bot_user_user_permissions (Many-to-Many relationship table)
ALTER TABLE public.bot_user_user_permissions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role has full access to bot_user_user_permissions" ON public.bot_user_user_permissions;
CREATE POLICY "Service role has full access to bot_user_user_permissions" 
ON public.bot_user_user_permissions
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Public has no access to bot_user_user_permissions" ON public.bot_user_user_permissions;
CREATE POLICY "Public has no access to bot_user_user_permissions" 
ON public.bot_user_user_permissions
FOR ALL
TO anon
USING (false);

-- ============================================================================
-- Verification Query
-- ============================================================================
-- Run this query to verify RLS is enabled on all tables:
--
-- SELECT 
--     schemaname, 
--     tablename, 
--     rowsecurity 
-- FROM pg_tables 
-- WHERE schemaname = 'public' 
--   AND tablename IN (
--     'bot_user', 
--     'bot_confession', 
--     'bot_comment', 
--     'bot_reaction',
--     'django_session',
--     'django_admin_log',
--     'bot_user_groups',
--     'bot_user_user_permissions'
--   )
-- ORDER BY tablename;
--
-- All tables should show rowsecurity = true
-- ============================================================================
