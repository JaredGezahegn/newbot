# Supabase Connection Pooler Setup for Vercel

## Problem
Error: `Cannot assign requested address` when connecting to Supabase from Vercel.

## Solution: Use Supabase Connection Pooler

Supabase's connection pooler is designed for serverless environments like Vercel and solves IPv6/connection issues.

## Step-by-Step Setup

### 1. Get Pooler Connection String

1. Go to your **Supabase Dashboard**
2. Select your project
3. Go to **Project Settings** (gear icon)
4. Click **Database** in the left sidebar
5. Scroll to **Connection Pooling** section
6. You'll see a connection string like:
   ```
   postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
   ```

### 2. Parse the Connection String

From the pooler URL, extract:
- **Host**: `aws-0-[region].pooler.supabase.com`
- **Port**: `6543`
- **User**: `postgres.[project-ref]`
- **Password**: Your database password
- **Database**: `postgres`

Example:
```
postgresql://postgres.tpdxvbqaofdqxekixyri:mypassword@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

Becomes:
- PGHOST: `aws-0-us-east-1.pooler.supabase.com`
- PGPORT: `6543`
- PGUSER: `postgres.tpdxvbqaofdqxekixyri`
- PGPASSWORD: `mypassword`
- PGDATABASE: `postgres`

### 3. Update Vercel Environment Variables

1. Go to your **Vercel Dashboard**
2. Select your project
3. Go to **Settings** → **Environment Variables**
4. Update these variables:

```
PGHOST=aws-0-[region].pooler.supabase.com
PGPORT=6543
PGUSER=postgres.[your-project-ref]
PGPASSWORD=[your-password]
PGDATABASE=postgres
```

**Important**: 
- Use the **pooler host**, not `db.xxx.supabase.co`
- Use port **6543**, not 5432
- User format is `postgres.[project-ref]`, not just `postgres`

### 4. Redeploy

```bash
vercel --prod
```

## Why This Works

### Direct Connection (Port 5432)
- ❌ Not optimized for serverless
- ❌ IPv6 connection issues
- ❌ Connection limits
- ❌ Cold start problems

### Connection Pooler (Port 6543)
- ✅ Designed for serverless
- ✅ Handles IPv4/IPv6 properly
- ✅ Connection pooling
- ✅ Better for Vercel functions

## Verification

After redeployment, test:

1. Send `/start` to your bot
2. Should register without errors
3. Check Vercel logs - should see successful connections

## Troubleshooting

### Still Getting Errors?

**Check 1: Verify Pooler URL**
Make sure you copied from "Connection Pooling" section, not "Connection String"

**Check 2: Password Encoding**
If your password has special characters, it might need URL encoding:
- `@` → `%40`
- `#` → `%23`
- `$` → `%24`
- etc.

**Check 3: Project Reference**
The user should be `postgres.[project-ref]`, not just `postgres`

**Check 4: Port Number**
Must be `6543` for pooler, not `5432`

### Test Locally

Test the connection locally:
```bash
psql "postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres"
```

If this works, your credentials are correct.

## Alternative: Supavisor (New Pooler)

Supabase has a newer pooler called Supavisor. If available in your project:

1. Look for "Supavisor" in Database settings
2. Use the Supavisor connection string instead
3. Follow same steps as above

## Settings Already Updated

I've already updated `core/settings.py` to:
- Support both port 5432 and 6543
- Add connection timeout
- Disable connection persistence (better for serverless)

Just update your environment variables and redeploy!

---

**Summary**: Use Supabase's connection pooler (port 6543) instead of direct connection (port 5432) for Vercel deployments.
