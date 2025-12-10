# User State Timeout Fix

## Problem Description

Users reported an issue where if they started writing a confession or comment but stopped typing for about a minute and then submitted their text, the bot would return a help message instead of processing their input properly.

## Root Cause

The bot maintains user conversation states (like `waiting_confession_text`, `waiting_comment_text`, etc.) in memory without any timeout mechanism. When users became inactive during a conversation flow, their state would remain active indefinitely, leading to:

1. Memory leaks from accumulated inactive states
2. Confusion when users resumed typing after long pauses
3. Inconsistent behavior where old states could interfere with new interactions

## Solution Implemented

### 1. Added Timeout Mechanism

**New Constants:**
```python
USER_STATE_TIMEOUT = 300  # 5 minutes in seconds
```

**Enhanced State Structure:**
```python
# Old format
user_states = {user_id: {'state': 'waiting_text', 'data': {...}}}

# New format with timestamp
user_states = {user_id: {'state': 'waiting_text', 'data': {...}, 'timestamp': datetime}}
```

### 2. State Management Functions

**`set_user_state(user_id, state, data=None)`**
- Sets user state with current timestamp
- Replaces direct dictionary assignments

**`update_user_state_timestamp(user_id)`**
- Updates timestamp when user is active in conversation
- Keeps session alive during active use

**`check_user_state_timeout(user_id)`**
- Checks if user state has expired
- Returns timeout status and expired state type
- Automatically cleans expired states

**`clean_expired_user_states()`**
- Periodically removes all expired states
- Prevents memory leaks from inactive sessions

### 3. Enhanced Message Handling

**Timeout Detection:**
```python
# Check if user state has timed out
timed_out, expired_state = check_user_state_timeout(telegram_id)
if timed_out:
    # Show helpful timeout message with instructions
    # Restore main menu keyboard
```

**Activity Tracking:**
```python
if telegram_id in user_states:
    # Update timestamp to show user is still active
    update_user_state_timestamp(telegram_id)
```

## User Experience Improvements

### Before Fix
```
User: /confess
Bot: Please type your confession...
[User stops typing for 2 minutes]
User: My confession text here
Bot: Please use /help to see available commands.
```

### After Fix
```
User: /confess
Bot: Please type your confession...
[User stops typing for 6 minutes]
User: My confession text here
Bot: ⏰ Session Timed Out
     Your confession text session has expired due to inactivity (5 minutes).
     Please start over using /confess
```

### Active Session (No Timeout)
```
User: /confess
Bot: Please type your confession...
[User types within 5 minutes]
User: My confession text here
Bot: ✅ Confession submitted successfully!
```

## Technical Details

### Timeout Duration
- **5 minutes** - Balances user convenience with resource management
- Long enough for thoughtful writing
- Short enough to prevent resource waste

### Memory Management
- Automatic cleanup of expired states
- Periodic cleaning during message processing
- No manual intervention required

### Backward Compatibility
- All existing functionality preserved
- Enhanced error messages provide clear guidance
- Graceful degradation for edge cases

## Files Modified

### `bot/bot.py`
1. **Added timeout constants and imports**
   - `USER_STATE_TIMEOUT = 300`
   - `from datetime import datetime, timedelta`

2. **Added state management functions**
   - `set_user_state()` - Create state with timestamp
   - `update_user_state_timestamp()` - Keep session alive
   - `check_user_state_timeout()` - Detect expired states
   - `clean_expired_user_states()` - Cleanup memory

3. **Updated state setting locations**
   - `/confess` command handler
   - `/comment` command handler
   - Add comment button callback
   - Reply button callback
   - Feedback button callback

4. **Enhanced message handler**
   - Timeout detection and user feedback
   - Automatic state cleanup
   - Activity timestamp updates

## Testing Scenarios

### Test Case 1: Normal Flow (No Timeout)
1. User starts `/confess`
2. User types confession within 5 minutes
3. ✅ Confession processed normally

### Test Case 2: Timeout During Confession
1. User starts `/confess`
2. User waits 6 minutes
3. User types confession text
4. ✅ Bot shows timeout message with instructions

### Test Case 3: Timeout During Comment
1. User starts `/comment 123`
2. User waits 6 minutes
3. User types comment text
4. ✅ Bot shows timeout message with instructions

### Test Case 4: Active Session Extension
1. User starts `/confess`
2. User waits 4 minutes
3. User types confession text (within 5 min total)
4. ✅ Confession processed normally (timestamp updated)

### Test Case 5: Memory Cleanup
1. Multiple users start conversations
2. Some users abandon sessions
3. ✅ Expired states automatically cleaned up

## Deployment

### No Database Changes Required
- All changes are in-memory state management
- No migrations needed
- Backward compatible

### Deploy Steps
```bash
git add bot/bot.py USER_STATE_TIMEOUT_FIX.md
git commit -m "Fix user state timeout issue - add 5min session expiry"
git push
```

### Monitoring
- Check logs for "Cleaning expired state" messages
- Monitor memory usage (should be more stable)
- User feedback on timeout messages

## Benefits

### For Users
1. **Clear Feedback** - Know when session expires
2. **Helpful Instructions** - Guided to restart process
3. **Consistent Behavior** - Predictable timeout handling
4. **No Lost Work** - Clear indication to start over

### For System
1. **Memory Management** - Automatic cleanup prevents leaks
2. **Resource Efficiency** - No indefinite state storage
3. **Better Performance** - Periodic cleanup maintains speed
4. **Debugging** - Clear timeout logs for troubleshooting

### For Developers
1. **Maintainable Code** - Centralized state management
2. **Extensible** - Easy to adjust timeout duration
3. **Testable** - Clear functions for unit testing
4. **Documented** - Well-documented timeout behavior

## Configuration

### Adjusting Timeout Duration
```python
# In bot/bot.py
USER_STATE_TIMEOUT = 300  # Change to desired seconds

# Examples:
USER_STATE_TIMEOUT = 180   # 3 minutes
USER_STATE_TIMEOUT = 600   # 10 minutes
USER_STATE_TIMEOUT = 900   # 15 minutes
```

### Customizing Timeout Messages
Edit the timeout message in `handle_unknown_command()`:
```python
timeout_message = f"""
⏰ <b>Session Timed Out</b>
Your {expired_state.replace('waiting_', '').replace('_', ' ')} session has expired...
"""
```

## Future Enhancements

Possible improvements:
1. **Warning Messages** - Notify users before timeout (e.g., at 4 minutes)
2. **Configurable Timeouts** - Different timeouts per conversation type
3. **State Persistence** - Save states to database for server restarts
4. **User Preferences** - Allow users to set their preferred timeout
5. **Analytics** - Track timeout frequency to optimize duration