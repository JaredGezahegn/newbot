# HTML Parsing Error Fix

## Error
```
Bad Request: can't parse entities: Unsupported start tag "id" at byte offset 175
```

## Root Cause
Telegram's HTML parser was interpreting `#` followed by numbers as HTML entities or tags. When we used patterns like:
- `ID: #{confession.id}` → becomes `ID: #1`
- `Confession #{confession_id}` → becomes `Confession #123`

Telegram tried to parse `#1` or `#123` as HTML tags, which failed.

## Solution
Removed all `#` symbols before variable IDs in HTML-formatted messages.

### Changed From:
```python
f"Your confession (ID: #{confession.id}) has been submitted"
f"<b>Confession #{confession_id}</b>"
f"<b>ID:</b> #{confession.id}"
```

### Changed To:
```python
f"Your confession (ID: {confession.id}) has been submitted"
f"<b>Confession {confession_id}</b>"
f"<b>ID:</b> {confession.id}"
```

## Files Modified

1. **bot/bot.py** - Multiple message templates
2. **bot/services/notification_service.py** - Admin and user notifications
3. **bot/services/confession_service.py** - Channel publishing message

## Testing

After redeployment, test:
1. Submit a confession → Should see "Your confession (ID: 1) has been submitted"
2. Admin approves → Should see "ID: 1" without errors
3. View comments → Should see "Comments on Confession 1" without errors
4. All buttons should work without HTML parsing errors

## Deployment

```bash
vercel --prod
```

Then test all flows to ensure no more HTML parsing errors appear in logs.
