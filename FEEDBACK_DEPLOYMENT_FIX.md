# Feedback System Deployment Fix

## Problem
When users try to submit feedback, they get an error: "Failed to submit feedback. Please try again."

## Root Cause
The `bot_feedback` table doesn't exist in the database yet because the migration hasn't been run.

## Solution

### Option 1: Run Migration via Vercel (Recommended)

Since you're on Vercel, the migration should run automatically on deployment. However, if it didn't, you need to trigger it manually.

**Check Vercel Logs:**
1. Go to your Vercel dashboard
2. Click on your project
3. Go to "Deployments"
4. Click on the latest deployment
5. Check the "Build Logs" for migration errors

**If migrations didn't run, you need to:**

Add a build command to run migrations in `vercel.json`:

```json
{
  "builds": [
    {
      "src": "core/wsgi.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "core/wsgi.py"
    }
  ],
  "env": {
    "DJANGO_SETTINGS_MODULE": "core.settings"
  }
}
```

Or add to `build.sh`:
```bash
#!/bin/bash
python manage.py migrate --noinput
```

### Option 2: Run Migration via Django Admin

If you have access to Django admin or a Python shell on your server:

```python
python manage.py migrate bot
```

### Option 3: Run Migration via SQL (Direct Database Access)

If you have direct access to your Supabase database, run this SQL:

```sql
-- Create bot_feedback table
CREATE TABLE bot_feedback (
    id BIGSERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    admin_notes TEXT DEFAULT '',
    reviewed_by_id BIGINT REFERENCES bot_user(id) ON DELETE SET NULL,
    user_id BIGINT NOT NULL REFERENCES bot_user(id) ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX bot_feedback_status_idx ON bot_feedback(status);
CREATE INDEX bot_feedback_created_at_idx ON bot_feedback(created_at);
CREATE INDEX bot_feedback_reviewed_by_id_idx ON bot_feedback(reviewed_by_id);
CREATE INDEX bot_feedback_user_id_idx ON bot_feedback(user_id);

-- Add to migration history
INSERT INTO django_migrations (app, name, applied)
VALUES ('bot', '0004_feedback', NOW());
```

### Option 4: Check and Run via Python Script

I created a script to check and run migrations:

```bash
python check_feedback_table.py
```

This will:
1. Check if the `bot_feedback` table exists
2. If not, run the migration automatically
3. Show you the results

## Verification

After running the migration, verify it worked:

### Via Python:
```python
python manage.py shell

from bot.models import Feedback
print(Feedback.objects.count())  # Should return 0 (no feedback yet)
```

### Via SQL:
```sql
SELECT * FROM bot_feedback LIMIT 1;
```

### Via Bot:
1. Type `/help`
2. Click **📝 Send Feedback**
3. Type some feedback (at least 10 characters)
4. Should see: "✅ Feedback Submitted!"

## Current Error Details

The error message now includes more details. When you try to submit feedback again, you should see:

```
❌ Failed to submit feedback. Please try again.

Error: [specific error message]
```

This will tell us exactly what's wrong. Common errors:

1. **"relation 'bot_feedback' does not exist"** → Migration hasn't run
2. **"column 'xyz' does not exist"** → Migration is incomplete
3. **"permission denied"** → Database user doesn't have CREATE TABLE permission

## Quick Fix Commands

### For Vercel:
```bash
# Redeploy to trigger migrations
git commit --allow-empty -m "Trigger migration"
git push
```

### For Local Testing:
```bash
python manage.py migrate bot
python manage.py runserver
```

### For Supabase Direct:
```bash
# Connect to Supabase and run the SQL above
```

## Next Steps

1. **Try the feedback feature again** - The error message will now show more details
2. **Share the error message** - I can help debug based on the specific error
3. **Check Vercel logs** - Look for migration errors in the deployment logs
4. **Run the check script** - Use `python check_feedback_table.py` to diagnose

## Prevention

To ensure migrations run automatically on Vercel:

1. Add to `build.sh`:
```bash
#!/bin/bash
echo "Running migrations..."
python manage.py migrate --noinput
echo "Migrations complete!"
```

2. Make it executable:
```bash
chmod +x build.sh
```

3. Update `vercel.json` to use it:
```json
{
  "buildCommand": "bash build.sh"
}
```

Let me know what error message you see now, and I'll help you fix it! 🔧
