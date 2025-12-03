# Comment Reaction Display Fix

## Problem
When users liked, disliked, or reported comments, two issues occurred:
1. The comment message showed reaction counts in the text: `👍 1 | 👎 0 | 🚩 0`
2. The old `rebuild_comment_view` function was being used, which showed commenter names instead of "Anonymous"

## Root Cause
The reaction handlers (like, dislike, report) were calling `rebuild_comment_view()` which used the OLD comment format:
- Showed commenter's real name
- Included reaction counts in the message text
- Used old button layout

This didn't match the NEW format from the handlers module:
- Always shows "Anonymous"
- No reaction counts in text (only in buttons)
- Clean, minimal layout

## Solution

### Step 1: Created update function in handlers module
Added `update_comment_message()` to `bot/handlers/comment_handlers.py`:
- Refreshes comment data from database
- Uses `build_comment_text()` for consistent "Anonymous" format
- Uses `build_comment_keyboard()` for proper button layout
- Updates the message in place

### Step 2: Replaced old function calls
Updated all reaction handlers in `bot/bot.py`:
- `handle_like_comment` - now uses `update_comment_message()`
- `handle_dislike_comment` - now uses `update_comment_message()`
- `handle_report_comment` - now uses `update_comment_message()`

### Step 3: Exported new function
Added `update_comment_message` to `bot/handlers/__init__.py` exports

## Result
Now when users react to comments:
1. ✅ Comment stays anonymous (shows "Anonymous")
2. ✅ No reaction counts in message text
3. ✅ Reaction counts only appear in buttons: [👍 N] [⚠️ N] [👎 N]
4. ✅ Message format stays consistent with the new layout
5. ✅ User gets a popup notification confirming their action

## Files Modified
1. `bot/handlers/comment_handlers.py` - Added `update_comment_message()` function
2. `bot/handlers/__init__.py` - Exported new function
3. `bot/bot.py` - Updated 3 reaction handlers to use new function

## Testing
After deployment:
1. View comments on any confession
2. Click like/dislike/report on a comment
3. Verify the comment message updates with new counts in buttons
4. Verify "Anonymous" is still shown (not real name)
5. Verify no reaction counts appear in the message text
