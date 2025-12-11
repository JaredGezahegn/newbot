# Row Level Security (RLS) Setup Instructions

## Overview

This guide explains how to enable Row Level Security (RLS) on your Supabase database tables to address the security warnings you're receiving.

## What is Row Level Security?

Row Level Security (RLS) is a PostgreSQL feature that restricts which rows users can access in database tables. Supabase requires RLS to be enabled on all public tables to prevent unauthorized direct database access.

## Current Security Issue

Your Supabase dashboard is showing warnings for these tables:
- `bot_user`
- `bot_confession`
- `bot_comment`
- `bot_reaction`
- `django_session`
- `django_admin_log`
- `bot_user_groups`
- `bot_user_user_permissions`

## How RLS Works in This Setup

1. **Service Role Access**: Your Django application connects using the service role credentials, which bypass RLS policies. This allows your app to perform all database operations normally.

2. **Public Access Denied**: Direct database access (without proper authentication) is blocked by RLS policies, protecting your data from unauthorized queries.

## Step-by-Step Setup

### Step 1: Access Supabase SQL Editor

1. Go to your Supabase project dashboard
2. Navigate to the **SQL Editor** section in the left sidebar
3. Click **New Query**

### Step 2: Run the RLS Script

1. Open the `enable_rls.sql` file in this repository
2. Copy the entire contents of the file
3. Paste it into the Supabase SQL Editor
4. Click **Run** to execute the script

The script will:
- Enable RLS on all 8 tables
- Create policies allowing full access for authenticated service role
- Create policies denying direct public access

### Step 3: Verify RLS is Enabled

Run this verification query in the SQL Editor:

```sql
SELECT 
    schemaname, 
    tablename, 
    rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' 
  AND tablename IN (
    'bot_user', 
    'bot_confession', 
    'bot_comment', 
    'bot_reaction',
    'django_session',
    'django_admin_log',
    'bot_user_groups',
    'bot_user_user_permissions'
  )
ORDER BY tablename;
```

**Expected Result**: All tables should show `rowsecurity = true`

### Step 4: Verify Your Django Connection

Ensure your Django application is using the correct database credentials:

1. Check your `.env` file or environment variables
2. Verify you're using the **service role** connection string (not the anon key)
3. Your connection should look like this:

```
PGHOST=aws-0-us-east-1.pooler.supabase.com
PGDATABASE=postgres
PGUSER=postgres.your-project-ref
PGPASSWORD=your-service-role-password
```

### Step 5: Test Your Application

1. Deploy your application or restart your local server
2. Test all bot functionality:
   - User registration
   - Confession submission
   - Admin moderation
   - Comments and reactions
3. Verify everything works normally

## Troubleshooting

### Issue: "Permission denied" errors after enabling RLS

**Solution**: Verify your Django app is using the service role credentials, not the anon key. The service role has permission to bypass RLS.

### Issue: Tables still show RLS warnings in Supabase

**Solution**: 
1. Refresh your Supabase dashboard
2. Wait a few minutes for the dashboard to update
3. Run the verification query to confirm RLS is actually enabled

### Issue: Script fails with "relation does not exist"

**Solution**: Some tables may not exist yet if migrations haven't run. This is normal. The script will enable RLS on existing tables. Run migrations first if needed:

```bash
python manage.py migrate
```

## Security Best Practices

1. **Never expose your service role key**: Keep it in environment variables only
2. **Use the anon key for client-side access**: If you add a web interface later
3. **Review policies regularly**: Ensure they match your security requirements
4. **Monitor access logs**: Check Supabase logs for suspicious activity

## Additional Resources

- [Supabase RLS Documentation](https://supabase.com/docs/guides/auth/row-level-security)
- [PostgreSQL RLS Documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

## Questions?

If you encounter any issues or have questions about RLS setup, refer to the Supabase documentation or check your application logs for specific error messages.
