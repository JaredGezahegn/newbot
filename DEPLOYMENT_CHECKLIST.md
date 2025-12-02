# Deployment Checklist for Anonymous Confession Bot

This checklist covers the final deployment steps for the Anonymous Confession Bot to Vercel.

## ✅ Completed Development Tasks

- [x] All models created and migrated
- [x] All service layer functions implemented
- [x] All bot command handlers implemented
- [x] All property-based tests passing (13 tests)
- [x] All integration tests passing (25 tests)
- [x] Error handling implemented
- [x] Database retry logic implemented

## 📋 Pre-Deployment Checklist

### 1. Environment Variables Configuration

Ensure the following environment variables are set in Vercel:

```bash
# Bot Configuration
BOT_TOKEN=<your_telegram_bot_token>
CHANNEL_ID=<your_telegram_channel_id>
ADMINS=<comma_separated_admin_telegram_ids>
WEB_HOOK_URL=<your_vercel_deployment_url>/webhook/

# Django Configuration
SECRET_KEY=<your_django_secret_key>
DEBUG=False
ALLOWED_HOSTS=.vercel.app

# Database Configuration (Supabase)
PGUSER=<postgres_username>
PGPASSWORD=<postgres_password>
PGHOST=<postgres_host>
PGDATABASE=<postgres_database_name>
PGPORT=5432
```

### 2. Telegram Bot Setup

- [ ] Create bot via @BotFather on Telegram
- [ ] Get bot token and add to environment variables
- [ ] Create a Telegram channel for publishing confessions
- [ ] Add bot as administrator to the channel
- [ ] Get channel ID (use @userinfobot or check channel info)
- [ ] Add channel ID to environment variables

### 3. Database Setup (Supabase)

- [ ] Create Supabase project
- [ ] Get PostgreSQL connection details
- [ ] Add database credentials to environment variables
- [ ] Ensure database is accessible from Vercel

### 4. Admin Configuration

- [ ] Identify admin Telegram user IDs
- [ ] Add admin IDs to ADMINS environment variable (comma-separated)
- [ ] Verify admins can access admin commands

## 🚀 Deployment Steps

### Step 1: Deploy to Vercel

```bash
# Install Vercel CLI if not already installed
npm install -g vercel

# Login to Vercel
vercel login

# Deploy
vercel --prod
```

### Step 2: Run Database Migrations

Migrations should run automatically via `build.sh`, but verify:

```bash
# Check build logs in Vercel dashboard
# Ensure migrations completed successfully
```

### Step 3: Set Webhook

After deployment, set the webhook URL:

```bash
# Option 1: Use Django management command
python manage.py set_webhook

# Option 2: Manual API call
curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=<VERCEL_URL>/webhook/"
```

### Step 4: Verify Webhook

```bash
# Check webhook status
curl "https://api.telegram.org/bot<BOT_TOKEN>/getWebhookInfo"
```

Expected response should show:
- `url`: Your Vercel webhook URL
- `has_custom_certificate`: false
- `pending_update_count`: 0
- `last_error_date`: should be empty or old

## 🧪 Post-Deployment Testing

### Test Complete User Flow

1. **User Registration**
   - [ ] Send `/start` to bot
   - [ ] Send `/register` to bot
   - [ ] Verify registration confirmation

2. **Confession Submission**
   - [ ] Send `/confess` to bot
   - [ ] Enter confession text
   - [ ] Verify submission confirmation
   - [ ] Check admin receives notification

3. **Admin Approval**
   - [ ] Admin receives pending confession notification
   - [ ] Admin clicks "Approve" button
   - [ ] Verify confession published to channel
   - [ ] Verify user receives approval notification

4. **Comment System**
   - [ ] Click "View / Add Comments" on channel post
   - [ ] Add a comment
   - [ ] Verify comment appears
   - [ ] Test like/dislike reactions
   - [ ] Verify reaction counts update

### Test Admin Workflows

1. **View Pending Confessions**
   - [ ] Admin sends `/pending`
   - [ ] Verify list of pending confessions

2. **View Statistics**
   - [ ] Admin sends `/stats`
   - [ ] Verify counts are accurate

3. **Delete Confession**
   - [ ] Admin sends `/delete <id>`
   - [ ] Verify confession deleted from database
   - [ ] Verify confession deleted from channel

### Test Error Handling

1. **Invalid Commands**
   - [ ] Send invalid command (e.g., `/invalidcommand`)
   - [ ] Verify helpful error message

2. **Character Limit**
   - [ ] Try to submit confession > 4096 characters
   - [ ] Verify rejection with error message

3. **Permission Denied**
   - [ ] Non-admin tries `/pending`
   - [ ] Verify permission denied message

4. **Invalid Confession ID**
   - [ ] Try `/comment 999999`
   - [ ] Verify "not found" error message

## 📊 Monitoring

### Check Logs

```bash
# View Vercel function logs
vercel logs <deployment-url>
```

### Monitor Database

- [ ] Check Supabase dashboard for connection count
- [ ] Monitor query performance
- [ ] Check for any errors in logs

### Monitor Bot Health

- [ ] Periodically check webhook status
- [ ] Monitor response times
- [ ] Check for any Telegram API errors

## 🔧 Troubleshooting

### Webhook Not Working

1. Check webhook URL is correct
2. Verify SSL certificate is valid
3. Check Vercel function logs for errors
4. Ensure webhook returns 200 OK

### Database Connection Issues

1. Verify database credentials
2. Check Supabase connection limits
3. Review retry logic in logs
4. Ensure database is not paused (Supabase free tier)

### Bot Not Responding

1. Check bot token is correct
2. Verify webhook is set correctly
3. Check Vercel function logs
4. Ensure no rate limiting from Telegram

### Admin Commands Not Working

1. Verify admin IDs are correct
2. Check ADMINS environment variable format
3. Ensure admins have registered with bot
4. Check permission checking logic

## 📝 Notes

- **Database Migrations**: Run automatically on each deployment via `build.sh`
- **Static Files**: Collected automatically during build
- **Webhook**: Must be set after each deployment if URL changes
- **Environment Variables**: Changes require redeployment
- **Logs**: Available in Vercel dashboard under Functions tab

## ✅ Deployment Complete

Once all items are checked:

- [ ] All environment variables configured
- [ ] Bot deployed to Vercel
- [ ] Webhook set and verified
- [ ] Complete user flow tested
- [ ] Admin workflows tested
- [ ] Error handling tested
- [ ] Monitoring in place

**Congratulations! Your Anonymous Confession Bot is live! 🎉**

## 🔗 Useful Links

- [Telegram Bot API Documentation](https://core.telegram.org/bots/api)
- [Vercel Documentation](https://vercel.com/docs)
- [Supabase Documentation](https://supabase.com/docs)
- [Django Documentation](https://docs.djangoproject.com/)

## 📞 Support

If you encounter issues:

1. Check Vercel function logs
2. Review Telegram webhook info
3. Check Supabase database logs
4. Review this checklist for missed steps
