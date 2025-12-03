# Reaction Toggle Logic Fix

## Problem
Users couldn't like/dislike AND report a comment at the same time. All reactions were mutually exclusive, which was wrong.

**Current (WRONG) behavior:**
- User likes a comment
- User tries to report it
- The like is removed and replaced with report

**Desired (CORRECT) behavior:**
- Like and Dislike toggle each other (mutually exclusive)
- Report is independent (can report AND have a like/dislike)

## Root Cause
The Reaction model had `unique_together = ('comment', 'user')` which enforced only ONE reaction per user per comment. This made all reaction types mutually exclusive.

## Solution

### Step 1: Changed database constraint
Updated `bot/models.py` Reaction model:
```python
# OLD:
unique_together = ('comment', 'user')

# NEW:
unique_together = ('comment', 'user', 'reaction_type')
```

This allows multiple reactions per user per comment, but prevents duplicate reaction types.

### Step 2: Rewrote add_reaction logic
Updated `bot/services/comment_service.py` `add_reaction()` function:

**Like/Dislike logic:**
1. Check if user already has this exact reaction → do nothing
2. Check if user has opposite reaction (like vs dislike) → remove it
3. Create new reaction and increment count

**Report logic:**
1. Check if user already reported → do nothing
2. Create new report reaction (doesn't affect existing like/dislike)
3. Increment report count

## Result
Now users can:
- ✅ Like a comment, then report it (both reactions exist)
- ✅ Dislike a comment, then report it (both reactions exist)
- ✅ Switch from like to dislike (toggle behavior)
- ✅ Switch from dislike to like (toggle behavior)
- ✅ Report multiple times does nothing (already reported)
- ✅ Like multiple times does nothing (already liked)

## Files Modified
1. `bot/models.py` - Changed Reaction model unique_together constraint
2. `bot/services/comment_service.py` - Rewrote add_reaction() function logic

## Database Migration
A migration is needed to update the database constraint. This will run automatically on Vercel when deployed.

**Migration command (for reference):**
```bash
python manage.py makemigrations bot --name change_reaction_unique_constraint
python manage.py migrate
```

## Testing
After deployment:
1. Like a comment → verify it shows [👍 1]
2. Report the same comment → verify it shows [⚠️ 1] and like is still there [👍 1]
3. Click dislike → verify like is removed [👍 0] and dislike appears [👎 1]
4. Report is still there [⚠️ 1]
