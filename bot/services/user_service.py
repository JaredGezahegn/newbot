"""
User service for managing user registration, settings, and statistics.
"""
from django.db import transaction
from django.db.models import Sum, Q, Count
from bot.models import User, Reaction


def register_user(telegram_id, first_name, username=None):
    """
    Register a new user or return existing user.
    
    Args:
        telegram_id: Telegram user ID
        first_name: User's first name
        username: User's username (optional)
    
    Returns:
        User: The created or existing user
    """
    user, created = User.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={
            'username': username or f'user_{telegram_id}',
            'first_name': first_name or 'User',
            'is_anonymous_mode': True,
            'total_confessions': 0,
            'total_comments': 0,
            'impact_points': 0,
        }
    )
    return user


def toggle_anonymity(user, enabled):
    """
    Toggle anonymity mode for a user.
    
    Args:
        user: User instance
        enabled: Boolean indicating whether to enable anonymity
    
    Returns:
        User: Updated user instance
    """
    user.is_anonymous_mode = enabled
    user.save(update_fields=['is_anonymous_mode'])
    return user


def get_user_stats(user):
    """
    Get comprehensive statistics for a user.
    
    Args:
        user: User instance
    
    Returns:
        dict: Dictionary containing user statistics
    """
    impact_points = calculate_impact_points(user)
    acceptance_score = calculate_acceptance_score(user)
    
    return {
        'total_confessions': user.confessions.filter(status='approved').count(),
        'total_comments': user.comments.count(),
        'impact_points': impact_points,
        'acceptance_score': acceptance_score,
    }


def calculate_impact_points(user):
    """
    Calculate impact points for a user.
    Impact points = approved confessions + comments + positive reactions received
    
    Args:
        user: User instance
    
    Returns:
        int: Total impact points
    """
    approved_confessions = user.confessions.filter(status='approved').count()
    total_comments = user.comments.count()
    
    # Get positive reactions (likes) on user's comments
    positive_reactions = Reaction.objects.filter(
        comment__user=user,
        reaction_type='like'
    ).count()
    
    impact_points = approved_confessions + total_comments + positive_reactions
    
    # Update the cached value
    user.impact_points = impact_points
    user.save(update_fields=['impact_points'])
    
    return impact_points


def calculate_acceptance_score(user):
    """
    Calculate community acceptance score for a user.
    Acceptance score = positive reactions / total reactions (as percentage)
    
    Args:
        user: User instance
    
    Returns:
        float: Acceptance score as percentage (0-100), or 0 if no reactions
    """
    # Get all reactions on user's comments
    reactions = Reaction.objects.filter(comment__user=user)
    
    total_reactions = reactions.count()
    if total_reactions == 0:
        return 0.0
    
    positive_reactions = reactions.filter(reaction_type='like').count()
    
    acceptance_score = (positive_reactions / total_reactions) * 100
    
    return round(acceptance_score, 2)
