# Like/Dislike/Report Feature Implementation

## Summary
Implemented interactive like, dislike, and report buttons for comments with real-time count updates and proper user tracking. Comments are displayed **one at a time** with reaction buttons directly underneath for better UX.

## Changes Made

### 1. One-Comment-at-a-Time Display

**Location**: `bot/bot.py` - `handle_view_comments()` and `handle_comments_pagination()`

Changed from showing multiple comments in a list to showing **one comment at a time** with:
- Full comment text (not truncated)
- Commenter name and username
- Like/dislike/report counts
- Interactive buttons directly under the comment
- Previous/Next navigation buttons

```python
# Show 1 comment at a time instead of 5
comments_data = get_comments(confession, page=1, page_size=1)

# Display format:
# Comment 1 of 5
# By: John (@john123)
# Comment: [full text]
# 👍 5  |  👎 2  |  🚩 0
# [👍 Like] [👎 Dislike] [🚩 Report]
# [⬅️ Previous] [Next ➡️]
# [➕ Add Comment]
```

### 2. Helper Function for View Rebuilding

**Location**: `bot/bot.py` - `rebuild_comment_view()`

Created a centralized function to rebuild the comment view after any reaction:
- Refreshes comment data from database
- Finds the comment's position in the list
- Rebuilds the message with updated counts
- Updates all buttons with current state

```python
def rebuild_comment_view(comment, chat_id, message_id):
    """Rebuild and update the comment view message with current data."""
    # Refresh comment data
    comment.refresh_from_db()
    
    # Find comment position
    all_comments = Comment.objects.filter(
        confession=confession,
        parent_comment=None
    ).order_by('-created_at')
    
    comment_index = list(all_comments.values_list('id', flat=True)).index(comment.id)
    current_page = comment_index + 1
    
    # Rebuild message and keyboard...
```

### 3. Enhanced Like Handler

**Location**: `bot/bot.py` - `handle_like_comment()`

**Features**:
- ✅ Prevents duplicate likes (checks if user already liked)
- ✅ Allows switching from dislike to like
- ✅ Updates message with new counts in real-time using `rebuild_comment_view()`
- ✅ Shows informative message if already liked

**Logic**:
```python
# Check if user already liked
existing_reaction = Reaction.objects.filter(comment=comment, user=user).first()
if existing_reaction and existing_reaction.reaction_type == 'like':
    bot.answer_callback_query(call.id, "ℹ️ You already liked this comment!")
    return

# Add reaction and rebuild view
add_reaction(user, comment, 'like')
rebuild_comment_view(comment, call.message.chat.id, call.message.message_id)
```

### 4. Enhanced Dislike Handler

**Location**: `bot/bot.py` - `handle_dislike_comment()`

**Features**:
- ✅ Prevents duplicate dislikes (checks if user already disliked)
- ✅ Allows switching from like to dislike
- ✅ Updates message with new counts in real-time using `rebuild_comment_view()`
- ✅ Shows informative message if already disliked

### 5. Enhanced Report Handler

**Location**: `bot/bot.py` - `handle_report_comment()`

**Features**:
- ✅ Prevents duplicate reports (checks if user already reported)
- ✅ Allows switching from like/dislike to report
- ✅ Updates message with new counts in real-time using `rebuild_comment_view()`
- ✅ Notifies admins when report threshold (5) is reached
- ✅ Shows informative message if already reported

### 6. Backend Logic (Already Existed)

**Location**: `bot/services/comment_service.py` - `add_reaction()`

The backend already had proper logic:
- ✅ One reaction per user per comment (enforced by database constraint)
- ✅ Allows switching between reaction types
- ✅ Properly updates counts when switching
- ✅ Uses database transactions for consistency

**Database Model**: `bot/models.py` - `Reaction`
```python
class Meta:
    unique_together = ('comment', 'user')  # Ensures one reaction per user
```

## User Experience

### Viewing Comments
1. User clicks "View / Add Comments" button on channel post
2. Bot opens in private chat showing **one comment at a time**
3. Comment is displayed with full text and reaction buttons directly underneath
4. User can navigate between comments using Previous/Next buttons

### Scenario 1: First Time Reaction
1. User views a comment
2. User clicks 👍 Like button
3. Like count increases by 1
4. Message updates instantly to show new count
5. User sees "👍 Liked!" notification

### Scenario 2: Switching Reactions
1. User previously liked a comment (👍 count = 5)
2. User clicks 👎 Dislike button
3. Like count decreases to 4
4. Dislike count increases by 1
5. Message updates instantly to show new counts
6. User sees "👎 Disliked!" notification

### Scenario 3: Duplicate Reaction Attempt
1. User already liked a comment
2. User clicks 👍 Like button again
3. No count changes
4. User sees "ℹ️ You already liked this comment!" notification

### Scenario 4: Reporting
1. User clicks 🚩 Report button
2. Report count increases
3. If report count >= 5, admins are notified
4. User sees "🚩 Comment reported..." notification

### Scenario 5: Navigating Comments
1. User views Comment 1 of 5
2. User clicks "Next ➡️" button
3. Bot shows Comment 2 of 5 with its own reaction buttons
4. User can like/dislike/report this comment independently

## Technical Details

### Database Constraints
- `unique_together = ('comment', 'user')` ensures one reaction per user per comment
- Prevents race conditions with database-level constraint

### Transaction Safety
- All reaction operations use `transaction.atomic()` for consistency
- Counts are updated atomically with reaction changes

### Real-Time Updates
- After each reaction, the message is refreshed with updated counts
- All comments on the current page are re-rendered
- Pagination buttons are preserved

## Testing

The existing property-based tests already cover:
- ✅ Reaction uniqueness per user (Property 8)
- ✅ Comment creation and linking
- ✅ Impact points calculation

## Deployment Notes

1. No database migrations needed (models already exist)
2. No environment variables needed
3. Deploy to Vercel as usual
4. Test with multiple users to verify reaction switching

## Future Enhancements

Potential improvements:
- Show which users liked/disliked (privacy consideration)
- Add reaction history/timeline
- Allow removing reactions (currently switches only)
- Add more reaction types (❤️, 😂, etc.)
