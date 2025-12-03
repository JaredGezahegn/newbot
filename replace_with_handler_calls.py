#!/usr/bin/env python3
"""
Replace old comment handler implementations with calls to the new handlers module
"""

with open('bot/bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the old handle_view_comments function body
old_view_comments = '''@bot.callback_query_handler(func=lambda call: call.data.startswith('view_comments_'))
def handle_view_comments(call: CallbackQuery):
    """Handle 'View / Add Comments' button - sends each comment as separate message"""
    try:
        telegram_id = call.from_user.id
        
        # Check if user is registered
        user, error = get_user_or_error(telegram_id)
        if error:
            bot.answer_callback_query(call.id, "❌ You need to /register first.")
            return
        
        # Extract and validate confession ID from callback data
        try:
            confession_id = int(call.data.split('_')[2])
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "❌ Invalid confession ID in callback.")
            return
        
        # Get the confession
        confession, error = get_confession_or_error(confession_id)
        if error:
            bot.answer_callback_query(call.id, "❌ Confession not found.")
            return
        
        # Get comments
        from bot.services.comment_service import get_comments
        comments_data = get_comments(confession, page=1, page_size=10)
        
        # Edit the main post to show "Comments below"
        confession_text = confession.text[:500] if len(confession.text) > 500 else confession.text
        
        main_post_text = f"{confession_text}\\n\\n"
        
        if comments_data['comments']:
            main_post_text += f"💬 <b>Comments below ↓</b>"
        else:
            main_post_text += "💬 <b>No comments yet</b>"
        
        # Create keyboard for main post with Add Comment button
        main_keyboard = InlineKeyboardMarkup()
        main_keyboard.row(
            InlineKeyboardButton("➕ Add Comment", callback_data=f"add_comment_{confession_id}")
        )
        
        # Edit the original message
        try:
            bot.edit_message_text(
                main_post_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='HTML',
                reply_markup=main_keyboard
            )
        except Exception as e:
            logger.warning(f"Could not edit main post: {e}")
        
        # Send each comment as a separate message with its own buttons
        for comment in comments_data['comments']:
            # Build comment text following guideline format
            # Author
            comment_text = "<b>Anonymous</b>\\n"
            # Comment text (truncated to 400 chars)
            comment_snippet = comment.text[:400]
            comment_text += f"{comment_snippet}\\n"
            # Timestamp
            from django.utils import timezone
            timestamp = comment.created_at.strftime("%b %d, %Y • %I:%M %p")
            comment_text += f"🕒 {timestamp}"
            
            # Create inline keyboard for this comment
            comment_keyboard = InlineKeyboardMarkup()
            # Row 1: Reactions
            comment_keyboard.row(
                InlineKeyboardButton(f"👍 {comment.like_count}", callback_data=f"like_comment_{comment.id}"),
                InlineKeyboardButton(f"⚠️ {comment.report_count}", callback_data=f"report_comment_{comment.id}"),
                InlineKeyboardButton(f"👎 {comment.dislike_count}", callback_data=f"dislike_comment_{comment.id}")
            )
            # Row 2: Reply
            comment_keyboard.row(
                InlineKeyboardButton("↩️ Reply", callback_data=f"reply_comment_{comment.id}")
            )
            
            # Send comment as separate message
            bot.send_message(
                call.message.chat.id,
                comment_text,
                parse_mode='HTML',
                reply_markup=comment_keyboard
            )
        
        # If there are more comments, show pagination info
        if comments_data['total_pages'] > 1:
            pagination_text = f"📄 Showing page 1 of {comments_data['total_pages']}"
            pagination_keyboard = InlineKeyboardMarkup()
            
            if comments_data['has_next']:
                pagination_keyboard.row(
                    InlineKeyboardButton("Next Page ➡️", callback_data=f"comments_page_{confession_id}_2")
                )
            
            bot.send_message(
                call.message.chat.id,
                pagination_text,
                reply_markup=pagination_keyboard
            )
        
        bot.answer_callback_query(call.id, "✅ Comments loaded")
        
    except DatabaseError as e:
        error_text = handle_database_error(e, "viewing comments")
        bot.answer_callback_query(call.id, "❌ Database error occurred.")
        logger.error(f"Database error viewing comments: {e}")
    except Exception as e:
        error_text = handle_generic_error(e, "viewing comments")
        bot.answer_callback_query(call.id, "❌ An error occurred.")
        logger.error(f"Error in handle_view_comments: {e}")'''

new_view_comments = '''@bot.callback_query_handler(func=lambda call: call.data.startswith('view_comments_'))
def handle_view_comments_wrapper(call: CallbackQuery):
    """Handle 'View / Add Comments' button - delegates to handlers module"""
    from bot.handlers.comment_handlers import handle_view_comments
    handle_view_comments(bot, call)'''

content = content.replace(old_view_comments, new_view_comments)

with open('bot/bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Replaced old handle_view_comments with wrapper that calls the new handler!")
