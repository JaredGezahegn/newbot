# Django Admin Dashboard Guide

## Overview

Django comes with a powerful built-in admin interface that lets you manage your database through a web UI. I've configured it for your confession bot!

## What You Can Do

With the admin dashboard, you can:
- ✅ View all users, confessions, comments, and reactions
- ✅ Search and filter data
- ✅ Edit or delete records
- ✅ Approve/reject confessions manually
- ✅ Monitor user activity
- ✅ Manage admin permissions

## How to Access

### Step 1: Create an Admin User

Run this command locally:

```bash
python manage.py createsuperuser
```

You'll be prompted for:
- Username: (choose any username)
- Email: (optional, can skip)
- Password: (choose a strong password)

### Step 2: Access the Admin Panel

**Local Development:**
```
http://localhost:8000/admin/
```

**Production (Vercel):**
```
https://newbot-drab.vercel.app/admin/
```

### Step 3: Login

Use the username and password you created in Step 1.

## Admin Features Configured

### 1. User Management

**What you see:**
- Username
- Telegram ID
- Anonymous mode status
- Total confessions
- Total comments
- Impact points
- Admin status
- Registration date

**What you can do:**
- Search users by username, Telegram ID, or name
- Filter by admin status, anonymous mode, registration date
- Make users admins
- View user statistics

### 2. Confession Management

**What you see:**
- Confession ID
- User who submitted
- Status (pending/approved/rejected)
- Anonymous status
- Preview of text
- Creation date
- Reviewer

**What you can do:**
- Search confessions by text or user
- Filter by status, anonymous mode, date
- Manually approve/reject confessions
- Delete confessions
- View full confession text

### 3. Comment Management

**What you see:**
- Comment ID
- User who commented
- Related confession
- Like/dislike/report counts
- Preview of text
- Creation date

**What you can do:**
- Search comments by text, user, or confession ID
- Filter by date
- Delete inappropriate comments
- View reaction counts

### 4. Reaction Management

**What you see:**
- Reaction ID
- User who reacted
- Comment reacted to
- Reaction type (like/dislike/report)
- Creation date

**What you can do:**
- Search reactions by user or comment
- Filter by reaction type and date
- Remove reactions

## Common Admin Tasks

### Task 1: Approve a Confession Manually

1. Go to **Confessions** section
2. Filter by **Status: Pending**
3. Click on the confession
4. Change **Status** to "Approved"
5. Click **Save**

### Task 2: Delete Inappropriate Content

1. Go to **Comments** or **Confessions**
2. Find the content
3. Check the checkbox next to it
4. Select **Delete selected** from dropdown
5. Click **Go**

### Task 3: Make Someone an Admin

1. Go to **Users** section
2. Search for the user
3. Click on their username
4. Check **Is admin** checkbox
5. Click **Save**

### Task 4: View User Statistics

1. Go to **Users** section
2. You can see stats in the list view:
   - Total confessions
   - Total comments
   - Impact points
3. Click on a user to see full details

### Task 5: Monitor Reported Comments

1. Go to **Reactions** section
2. Filter by **Reaction type: Report**
3. View which comments are being reported
4. Click on comment ID to see the comment
5. Delete if inappropriate

## Admin URL Structure

```
/admin/                          - Main dashboard
/admin/bot/user/                 - User management
/admin/bot/confession/           - Confession management
/admin/bot/comment/              - Comment management
/admin/bot/reaction/             - Reaction management
```

## Security Notes

### ⚠️ Important Security Tips:

1. **Strong Password**: Use a strong, unique password for admin account
2. **Limited Access**: Only give admin access to trusted people
3. **HTTPS Only**: Always access admin over HTTPS (automatic on Vercel)
4. **Regular Monitoring**: Check admin logs regularly
5. **Backup Data**: Export data regularly

### Creating Admin on Production (Vercel)

Since Vercel is serverless, you can't run `createsuperuser` directly. Instead:

**Option 1: Create locally, then push database**
```bash
# Run locally
python manage.py createsuperuser

# The user is saved to your Supabase database
# Now you can login on production
```

**Option 2: Create via Django shell (if you have access)**
```python
from bot.models import User
User.objects.create_superuser(
    username='admin',
    password='your-strong-password',
    telegram_id=0,  # Use 0 for admin-only accounts
    is_admin=True
)
```

## Admin Customization

The admin is already configured with:

### User Admin
- ✅ List view with key stats
- ✅ Search by username, Telegram ID, name
- ✅ Filter by admin status, anonymous mode, date
- ✅ Readonly fields for security

### Confession Admin
- ✅ List view with status and preview
- ✅ Search by text and user
- ✅ Filter by status, anonymous mode, date
- ✅ Text preview (first 100 chars)

### Comment Admin
- ✅ List view with reaction counts
- ✅ Search by text, user, confession
- ✅ Filter by date
- ✅ Text preview

### Reaction Admin
- ✅ List view with all details
- ✅ Search by user and comment
- ✅ Filter by reaction type and date

## Screenshots of What You'll See

### Dashboard Home
```
Django administration
Welcome, admin

Recent actions:
- Added confession "..."
- Changed user "..."

Site administration:
- Users (125)
- Confessions (45 pending, 230 approved)
- Comments (567)
- Reactions (1,234)
```

### User List View
```
Users
[Search box]
Filters: Is admin | Anonymous mode | Created date

Username    | Telegram ID | Anonymous | Confessions | Comments | Impact | Admin | Created
----------- | ----------- | --------- | ----------- | -------- | ------ | ----- | -------
user123     | 123456789   | Yes       | 5           | 12       | 45     | No    | Dec 1
admin       | 987654321   | No        | 0           | 0        | 0      | Yes   | Nov 15
```

### Confession Detail View
```
Change confession

User: user123
Text: [Full confession text here...]
Is anonymous: ☑
Status: [Dropdown: Pending/Approved/Rejected]
Channel message ID: 12345
Reviewed by: admin
Created at: Dec 5, 2024, 3:45 PM
Reviewed at: Dec 5, 2024, 4:00 PM

[Save] [Save and continue editing] [Save and add another] [Delete]
```

## Troubleshooting

### Can't Access Admin
- Make sure you're using the correct URL
- Check that you created a superuser
- Verify your username and password

### "Permission Denied"
- Make sure your user has `is_superuser=True` or `is_staff=True`
- Check that Django admin is enabled in `INSTALLED_APPS`

### Changes Not Saving
- Check for validation errors (shown in red)
- Make sure required fields are filled
- Check database connection

## Advanced Features

### Bulk Actions
- Select multiple items with checkboxes
- Choose action from dropdown (delete, etc.)
- Click "Go"

### Export Data
- Use Django admin's built-in export
- Or use database queries
- Or add django-import-export package

### Custom Filters
- Already configured for common filters
- Can add more in `admin.py` if needed

## Files Modified

- `bot/admin.py` - Admin configuration

## Next Steps

1. Create your admin user:
   ```bash
   python manage.py createsuperuser
   ```

2. Access the admin:
   ```
   http://localhost:8000/admin/
   ```

3. Explore the interface!

## Tips

- Use search to find specific records quickly
- Use filters to narrow down results
- Click column headers to sort
- Use "Save and continue editing" to stay on the same page
- Check "Recent actions" to see what changed

Enjoy your Django admin dashboard! 🎉
