# Comment Count in Button Feature

## Overview

Added comment count display to the "View / Add Comments" button on channel posts, showing users how many comments exist before they click.

## Changes Made

### 1. Updated Button Creation (`bot/services/confession_service.py`)

**Function:** `publish_to_channel()`

Added comment count to button text when confession is first published:

```python
# Get comment count for this confession
comment_count = confession.comments.count()

# Include comment count in button text
button_text = f"💬 View / Add Comments ({comment_count})"
```

### 2. Added Button Update Function (`bot/services/comment_service.py`)

**New Function:** `update_channel_button()`

Updates the channel message button whenever a new comment is added:

```python
def update_channel_button(confession, bot_instance):
    """
    Update the "View / Add Comments" button on the channel message 
    with current comment count.
    """
    # Get current comment count
    comment_count = confession.comments.count()
    
    # Create updated keyboard
    button_text = f"💬 View / Add Comments ({comment_count})"
    
    # Update the message's reply markup
    bot_instance.edit_message_reply_markup(
        chat_id=channel_id,
        message_id=confession.channel_message_id,
        reply_markup=keyboard
    )
```

### 3. Updated Comment Creation (`bot/services/comment_service.py`)

**Function:** `create_comment()`

Now accepts `bot_instance` parameter and automatically updates the channel button:

```python
def create_comment(user, confession, text, parent_comment=None, bot_instance=None):
    # ... create comment ...
    
    # Update channel message button with new comment count
    if bot_instance and confession.channel_message_id:
        update_channel_button(confession, bot_instance)
```

### 4. Updated Bot Handlers (`bot/bot.py`)

Updated both places where comments are created to pass the bot instance:

**Comment creation:**
```python
comment = create_comment(user, confession, comment_text, bot_instance=bot)
```

**Reply creation:**
```python
reply = create_comment(user, confession, reply_text, parent_comment=parent_comment, bot_instance=bot)
```

## How It Works

### Initial State (No Comments)
When a confession is approved and published:
```
💬 View / Add Comments (0)
```

### After Comments Are Added
When users add comments, the button updates automatically:
```
💬 View / Add Comments (1)
💬 View / Add Comments (5)
💬 View / Add Comments (16)
```

## User Experience

### Before
- Button showed: "💬 View / Add Comments"
- Users had no idea how many comments existed
- Had to click to see if there were any comments

### After
- Button shows: "💬 View / Add Comments (16)"
- Users can see comment count at a glance
- Encourages engagement when they see active discussions

## Technical Details

### Real-time Updates
- Button updates immediately when a comment is added
- Uses Telegram's `edit_message_reply_markup` API
- Only updates the button, not the entire message
- Handles errors gracefully (won't fail comment creation if button update fails)

### Performance
- Comment count is calculated using `confession.comments.count()`
- Efficient database query (uses COUNT)
- No impact on comment creation performance

### Error Handling
- If button update fails, comment is still created successfully
- Errors are logged but don't affect user experience
- Button will show correct count on next comment

## Testing

### Manual Testing Steps

1. **Submit and approve a confession**
   - Check button shows: "💬 View / Add Comments (0)"

2. **Add first comment**
   - Button should update to: "💬 View / Add Comments (1)"

3. **Add more comments**
   - Button should increment: (2), (3), (4), etc.

4. **Add a reply to a comment**
   - Button should still increment (replies count as comments)

5. **Check from channel**
   - Open channel post
   - Verify button shows correct count
   - Click button to verify it still works

## Deployment

### No Database Changes Required
- Uses existing `channel_message_id` field
- Uses existing `comments` relationship
- No migrations needed

### No Configuration Changes Required
- Uses existing `BOT_USERNAME` setting
- Uses existing `CHANNEL_ID` setting

### Deploy Steps
1. Push code to GitHub
2. Vercel will auto-deploy
3. Feature works immediately on new confessions
4. Existing confessions will show count when next comment is added

## Notes

- Button only updates when comments are added through the bot
- If database is manually modified, button won't update until next comment
- Count includes both top-level comments and replies
- Works with the existing deep link system

## Files Modified

1. `bot/services/confession_service.py` - Added comment count to initial button
2. `bot/services/comment_service.py` - Added update function and bot_instance parameter
3. `bot/bot.py` - Pass bot instance when creating comments

## Related Features

- Deep link system for opening bot from channel
- Comment pagination system
- Reaction system (likes, dislikes, reports)
