# Comment Layout Update - One Comment Per Message

## Summary
Implemented a new comment display system where each comment is sent as a **separate message** with its own inline keyboard directly below it. This solves the Telegram API limitation of only allowing one inline keyboard per message.

## Changes Made

### 1. Updated `handle_view_comments()` Function
**Location**: `bot/bot.py` line ~1486

**New Behavior**:
1. When user clicks "View Comments" button:
   - Edits the main confession post to show "💬 Comments below ↓"
   - Adds "➕ Add Comment" button to the main post
   - Sends each comment as a **separate message**
   - Each comment message has its own inline keyboard with:
     - `[👍 N]` - Like button with count
     - `[👎 N]` - Dislike button with count
     - `[💬 Reply]` - Reply button
   - If there are more than 10 comments, shows pagination at the bottom

### 2. Updated `handle_comments_pagination()` Function
**Location**: `bot/bot.py` line ~1601

**New Behavior**:
1. When user clicks "Next Page" button:
   - Deletes the pagination message
   - Sends the next 10 comments as separate messages
   - Each comment has its own inline keyboard
   - Shows new pagination button if more comments exist

## User Flow

### Initial State
```
[Main Post Message]
"Student address"
[Add Comment] [View Comments (2)]
```

### After Clicking "View Comments"
```
[Main Post Message - EDITED]
"Student address"

💬 Comments below ↓
[➕ Add Comment]

[Comment Message 1]
Comment #14 by Anonymous
"Out UK k8"
[👍 0] [👎 0] [💬 Reply]

[Comment Message 2]
Comment #12 by Anonymous
"ur comment below. You c"
[👍 2] [👎 1] [💬 Reply]
```

### With Pagination (>10 comments)
```
[Main Post]
...

[Comment 1]
...
[👍 0] [👎 0] [💬 Reply]

[Comment 2]
...
[👍 2] [👎 1] [💬 Reply]

...

[Pagination Message]
📄 Showing page 1 of 3
[Next Page ➡️]
```

## Benefits

1. ✅ **Buttons directly under each comment** - Each comment has its own reaction buttons
2. ✅ **Clean layout** - No confusion about which buttons belong to which comment
3. ✅ **Scalable** - Works with any number of comments
4. ✅ **Respects Telegram API** - Works within Telegram's one-keyboard-per-message limitation
5. ✅ **Better UX** - Users can react to comments individually without scrolling

## Technical Details

- **Page size**: 10 comments per page
- **Anonymity**: Respects user's anonymous mode setting
- **Error handling**: Graceful fallbacks for edit failures
- **Callback data format**: 
  - View comments: `view_comments_{confession_id}`
  - Pagination: `comments_page_{confession_id}_{page_number}`
  - Like: `like_comment_{comment_id}`
  - Dislike: `dislike_comment_{comment_id}`
  - Reply: `reply_comment_{comment_id}`

## Files Modified

- `bot/bot.py` - Updated `handle_view_comments()` and `handle_comments_pagination()`

## Testing Checklist

- [ ] Click "View Comments" on a confession with 0 comments
- [ ] Click "View Comments" on a confession with 1-10 comments
- [ ] Click "View Comments" on a confession with >10 comments
- [ ] Click "Next Page" to load more comments
- [ ] Click like/dislike buttons on individual comments
- [ ] Verify buttons update only for the specific comment
- [ ] Test with anonymous and non-anonymous commenters
- [ ] Test "Add Comment" button from main post

## Deployment

Deploy to Vercel and test in the Telegram bot to verify the new layout works as expected.
