# Confession Menu Button Fix

## Problem
After submitting a confession, the bot showed 4 buttons instead of the standard 3-button menu:
- 📝 Confess
- 👤 Profile
- 💬 My Comments ❌ (shouldn't be here)
- ❓ Help

## Root Cause
Multiple places in bot.py were creating a 4-button keyboard after confession-related actions:
1. After successful confession submission (line ~1156)
2. After canceling confession edit (line ~1209)
3. After canceling confession submission (line ~1777)

## Solution
Replaced all 4-button keyboards with the standard 3-button main menu:
- ✍️ Confess
- 👤 Profile
- ℹ️ Help

Changed from:
```python
keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.row(KeyboardButton("📝 Confess"), KeyboardButton("👤 Profile"))
keyboard.row(KeyboardButton("💬 My Comments"), KeyboardButton("❓ Help"))
```

To:
```python
keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
keyboard.add(
    KeyboardButton("✍️ Confess"),
    KeyboardButton("👤 Profile"),
    KeyboardButton("ℹ️ Help")
)
```

## Files Modified
- `bot/bot.py` - Fixed 3 locations where 4-button keyboard was used

## Result
Now after submitting, editing, or canceling a confession, users see the standard 3-button menu matching the rest of the bot interface.

## Note
The "My Comments" button handler still exists in the code but won't be triggered since the button is no longer displayed. Users can still access their comments via the `/mycomments` command if needed.
