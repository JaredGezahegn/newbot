"""
Comment service for managing comments and reactions.
"""
from django.db import transaction
from django.core.paginator import Paginator
from bot.models import Comment, Reaction, User, Confession


def create_comment(user, confession, text, parent_comment=None, bot_instance=None):
    """
    Create a new comment on a confession or reply to another comment.
    
    Args:
        user: User instance
        confession: Confession instance
        text: Comment text (max 1000 characters)
        parent_comment: Optional parent Comment instance for replies
        bot_instance: Optional TeleBot instance to update channel message button
    
    Returns:
        Comment: The created comment
    
    Raises:
        ValueError: If text exceeds 1000 characters
    """
    if len(text) > 1000:
        raise ValueError(f"Comment text exceeds maximum length of 1000 characters (current: {len(text)})")
    
    with transaction.atomic():
        comment = Comment.objects.create(
            confession=confession,
            user=user,
            parent_comment=parent_comment,
            text=text
        )
        
        # Increment user's comment count
        user.total_comments += 1
        user.save(update_fields=['total_comments'])
        
        # Update channel message button with new comment count
        if bot_instance and confession.channel_message_id:
            update_channel_button(confession, bot_instance)
    
    return comment


def get_comments(confession, page=1, page_size=10):
    """
    Get paginated comments for a confession.
    
    Args:
        confession: Confession instance
        page: Page number (default: 1)
        page_size: Number of comments per page (default: 10)
    
    Returns:
        dict: Dictionary containing:
            - comments: List of Comment instances
            - has_next: Boolean indicating if there are more pages
            - has_previous: Boolean indicating if there are previous pages
            - total_pages: Total number of pages
            - current_page: Current page number
    """
    # Get top-level comments (no parent) for this confession
    comments_queryset = Comment.objects.filter(
        confession=confession,
        parent_comment=None
    ).select_related('user').prefetch_related('replies').order_by('-created_at')
    
    paginator = Paginator(comments_queryset, page_size)
    page_obj = paginator.get_page(page)
    
    return {
        'comments': list(page_obj.object_list),
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'total_pages': paginator.num_pages,
        'current_page': page_obj.number,
    }


def add_reaction(user, comment, reaction_type):
    """
    Add or update a reaction to a comment.
    
    Rules:
    - Like and Dislike are mutually exclusive (toggle each other)
    - Report is independent (can report AND like/dislike)
    
    Args:
        user: User instance
        comment: Comment instance
        reaction_type: String ('like', 'dislike', or 'report')
    
    Returns:
        Reaction: The created or updated reaction
    
    Raises:
        ValueError: If reaction_type is invalid
    """
    valid_reactions = ['like', 'dislike', 'report']
    if reaction_type not in valid_reactions:
        raise ValueError(f"Invalid reaction type: {reaction_type}. Must be one of {valid_reactions}")
    
    with transaction.atomic():
        if reaction_type in ['like', 'dislike']:
            # Like/Dislike logic: mutually exclusive
            # Check if user already has this exact reaction
            existing_same = Reaction.objects.filter(
                comment=comment, 
                user=user, 
                reaction_type=reaction_type
            ).first()
            
            if existing_same:
                # Already has this reaction, do nothing
                return existing_same
            
            # Check for opposite reaction (like vs dislike)
            opposite_type = 'dislike' if reaction_type == 'like' else 'like'
            existing_opposite = Reaction.objects.filter(
                comment=comment,
                user=user,
                reaction_type=opposite_type
            ).first()
            
            if existing_opposite:
                # Remove opposite reaction
                if opposite_type == 'like':
                    comment.like_count = max(0, comment.like_count - 1)
                else:
                    comment.dislike_count = max(0, comment.dislike_count - 1)
                existing_opposite.delete()
            
            # Create new reaction
            reaction = Reaction.objects.create(
                comment=comment,
                user=user,
                reaction_type=reaction_type
            )
            
            # Increment count
            if reaction_type == 'like':
                comment.like_count += 1
            else:
                comment.dislike_count += 1
                
        elif reaction_type == 'report':
            # Report logic: independent of like/dislike
            # Check if already reported
            existing_report = Reaction.objects.filter(
                comment=comment,
                user=user,
                reaction_type='report'
            ).first()
            
            if existing_report:
                # Already reported, do nothing
                return existing_report
            
            # Create new report reaction (doesn't affect like/dislike)
            reaction = Reaction.objects.create(
                comment=comment,
                user=user,
                reaction_type='report'
            )
            
            comment.report_count += 1
        
        comment.save(update_fields=['like_count', 'dislike_count', 'report_count'])
    
    return reaction


def get_comment_reactions(comment):
    """
    Get reaction counts for a comment.
    
    Args:
        comment: Comment instance
    
    Returns:
        dict: Dictionary containing reaction counts:
            - likes: Number of likes
            - dislikes: Number of dislikes
            - reports: Number of reports
    """
    return {
        'likes': comment.like_count,
        'dislikes': comment.dislike_count,
        'reports': comment.report_count,
    }



def update_channel_button(confession, bot_instance):
    """
    Update the "View / Add Comments" button on the channel message with current comment count.
    
    Args:
        confession: Confession instance
        bot_instance: TeleBot instance
    
    Returns:
        bool: True if updated successfully, False otherwise
    """
    from django.conf import settings
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    if not confession.channel_message_id:
        return False
    
    channel_id = getattr(settings, 'CHANNEL_ID', None)
    if not channel_id:
        return False
    
    try:
        # Get bot username from settings
        bot_username = getattr(settings, 'BOT_USERNAME', 'your_bot')
        
        # Get current comment count
        comment_count = confession.comments.count()
        
        # Create updated keyboard
        keyboard = InlineKeyboardMarkup()
        button_text = f"💬 View / Add Comments ({comment_count})"
        keyboard.add(InlineKeyboardButton(
            button_text,
            url=f"https://t.me/{bot_username}?start=comments_{confession.id}"
        ))
        
        # Update the message's reply markup (button only)
        bot_instance.edit_message_reply_markup(
            chat_id=channel_id,
            message_id=confession.channel_message_id,
            reply_markup=keyboard
        )
        
        return True
    except Exception as e:
        # Log error but don't fail the comment creation
        print(f"Error updating channel button: {e}")
        return False
