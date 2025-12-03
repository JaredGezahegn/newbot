# Deep Link Comment Display Fix

## Problem
When users clicked "View Comments" button from the channel, the bot displayed comments in the WRONG format:
- Everything in ONE message
- All buttons grouped at the bottom
- Format: Header → All comments text → Separator → All buttons

## Root Cause
The `/start` command deep link handler (lines 246-335 in bot/bot.py) was using OLD code that built everything in a single message, instead of using the new `handle_view_comments` function from the handlers module.

## Solution
Replaced the old inline comment display code with a call to `handle_view_comments`:

```python
# OLD CODE (removed):
# - Built response_text with all comments
# - Created inline_keyboard with all buttons
# - Sent ONE message with everything

# NEW CODE:
handle_view_comments(bot, message.chat.id, confession_id, page=1)
```

## Result
Now when users click "View Comments" from the channel, they get the CORRECT format:
- Header message with "Add Comment" button
- Each comment as a SEPARATE message
- Each comment has its own reaction buttons [👍] [👎] [↩️ Reply]
- Pagination buttons at the end if needed

## Files Modified
- `bot/bot.py` - Updated start command deep link handler (lines 256-268)

## Testing
Deploy to Vercel and test by:
1. Click "View Comments" button on any confession in the channel
2. Verify each comment appears as a separate message
3. Verify each comment has its own buttons below it
