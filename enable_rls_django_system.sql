-- ============================================================================
-- Row Level Security (RLS) for Django System Tables
-- ============================================================================
-- This script enables RLS on the remaining Django system tables
-- ============================================================================

-- Table: auth_group
ALTER TABLE public.auth_group ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role has full access to auth_group" ON public.auth_group;
CREATE POLICY "Service role has full access to auth_group" 
ON public.auth_group
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Public has no access to auth_group" ON public.auth_group;
CREATE POLICY "Public has no access to auth_group" 
ON public.auth_group
FOR ALL
TO anon
USING (false);

-- Table: auth_group_permissions
ALTER TABLE public.auth_group_permissions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role has full access to auth_group_permissions" ON public.auth_group_permissions;
CREATE POLICY "Service role has full access to auth_group_permissions" 
ON public.auth_group_permissions
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Public has no access to auth_group_permissions" ON public.auth_group_permissions;
CREATE POLICY "Public has no access to auth_group_permissions" 
ON public.auth_group_permissions
FOR ALL
TO anon
USING (false);

-- Table: auth_permission
ALTER TABLE public.auth_permission ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role has full access to auth_permission" ON public.auth_permission;
CREATE POLICY "Service role has full access to auth_permission" 
ON public.auth_permission
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Public has no access to auth_permission" ON public.auth_permission;
CREATE POLICY "Public has no access to auth_permission" 
ON public.auth_permission
FOR ALL
TO anon
USING (false);

-- Table: django_content_type
ALTER TABLE public.django_content_type ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role has full access to django_content_type" ON public.django_content_type;
CREATE POLICY "Service role has full access to django_content_type" 
ON public.django_content_type
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Public has no access to django_content_type" ON public.django_content_type;
CREATE POLICY "Public has no access to django_content_type" 
ON public.django_content_type
FOR ALL
TO anon
USING (false);

-- Table: django_migrations
ALTER TABLE public.django_migrations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role has full access to django_migrations" ON public.django_migrations;
CREATE POLICY "Service role has full access to django_migrations" 
ON public.django_migrations
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Public has no access to django_migrations" ON public.django_migrations;
CREATE POLICY "Public has no access to django_migrations" 
ON public.django_migrations
FOR ALL
TO anon
USING (false);

-- ============================================================================
-- Done! All Django system tables now have RLS enabled.
-- ============================================================================
