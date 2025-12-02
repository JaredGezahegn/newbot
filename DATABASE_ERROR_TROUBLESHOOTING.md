# Database Error Troubleshooting Guide

## Error: "A temporary database issue occurred during registration"

This error indicates a connection problem with your Supabase PostgreSQL database.

## What I've Done to Fix It

### 1. Added Retry Logic
The registration function now automatically retries up to 3 times with exponential backoff if the database connection fails.

### 2. Better Error Messages
Error messages now include details about what went wrong, making it easier to diagnose the issue.

### 3. Auto-Registration on /start
Users are automatically registered when they send `/start`, reducing the chances of hitting the error.

## Common Causes and Solutions

### Cause 1: Database Connection Limit Reached
**Symptom**: Error occurs intermittently
**Solution**: 
- Supabase free tier has connection limits
- Check your Supabase dashboard for active connections
- Consider upgrading if you hit limits frequently

### Cause 2: Database Credentials Incorrect
**Symptom**: Error occurs consistently
**Solution**:
1. Check your `.env` file has correct values:
   ```
   PGUSER=your_username
   PGPASSWORD=your_password
   PGHOST=your_host.supabase.co
   PGDATABASE=postgres
   ```
2. Verify in Vercel environment variables
3. Make sure password doesn't have special characters that need escaping

### Cause 3: Database is Paused (Free Tier)
**Symptom**: Error after period of inactivity
**Solution**:
- Supabase free tier pauses databases after inactivity
- Go to Supabase dashboard and wake up the database
- Consider upgrading for always-on database

### Cause 4: SSL Connection Issues
**Symptom**: Connection timeout or SSL errors
**Solution**:
- The settings already include `"OPTIONS": {"sslmode": "require"}`
- This should work with Supabase
- If issues persist, try `"sslmode": "prefer"`

### Cause 5: Network Issues on Vercel
**Symptom**: Random connection failures
**Solution**:
- Vercel serverless functions have cold starts
- The retry logic should handle this
- If persistent, check Vercel status page

## How to Debug

### Step 1: Check Vercel Logs
```bash
vercel logs --follow
```

Look for:
- Detailed error messages
- Database connection attempts
- Retry attempts

### Step 2: Test Database Connection
Run this command locally to test your database:
```bash
python manage.py dbshell
```

If this fails, your credentials are wrong.

### Step 3: Check Supabase Dashboard
1. Go to your Supabase project
2. Check "Database" → "Connection pooling"
3. Look for active connections
4. Check if database is paused

### Step 4: Verify Environment Variables
In Vercel dashboard:
1. Go to your project
2. Settings → Environment Variables
3. Verify all database variables are set:
   - `PGUSER`
   - `PGPASSWORD`
   - `PGHOST`
   - `PGDATABASE`

## Testing After Deployment

### Test 1: Send /start
```
/start
```
Should auto-register without errors.

### Test 2: Send /register
```
/register
```
Should either:
- Register successfully, OR
- Say "You are already registered"

### Test 3: Check Logs
If error occurs, check logs for details:
```bash
vercel logs | grep -i "database\|error"
```

## Expected Behavior After Fix

### With Retry Logic:
1. First connection attempt fails
2. Bot waits 0.1 seconds
3. Second attempt succeeds
4. User is registered successfully

### Error Message Format:
If all retries fail, you'll see:
```
❌ Database connection error. Please try again in a moment.

Error details: [first 100 characters of error]
```

This helps you diagnose the specific issue.

## Quick Fixes

### Fix 1: Restart Database (Supabase)
1. Go to Supabase dashboard
2. Project Settings → Database
3. Click "Restart database"
4. Wait 1-2 minutes
5. Try again

### Fix 2: Redeploy
Sometimes a fresh deployment helps:
```bash
vercel --prod
```

### Fix 3: Check Connection String
Get a fresh connection string from Supabase:
1. Supabase → Project Settings → Database
2. Copy connection string
3. Update environment variables
4. Redeploy

## Still Having Issues?

If the error persists after trying these solutions:

1. **Share the full error message** from Vercel logs
2. **Check Supabase status**: https://status.supabase.com/
3. **Verify database is active** in Supabase dashboard
4. **Test connection locally** with `python manage.py dbshell`

## Prevention

To prevent this error in the future:

1. **Upgrade Supabase** to paid tier for:
   - More connections
   - No auto-pause
   - Better reliability

2. **Monitor connections** in Supabase dashboard

3. **Use connection pooling** (already configured)

4. **Keep database active** by regular usage

---

**Note**: The retry logic should handle most temporary connection issues automatically. If you're still seeing errors after deployment, it's likely a configuration issue with your database credentials or Supabase plan limits.
