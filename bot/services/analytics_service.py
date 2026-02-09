"""
Analytics service for tracking user interactions and calculating monthly active users.
This is a minimal implementation for the monthly users count feature.
"""

from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
from bot.models import User
import logging

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for handling user analytics and monthly active user calculations."""
    
    CACHE_KEY_MAU = 'monthly_active_users_count'
    CACHE_TIMEOUT = 3600  # 1 hour
    
    # Display configuration defaults
    DEFAULT_DISPLAY_CONFIG = {
        'format': 'abbreviated',  # 'abbreviated' (1.2K) or 'full' (1200)
        'position': 'inline',  # 'inline' or 'separate_line'
        'label': 'monthly active users',  # Label text to display
        'show_label': True,  # Whether to show the label
        'hide_low_counts': False,  # Hide counts under 10
        'low_count_threshold': 10  # Threshold for low counts
    }
    
    @staticmethod
    def get_monthly_active_users_count():
        """
        Get the count of monthly active users based on UserInteraction records.
        
        Returns the number of unique users who have interacted with the bot
        in the last 30 days. Uses caching with 1-hour timeout for efficiency.
        
        Implements graceful degradation:
        - Falls back to cached value if database fails
        - Falls back to database if cache fails
        - Returns 0 if both fail
        
        Returns:
            int: Number of unique active users in the last 30 days
        """
        # Check cache first (with error handling)
        cached_count = None
        try:
            cached_count = cache.get(AnalyticsService.CACHE_KEY_MAU)
            if cached_count is not None:
                logger.info(f"Returning cached MAU count: {cached_count}")
                return cached_count
        except Exception as e:
            logger.warning(f"Cache get failed, falling back to database: {e}")
        
        try:
            from bot.models import UserInteraction
            
            # Calculate 30 days ago
            thirty_days_ago = timezone.now() - timedelta(days=30)
            
            # Get count of unique users who have interactions in the last 30 days
            mau_count = UserInteraction.objects.filter(
                timestamp__gte=thirty_days_ago
            ).values('user').distinct().count()
            
            # Try to cache the result for 1 hour (with error handling)
            try:
                cache.set(AnalyticsService.CACHE_KEY_MAU, mau_count, AnalyticsService.CACHE_TIMEOUT)
            except Exception as cache_error:
                logger.warning(f"Cache set failed: {cache_error}")
            
            logger.info(f"Calculated MAU count: {mau_count}")
            return mau_count
            
        except Exception as e:
            logger.error(f"Error calculating monthly active users: {e}", exc_info=True)
            # If we have a cached value from earlier, return it
            if cached_count is not None:
                logger.info(f"Returning stale cached value due to database error: {cached_count}")
                return cached_count
            # Return a fallback count
            return 0
    
    @staticmethod
    def get_total_registered_users_count():
        """
        Get the total count of all registered users.
        
        Returns the total number of users in the database.
        Uses caching with 1-hour timeout for efficiency.
        
        Returns:
            int: Total number of registered users
        """
        cache_key = 'total_registered_users_count'
        
        # Check cache first
        cached_count = None
        try:
            cached_count = cache.get(cache_key)
            if cached_count is not None:
                logger.info(f"Returning cached total users count: {cached_count}")
                return cached_count
        except Exception as e:
            logger.warning(f"Cache get failed, falling back to database: {e}")
        
        try:
            # Get total count of all users
            total_count = User.objects.count()
            
            # Try to cache the result for 1 hour
            try:
                cache.set(cache_key, total_count, AnalyticsService.CACHE_TIMEOUT)
            except Exception as cache_error:
                logger.warning(f"Cache set failed: {cache_error}")
            
            logger.info(f"Calculated total users count: {total_count}")
            return total_count
            
        except Exception as e:
            logger.error(f"Error calculating total registered users: {e}", exc_info=True)
            # If we have a cached value from earlier, return it
            if cached_count is not None:
                logger.info(f"Returning stale cached value due to database error: {cached_count}")
                return cached_count
            # Return a fallback count
            return 0
    
    @staticmethod
    def format_user_count(count):
        """
        Format user count for display.
        
        Args:
            count (int): The user count to format
            
        Returns:
            str: Formatted count string (e.g., "1.2K", "5.3M")
        """
        if count < 1000:
            return str(count)
        elif count < 1000000:
            return f"{count/1000:.1f}K"
        else:
            return f"{count/1000000:.1f}M"
    
    @staticmethod
    def format_display(count, config=None):
        """
        Format the monthly active users count for display with configuration options.
        
        Args:
            count (int): The user count to format
            config (dict, optional): Display configuration options. If None, uses defaults.
                - format: 'abbreviated' (1.2K) or 'full' (1200)
                - position: 'inline' or 'separate_line'
                - label: Label text to display
                - show_label: Whether to show the label
                - hide_low_counts: Hide counts under threshold
                - low_count_threshold: Threshold for low counts
        
        Returns:
            str: Formatted display string, or empty string if hidden
        """
        # Use default config if none provided
        if config is None:
            config = AnalyticsService.DEFAULT_DISPLAY_CONFIG.copy()
        else:
            # Merge with defaults for any missing keys
            merged_config = AnalyticsService.DEFAULT_DISPLAY_CONFIG.copy()
            merged_config.update(config)
            config = merged_config
        
        # Handle low count hiding
        if config.get('hide_low_counts', False):
            threshold = config.get('low_count_threshold', 10)
            if count < threshold:
                return ''
        
        # Format the count based on format setting
        if config.get('format') == 'full':
            formatted_count = str(count)
        else:  # abbreviated
            formatted_count = AnalyticsService.format_user_count(count)
        
        # Build the display string
        if config.get('show_label', True):
            label = config.get('label', 'monthly active users')
            if config.get('position') == 'separate_line':
                return f"{label}\n{formatted_count}"
            else:  # inline
                return f"{formatted_count} {label}"
        else:
            return formatted_count
    
    @staticmethod
    def track_user_interaction(user, interaction_type, max_retries=2):
        """
        Track a user interaction by creating a UserInteraction record.
        
        Implements retry logic with exponential backoff for transient failures.
        
        Args:
            user: User instance
            interaction_type (str): Type of interaction (message, command, button_click, etc.)
            max_retries (int): Maximum number of retry attempts (default: 2)
        
        Returns:
            UserInteraction: The created interaction record, or None if failed
        """
        from bot.models import UserInteraction
        import time
        
        # Validate inputs
        if user is None:
            logger.warning("Cannot track interaction: user is None")
            return None
        
        if not interaction_type:
            logger.warning("Cannot track interaction: interaction_type is empty")
            return None
        
        # Attempt to create the interaction with retry logic
        for attempt in range(max_retries + 1):
            try:
                interaction = UserInteraction.objects.create(
                    user=user,
                    interaction_type=interaction_type
                )
                logger.info(f"User interaction tracked: {user.id} - {interaction_type}")
                return interaction
            except Exception as e:
                logger.error(f"Error tracking user interaction (attempt {attempt + 1}/{max_retries + 1}): {e}", exc_info=True)
                
                # If not the last attempt, wait before retrying (exponential backoff)
                if attempt < max_retries:
                    wait_time = (2 ** attempt) * 0.1  # 0.1s, 0.2s, 0.4s, etc.
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    # All retries exhausted
                    logger.error(f"Failed to track interaction after {max_retries + 1} attempts")
                    return None
    
    @staticmethod
    def clear_cache():
        """
        Clear the MAU cache to force recalculation.
        
        Handles cache failures gracefully without raising exceptions.
        """
        try:
            cache.delete(AnalyticsService.CACHE_KEY_MAU)
            logger.info("MAU cache cleared")
        except Exception as e:
            logger.warning(f"Failed to clear MAU cache: {e}")
    
    @staticmethod
    def get_admin_analytics_report():
        """
        Generate an admin analytics report with aggregate data only.
        
        This method provides insights into bot usage without exposing individual
        user identities, ensuring privacy compliance.
        
        Returns:
            dict: Analytics report containing:
                - total_interactions: Total number of interactions recorded
                - monthly_active_users: Number of unique users in last 30 days
                - interaction_types_breakdown: Count of each interaction type
                - daily_active_users: Number of unique users in last 24 hours
                - weekly_active_users: Number of unique users in last 7 days
        """
        from bot.models import UserInteraction
        from datetime import timedelta
        from django.db.models import Count
        
        try:
            now = timezone.now()
            
            # Calculate time boundaries
            one_day_ago = now - timedelta(days=1)
            seven_days_ago = now - timedelta(days=7)
            thirty_days_ago = now - timedelta(days=30)
            
            # Total interactions (all time)
            total_interactions = UserInteraction.objects.count()
            
            # Monthly active users (already cached)
            monthly_active_users = AnalyticsService.get_monthly_active_users_count()
            
            # Daily active users
            daily_active_users = UserInteraction.objects.filter(
                timestamp__gte=one_day_ago
            ).values('user').distinct().count()
            
            # Weekly active users
            weekly_active_users = UserInteraction.objects.filter(
                timestamp__gte=seven_days_ago
            ).values('user').distinct().count()
            
            # Interaction types breakdown (aggregate counts only, no user info)
            interaction_types = UserInteraction.objects.values('interaction_type').annotate(
                count=Count('id')
            ).order_by('-count')
            
            interaction_types_breakdown = {
                item['interaction_type']: item['count']
                for item in interaction_types
            }
            
            # Build the report with only aggregate data
            report = {
                'total_interactions': total_interactions,
                'monthly_active_users': monthly_active_users,
                'daily_active_users': daily_active_users,
                'weekly_active_users': weekly_active_users,
                'interaction_types_breakdown': interaction_types_breakdown,
            }
            
            logger.info("Admin analytics report generated successfully")
            return report
            
        except Exception as e:
            logger.error(f"Error generating admin analytics report: {e}", exc_info=True)
            # Return empty report on error
            return {
                'total_interactions': 0,
                'monthly_active_users': 0,
                'daily_active_users': 0,
                'weekly_active_users': 0,
                'interaction_types_breakdown': {},
            }
    
    @staticmethod
    def cleanup_old_interactions(days=90):
        """
        Clean up interaction data older than the specified number of days.
        
        This implements data retention policies for privacy compliance.
        Only keeps interaction data for the specified retention period.
        
        Args:
            days (int): Number of days to retain data (default: 90)
            
        Returns:
            int: Number of interactions deleted
        """
        from bot.models import UserInteraction
        from datetime import timedelta
        
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Delete interactions older than the retention period
            deleted_count, _ = UserInteraction.objects.filter(
                timestamp__lt=cutoff_date
            ).delete()
            
            # Clear cache after cleanup to ensure fresh calculations
            AnalyticsService.clear_cache()
            
            logger.info(f"Cleaned up {deleted_count} old interactions (retention: {days} days)")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old interactions: {e}", exc_info=True)
            return 0
    
    @staticmethod
    def update_bot_description_with_count(bot_instance=None, config=None):
        """
        Update the bot's description to include the monthly active users count.
        
        This method updates the bot's description via the Telegram Bot API to display
        the current monthly active users count. It handles rate limiting, API errors,
        and provides fallback options.
        
        Args:
            bot_instance: TeleBot instance to use for API calls. If None, creates a new instance.
            config (dict, optional): Configuration options:
                - enabled: Whether to enable automatic description updates (default: False)
                - description_template: Template string with {count} placeholder
                - update_interval: Minimum seconds between updates (default: 3600)
                - retry_attempts: Number of retry attempts on failure (default: 3)
                - retry_delay: Seconds to wait between retries (default: 60)
        
        Returns:
            dict: Result dictionary with:
                - success (bool): Whether the update succeeded
                - message (str): Status message
                - count (int): The MAU count that was used
                - error (str, optional): Error message if failed
        """
        import time
        from django.conf import settings
        
        # Default configuration
        default_config = {
            'enabled': False,
            'description_template': 'Anonymous Confession Bot - {count} monthly active users',
            'update_interval': 3600,  # 1 hour
            'retry_attempts': 3,
            'retry_delay': 60,  # 1 minute
        }
        
        # Merge with provided config
        if config is None:
            config = default_config
        else:
            merged_config = default_config.copy()
            merged_config.update(config)
            config = merged_config
        
        # Check if updates are enabled
        if not config.get('enabled', False):
            return {
                'success': False,
                'message': 'Bot description updates are disabled in configuration',
                'count': 0
            }
        
        # Check rate limiting using cache
        last_update_key = 'bot_description_last_update'
        last_update_time = cache.get(last_update_key)
        
        if last_update_time is not None:
            time_since_update = time.time() - last_update_time
            if time_since_update < config['update_interval']:
                return {
                    'success': False,
                    'message': f'Rate limited: {int(config["update_interval"] - time_since_update)}s until next update allowed',
                    'count': 0
                }
        
        # Get the user count based on config
        try:
            count_type = config.get('count_type', 'monthly_active_users')
            
            if count_type == 'total_users':
                user_count = AnalyticsService.get_total_registered_users_count()
            else:  # default to monthly_active_users
                user_count = AnalyticsService.get_monthly_active_users_count()
            
            formatted_count = AnalyticsService.format_user_count(user_count)
        except Exception as e:
            logger.error(f"Error getting user count for description update: {e}", exc_info=True)
            return {
                'success': False,
                'message': 'Failed to retrieve user count',
                'count': 0,
                'error': str(e)
            }
        
        # Format the description using the template
        try:
            description = config['description_template'].format(count=formatted_count)
        except KeyError as e:
            logger.error(f"Invalid description template: {e}", exc_info=True)
            return {
                'success': False,
                'message': 'Invalid description template format',
                'count': mau_count,
                'error': str(e)
            }
        
        # Get or create bot instance
        if bot_instance is None:
            try:
                from telebot import TeleBot
                bot_instance = TeleBot(settings.BOT_TOKEN, parse_mode="HTML", threaded=False)
            except Exception as e:
                logger.error(f"Error creating bot instance: {e}", exc_info=True)
                return {
                    'success': False,
                    'message': 'Failed to create bot instance',
                    'count': mau_count,
                    'error': str(e)
                }
        
        # Attempt to update the bot description with retry logic
        retry_attempts = config.get('retry_attempts', 3)
        retry_delay = config.get('retry_delay', 60)
        
        for attempt in range(retry_attempts):
            try:
                # Update bot description using Telegram Bot API
                # Note: set_my_description is the correct method for bot description
                bot_instance.set_my_description(description)
                
                # Update the last update timestamp
                cache.set(last_update_key, time.time(), timeout=None)
                
                logger.info(f"Successfully updated bot description with MAU count: {formatted_count}")
                return {
                    'success': True,
                    'message': f'Bot description updated successfully with {formatted_count} users',
                    'count': user_count
                }
                
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Attempt {attempt + 1}/{retry_attempts} to update bot description failed: {error_msg}")
                
                # Check for specific error types
                if 'rate limit' in error_msg.lower() or '429' in error_msg:
                    # Rate limited by Telegram API
                    logger.error(f"Telegram API rate limit hit: {error_msg}")
                    return {
                        'success': False,
                        'message': 'Telegram API rate limit exceeded',
                        'count': mau_count,
                        'error': error_msg
                    }
                
                if 'permission' in error_msg.lower() or '403' in error_msg:
                    # Permission error
                    logger.error(f"Permission error updating bot description: {error_msg}")
                    return {
                        'success': False,
                        'message': 'Insufficient permissions to update bot description',
                        'count': mau_count,
                        'error': error_msg
                    }
                
                # If not the last attempt, wait before retrying
                if attempt < retry_attempts - 1:
                    logger.info(f"Waiting {retry_delay}s before retry...")
                    time.sleep(retry_delay)
                else:
                    # Final attempt failed
                    logger.error(f"All {retry_attempts} attempts to update bot description failed")
                    return {
                        'success': False,
                        'message': f'Failed to update bot description after {retry_attempts} attempts',
                        'count': user_count,
                        'error': error_msg
                    }
        
        # Should not reach here, but return failure as fallback
        return {
            'success': False,
            'message': 'Unknown error during bot description update',
            'count': user_count
        }
    
    @staticmethod
    def get_bot_description_config():
        """
        Get the bot description update configuration from Django settings.
        
        Returns:
            dict: Configuration dictionary with default values if not set in settings
        """
        from django.conf import settings
        
        # Try to get configuration from settings
        return getattr(settings, 'BOT_DESCRIPTION_CONFIG', {
            'enabled': False,
            'description_template': 'Anonymous Confession Bot - {count} monthly active users',
            'update_interval': 3600,
            'retry_attempts': 3,
            'retry_delay': 60,
        })