# Commenter Stats Display Feature

## Overview

Added display of commenter's impact points and community acceptance score on each comment, with emoji indicators based on acceptance level.

## Changes Made

### Updated `bot/handlers/comment_handlers.py`

**Added Function:** `get_acceptance_emoji()`

Determines which emoji to show based on community acceptance score:
- 😈 (Devil) - Below 30% acceptance
- 😐 (Neutral) - Between 30% and 50% acceptance  
- 😇 (Angel) - Above 50% acceptance

**Updated Function:** `build_comment_text()`

Now includes commenter stats line between comment text and timestamp:

```python
👤 • ⭐ {impact_points} • {emoji} {acceptance_score}
```

## Display Format

### Before:
```
Anonymous
Great perspective on this situation...
🕒 Dec 3, 2024 • 02:30 PM
```

### After:
```
Anonymous
Great perspective on this situation...

👤 • ⭐ -11 • 😈 1.58
🕒 Dec 3, 2024 • 02:30 PM
```

## Stats Explained

### Impact Points (⭐)
- Calculated from: approved confessions + comments + likes received
- Can be negative if user has more dislikes than likes
- Shows user's overall contribution to the community

### Community Acceptance Score (😈/😐/😇)
- Percentage of positive reactions vs total reactions
- Formula: (likes / total reactions) × 100
- Emoji changes based on score:
  - **😈 < 30%** - Low acceptance (controversial user)
  - **😐 30-50%** - Neutral acceptance (mixed reception)
  - **😇 > 50%** - High acceptance (well-liked user)

## Example Scenarios

### New User (No Reactions Yet)
```
Anonymous
This is my first comment!

👤 • ⭐ 1 • 😈 0.00
🕒 Dec 5, 2024 • 10:30 AM
```
- Impact: 1 (from the comment itself)
- Acceptance: 0% (no reactions yet) → 😈

### Controversial User
```
Anonymous
Hot take: pineapple belongs on pizza!

👤 • ⭐ 15 • 😈 25.50
🕒 Dec 5, 2024 • 11:15 AM
```
- Impact: 15 (active but divisive)
- Acceptance: 25.5% (more dislikes than likes) → 😈

### Neutral User
```
Anonymous
I see both sides of this argument.

👤 • ⭐ 42 • 😐 45.00
🕒 Dec 5, 2024 • 12:00 PM
```
- Impact: 42 (moderately active)
- Acceptance: 45% (balanced reactions) → 😐

### Popular User
```
Anonymous
Great advice! This really helped me.

👤 • ⭐ 128 • 😇 87.50
🕒 Dec 5, 2024 • 1:30 PM
```
- Impact: 128 (very active)
- Acceptance: 87.5% (mostly likes) → 😇

## Technical Details

### Performance
- Stats are calculated on-the-fly when comment is displayed
- Uses existing `calculate_impact_points()` and `calculate_acceptance_score()` functions
- Efficient database queries with proper indexing

### Calculation Methods

**Impact Points:**
```python
impact_points = approved_confessions + total_comments + positive_reactions
```

**Acceptance Score:**
```python
acceptance_score = (positive_reactions / total_reactions) × 100
```

## User Experience

### Benefits
1. **Reputation System** - Users can see who's trusted in the community
2. **Engagement Indicator** - Shows how active and well-received a user is
3. **Visual Feedback** - Emojis make it easy to quickly assess reputation
4. **Transparency** - Everyone can see the same stats

### Privacy
- Still shows "Anonymous" as the name
- Stats are aggregate and don't reveal identity
- Encourages quality contributions

## Edge Cases Handled

### No Reactions Yet
- Acceptance score: 0.00%
- Shows 😈 emoji (will improve as they get reactions)

### Only Negative Reactions
- Acceptance score: 0.00%
- Shows 😈 emoji

### Only Positive Reactions
- Acceptance score: 100.00%
- Shows 😇 emoji

### Negative Impact Points
- Can happen if user has very few contributions but many dislikes
- Displayed as negative number (e.g., ⭐ -5)

## Files Modified

1. `bot/handlers/comment_handlers.py`
   - Added `get_acceptance_emoji()` function
   - Updated `build_comment_text()` to include stats

## Deployment

### No Database Changes Required
- Uses existing user and reaction data
- No migrations needed

### Backward Compatible
- Only changes display format
- All existing functionality preserved

### Deploy Steps
```bash
git add bot/handlers/comment_handlers.py
git commit -m "Add commenter stats display with emoji indicators"
git push
```

## Testing Checklist

- [ ] View comments from new user (0 reactions)
- [ ] View comments from user with low acceptance (< 30%)
- [ ] View comments from user with neutral acceptance (30-50%)
- [ ] View comments from user with high acceptance (> 50%)
- [ ] Verify impact points display correctly
- [ ] Verify emojis change based on acceptance score
- [ ] Check formatting looks good on mobile

## Future Enhancements

Possible additions:
- Rank badges (Bronze/Silver/Gold) based on impact points
- Trending indicator for users gaining acceptance quickly
- Leaderboard of top contributors
- Achievement system for milestones
