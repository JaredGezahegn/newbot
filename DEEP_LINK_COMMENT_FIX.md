# Deep Link Comment Display Fix

## Problem
When users clicked "View Comments" button from the channel, the bot displayed comments in the WRONG format:
- Everything in ONE message
- All buttons grouped at the bottom
- Format: Header → All comments text → Separator → All buttons

## Root Cause - Issue 1
The `/start` command deep link handler (lines 246-335 in bot/bot.py) was using OLD code that built everything in a single message, instead of using the new handlers module.

## Root Cause - Issue 2
The `handle_view_comments` function expected a `CallbackQuery` object, but the start command needed to call it with simple parameters (bot, chat_id, confession_id, page).

## Solution

### Step 1: Created new function for direct calls
Created `show_comments_for_confession(bot, chat_id, confession_id, page)` in `bot/handlers/comment_handlers.py`:
- Takes simple parameters instead of CallbackQuery
- Can be called from start command or anywhere else
- Sends header + each comment as separate messages

### Step 2: Refactored existing callback handler
Modified `handle_view_comments(bot, call)` to be a thin wrapper:
- Extracts data from CallbackQuery
- Calls `show_comments_for_confession` with extracted data
- Handles callback acknowledgment

### Step 3: Updated start command
Replaced ~80 lines of old code with:
```python
show_comments_for_confession(bot, message.chat.id, confession_id, page=1)
```

## Result
Now when users click "View Comments" from the channel, they get the CORRECT format:
- Header message: "💬 Comments for Confession #X • Page Y"
  - With "Add Comment" button: [➕ Add Comment]
  - Navigation buttons (if needed): [⬅️ Prev] [Next ➡️]
- Each comment as a SEPARATE message with:
  - Anonymous author
  - Comment text
  - Timestamp (🕒 Dec 3, 2024 • 02:30 PM)
  - Reaction buttons: [👍 N] [⚠️ N] [👎 N]
  - Reply button: [↩️ Reply]
- If no comments: "No comments yet. Be the first to comment!"

## Files Modified
1. `bot/handlers/comment_handlers.py` - Added `show_comments_for_confession()`, refactored `handle_view_comments()`
2. `bot/handlers/__init__.py` - Exported new function
3. `bot/bot.py` - Updated start command deep link handler to use new function

## Testing
Deploy to Vercel and test by:
1. Click "View Comments" button on any confession in the channel
2. Verify header appears first with page info
3. Verify each comment appears as a separate message
4. Verify each comment has its own buttons below it
5. Verify pagination works (if multiple pages)
