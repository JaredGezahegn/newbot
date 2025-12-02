#!/usr/bin/env python3
"""Add comment ID labels to buttons and move Add Comment to top"""

with open('bot/bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Pattern 1: Fix deep link handler - add comment ID to buttons and move Add Comment to top
old_deep = """            # Create inline keyboard with action buttons
            inline_keyboard = InlineKeyboardMarkup()
            
            # Add like/dislike/report buttons for EACH comment
            for comment in comments_data['comments']:
                inline_keyboard.row(
                    InlineKeyboardButton(f"👍 {comment.like_count}", callback_data=f"like_comment_{comment.id}"),
                    InlineKeyboardButton(f"⚠️ Report", callback_data=f"report_comment_{comment.id}"),
                    InlineKeyboardButton(f"👎 {comment.dislike_count}", callback_data=f"dislike_comment_{comment.id}"),
                    InlineKeyboardButton(f"💬 Reply", callback_data=f"reply_comment_{comment.id}")
                )
            
            # Add comment button
            inline_keyboard.row(
                InlineKeyboardButton("➕ Add Comment", callback_data=f"add_comment_{confession_id}")
            )"""

new_deep = """            # Create inline keyboard with action buttons
            inline_keyboard = InlineKeyboardMarkup()
            
            # Add comment button at the top
            inline_keyboard.row(
                InlineKeyboardButton("➕ Add Comment", callback_data=f"add_comment_{confession_id}")
            )
            
            # Add like/dislike/report buttons for EACH comment with comment ID label
            for comment in comments_data['comments']:
                inline_keyboard.row(
                    InlineKeyboardButton(f"#{comment.id} 👍 {comment.like_count}", callback_data=f"like_comment_{comment.id}"),
                    InlineKeyboardButton(f"#{comment.id} ⚠️", callback_data=f"report_comment_{comment.id}"),
                    InlineKeyboardButton(f"#{comment.id} 👎 {comment.dislike_count}", callback_data=f"dislike_comment_{comment.id}"),
                    InlineKeyboardButton(f"#{comment.id} 💬", callback_data=f"reply_comment_{comment.id}")
                )"""

content = content.replace(old_deep, new_deep)

# Pattern 2: Fix handle_view_comments - same changes
old_view = """        # Create inline keyboard with action buttons
        keyboard = InlineKeyboardMarkup()
        
        # Add like/dislike/report buttons for EACH comment
        for comment in comments_data['comments']:
            keyboard.row(
                InlineKeyboardButton(f"👍 {comment.like_count}", callback_data=f"like_comment_{comment.id}"),
                InlineKeyboardButton(f"⚠️ Report", callback_data=f"report_comment_{comment.id}"),
                InlineKeyboardButton(f"👎 {comment.dislike_count}", callback_data=f"dislike_comment_{comment.id}"),
                InlineKeyboardButton(f"💬 Reply", callback_data=f"reply_comment_{comment.id}")
            )
        
        # Add pagination buttons if needed
        if comments_data['total_pages'] > 1:
            nav_buttons = []
            if comments_data['has_previous']:
                nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"comments_page_{confession_id}_{comments_data['current_page'] - 1}"))
            if comments_data['has_next']:
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"comments_page_{confession_id}_{comments_data['current_page'] + 1}"))
            if nav_buttons:
                keyboard.row(*nav_buttons)
        
        # Add comment button
        keyboard.row(
            InlineKeyboardButton("➕ Add Comment", callback_data=f"add_comment_{confession_id}")
        )"""

new_view = """        # Create inline keyboard with action buttons
        keyboard = InlineKeyboardMarkup()
        
        # Add comment button at the top
        keyboard.row(
            InlineKeyboardButton("➕ Add Comment", callback_data=f"add_comment_{confession_id}")
        )
        
        # Add like/dislike/report buttons for EACH comment with comment ID label
        for comment in comments_data['comments']:
            keyboard.row(
                InlineKeyboardButton(f"#{comment.id} 👍 {comment.like_count}", callback_data=f"like_comment_{comment.id}"),
                InlineKeyboardButton(f"#{comment.id} ⚠️", callback_data=f"report_comment_{comment.id}"),
                InlineKeyboardButton(f"#{comment.id} 👎 {comment.dislike_count}", callback_data=f"dislike_comment_{comment.id}"),
                InlineKeyboardButton(f"#{comment.id} 💬", callback_data=f"reply_comment_{comment.id}")
            )
        
        # Add pagination buttons if needed
        if comments_data['total_pages'] > 1:
            nav_buttons = []
            if comments_data['has_previous']:
                nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"comments_page_{confession_id}_{comments_data['current_page'] - 1}"))
            if comments_data['has_next']:
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"comments_page_{confession_id}_{comments_data['current_page'] + 1}"))
            if nav_buttons:
                keyboard.row(*nav_buttons)"""

content = content.replace(old_view, new_view)

# Pattern 3: Fix pagination handler
old_page = """        # Create inline keyboard with action buttons
        keyboard = InlineKeyboardMarkup()
        
        # Add like/dislike/report buttons for EACH comment
        for comment in comments_data['comments']:
            keyboard.row(
                InlineKeyboardButton(f"👍 {comment.like_count}", callback_data=f"like_comment_{comment.id}"),
                InlineKeyboardButton(f"⚠️ Report", callback_data=f"report_comment_{comment.id}"),
                InlineKeyboardButton(f"👎 {comment.dislike_count}", callback_data=f"dislike_comment_{comment.id}"),
                InlineKeyboardButton(f"💬 Reply", callback_data=f"reply_comment_{comment.id}")
            )
        
        # Add navigation buttons
        nav_buttons = []
        if comments_data['has_previous']:
            nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"comments_page_{confession_id}_{comments_data['current_page'] - 1}"))
        if comments_data['has_next']:
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"comments_page_{confession_id}_{comments_data['current_page'] + 1}"))
        if nav_buttons:
            keyboard.row(*nav_buttons)
        
        # Add comment button
        keyboard.row(
            InlineKeyboardButton("➕ Add Comment", callback_data=f"add_comment_{confession_id}")
        )"""

new_page = """        # Create inline keyboard with action buttons
        keyboard = InlineKeyboardMarkup()
        
        # Add comment button at the top
        keyboard.row(
            InlineKeyboardButton("➕ Add Comment", callback_data=f"add_comment_{confession_id}")
        )
        
        # Add like/dislike/report buttons for EACH comment with comment ID label
        for comment in comments_data['comments']:
            keyboard.row(
                InlineKeyboardButton(f"#{comment.id} 👍 {comment.like_count}", callback_data=f"like_comment_{comment.id}"),
                InlineKeyboardButton(f"#{comment.id} ⚠️", callback_data=f"report_comment_{comment.id}"),
                InlineKeyboardButton(f"#{comment.id} 👎 {comment.dislike_count}", callback_data=f"dislike_comment_{comment.id}"),
                InlineKeyboardButton(f"#{comment.id} 💬", callback_data=f"reply_comment_{comment.id}")
            )
        
        # Add navigation buttons
        nav_buttons = []
        if comments_data['has_previous']:
            nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"comments_page_{confession_id}_{comments_data['current_page'] - 1}"))
        if comments_data['has_next']:
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"comments_page_{confession_id}_{comments_data['current_page'] + 1}"))
        if nav_buttons:
            keyboard.row(*nav_buttons)"""

content = content.replace(old_page, new_page)

with open('bot/bot.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed button order and labels!")
