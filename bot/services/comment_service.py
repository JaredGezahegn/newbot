"""
Comment service for managing comments and reactions.
"""
from django.db import transaction
from django.core.paginator import Paginator
from bot.models import Comment, Reaction, User, Confession


def create_comment(user, confession, text, parent_comment=None):
    """
    Create a new comment on a confession or reply to another comment.
    
    Args:
        user: User instance
        confession: Confession instance
        text: Comment text (max 1000 characters)
        parent_comment: Optional parent Comment instance for replies
    
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
    Enforces one reaction per user per comment.
    
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
        # Get existing reaction if any
        existing_reaction = Reaction.objects.filter(comment=comment, user=user).first()
        
        if existing_reaction:
            # Update existing reaction
            old_type = existing_reaction.reaction_type
            
            # Decrement old reaction count
            if old_type == 'like':
                comment.like_count = max(0, comment.like_count - 1)
            elif old_type == 'dislike':
                comment.dislike_count = max(0, comment.dislike_count - 1)
            elif old_type == 'report':
                comment.report_count = max(0, comment.report_count - 1)
            
            # Update reaction type
            existing_reaction.reaction_type = reaction_type
            existing_reaction.save(update_fields=['reaction_type'])
            reaction = existing_reaction
        else:
            # Create new reaction
            reaction = Reaction.objects.create(
                comment=comment,
                user=user,
                reaction_type=reaction_type
            )
        
        # Increment new reaction count
        if reaction_type == 'like':
            comment.like_count += 1
        elif reaction_type == 'dislike':
            comment.dislike_count += 1
        elif reaction_type == 'report':
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
