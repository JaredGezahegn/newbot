"""
Unit tests for bot description update functionality
"""
from django.test import TestCase
from unittest.mock import Mock, patch, MagicMock
from bot.services.analytics_service import AnalyticsService
from bot.models import User, UserInteraction
from django.core.cache import cache
import time


class BotDescriptionUpdateTests(TestCase):
    """Tests for bot description update functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear cache before each test
        cache.clear()
        
        # Clear all interactions
        UserInteraction.objects.all().delete()
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    def test_update_disabled_by_default(self):
        """Test that bot description updates are disabled by default"""
        result = AnalyticsService.update_bot_description_with_count()
        
        self.assertFalse(result['success'])
        self.assertIn('disabled', result['message'].lower())
    
    def test_update_with_enabled_config(self):
        """Test bot description update with enabled configuration"""
        # Create a mock bot instance
        mock_bot = Mock()
        mock_bot.set_my_description = Mock()
        
        # Create test user and interaction
        user = User.objects.create(telegram_id=123456, first_name="TestUser")
        UserInteraction.objects.create(user=user, interaction_type='message')
        
        # Configure to enable updates
        config = {
            'enabled': True,
            'description_template': 'Test Bot - {count} users',
            'update_interval': 0,  # No rate limiting for test
            'retry_attempts': 1,
            'retry_delay': 0
        }
        
        # Update description
        result = AnalyticsService.update_bot_description_with_count(
            bot_instance=mock_bot,
            config=config
        )
        
        # Verify success
        self.assertTrue(result['success'])
        self.assertEqual(result['count'], 1)
        
        # Verify bot API was called
        mock_bot.set_my_description.assert_called_once()
        call_args = mock_bot.set_my_description.call_args[0][0]
        self.assertIn('1', call_args)
        self.assertIn('users', call_args)
    
    def test_rate_limiting(self):
        """Test that rate limiting prevents frequent updates"""
        mock_bot = Mock()
        mock_bot.set_my_description = Mock()
        
        config = {
            'enabled': True,
            'description_template': 'Test Bot - {count} users',
            'update_interval': 3600,  # 1 hour
            'retry_attempts': 1,
            'retry_delay': 0
        }
        
        # First update should succeed
        result1 = AnalyticsService.update_bot_description_with_count(
            bot_instance=mock_bot,
            config=config
        )
        self.assertTrue(result1['success'])
        
        # Second update immediately after should be rate limited
        result2 = AnalyticsService.update_bot_description_with_count(
            bot_instance=mock_bot,
            config=config
        )
        self.assertFalse(result2['success'])
        self.assertIn('rate limited', result2['message'].lower())
    
    def test_invalid_template(self):
        """Test handling of invalid description template"""
        mock_bot = Mock()
        
        config = {
            'enabled': True,
            'description_template': 'Test Bot - {invalid_placeholder}',
            'update_interval': 0,
            'retry_attempts': 1,
            'retry_delay': 0
        }
        
        result = AnalyticsService.update_bot_description_with_count(
            bot_instance=mock_bot,
            config=config
        )
        
        self.assertFalse(result['success'])
        self.assertIn('template', result['message'].lower())
    
    def test_telegram_api_error_handling(self):
        """Test handling of Telegram API errors"""
        mock_bot = Mock()
        mock_bot.set_my_description = Mock(side_effect=Exception("API Error"))
        
        config = {
            'enabled': True,
            'description_template': 'Test Bot - {count} users',
            'update_interval': 0,
            'retry_attempts': 2,
            'retry_delay': 0
        }
        
        result = AnalyticsService.update_bot_description_with_count(
            bot_instance=mock_bot,
            config=config
        )
        
        self.assertFalse(result['success'])
        self.assertIn('failed', result['message'].lower())
        self.assertIn('error', result)
    
    def test_rate_limit_error_from_telegram(self):
        """Test handling of Telegram API rate limit errors"""
        mock_bot = Mock()
        mock_bot.set_my_description = Mock(side_effect=Exception("Rate limit exceeded (429)"))
        
        config = {
            'enabled': True,
            'description_template': 'Test Bot - {count} users',
            'update_interval': 0,
            'retry_attempts': 1,
            'retry_delay': 0
        }
        
        result = AnalyticsService.update_bot_description_with_count(
            bot_instance=mock_bot,
            config=config
        )
        
        self.assertFalse(result['success'])
        self.assertIn('rate limit', result['message'].lower())
    
    def test_permission_error_from_telegram(self):
        """Test handling of Telegram API permission errors"""
        mock_bot = Mock()
        mock_bot.set_my_description = Mock(side_effect=Exception("Permission denied (403)"))
        
        config = {
            'enabled': True,
            'description_template': 'Test Bot - {count} users',
            'update_interval': 0,
            'retry_attempts': 1,
            'retry_delay': 0
        }
        
        result = AnalyticsService.update_bot_description_with_count(
            bot_instance=mock_bot,
            config=config
        )
        
        self.assertFalse(result['success'])
        self.assertIn('permission', result['message'].lower())
    
    def test_retry_logic(self):
        """Test retry logic on transient failures"""
        mock_bot = Mock()
        # First call fails, second succeeds
        mock_bot.set_my_description = Mock(
            side_effect=[Exception("Temporary error"), None]
        )
        
        config = {
            'enabled': True,
            'description_template': 'Test Bot - {count} users',
            'update_interval': 0,
            'retry_attempts': 2,
            'retry_delay': 0
        }
        
        result = AnalyticsService.update_bot_description_with_count(
            bot_instance=mock_bot,
            config=config
        )
        
        # Should succeed on second attempt
        self.assertTrue(result['success'])
        self.assertEqual(mock_bot.set_my_description.call_count, 2)
    
    def test_formatted_count_in_description(self):
        """Test that count is properly formatted in description"""
        mock_bot = Mock()
        mock_bot.set_my_description = Mock()
        
        # Create 1500 users to test K formatting
        for i in range(1500):
            user = User.objects.create(
                telegram_id=100000 + i, 
                first_name=f"User{i}",
                username=f"user{i}"  # Add unique username to avoid constraint violation
            )
            UserInteraction.objects.create(user=user, interaction_type='message')
        
        config = {
            'enabled': True,
            'description_template': 'Bot with {count} monthly users',
            'update_interval': 0,
            'retry_attempts': 1,
            'retry_delay': 0
        }
        
        result = AnalyticsService.update_bot_description_with_count(
            bot_instance=mock_bot,
            config=config
        )
        
        self.assertTrue(result['success'])
        
        # Verify formatted count (should be "1.5K")
        call_args = mock_bot.set_my_description.call_args[0][0]
        self.assertIn('1.5K', call_args)
    
    def test_get_bot_description_config(self):
        """Test getting bot description configuration"""
        config = AnalyticsService.get_bot_description_config()
        
        # Verify default configuration structure
        self.assertIsInstance(config, dict)
        self.assertIn('enabled', config)
        self.assertIn('description_template', config)
        self.assertIn('update_interval', config)
        self.assertIn('retry_attempts', config)
        self.assertIn('retry_delay', config)
    
    def test_fallback_when_bot_instance_creation_fails(self):
        """Test fallback behavior when bot instance creation fails"""
        config = {
            'enabled': True,
            'description_template': 'Test Bot - {count} users',
            'update_interval': 0,
            'retry_attempts': 1,
            'retry_delay': 0
        }
        
        # Pass None as bot_instance to test fallback behavior
        # The method should try to create a bot instance internally
        with patch('telebot.TeleBot') as mock_bot_class:
            mock_bot_class.side_effect = Exception("Bot creation failed")
            
            result = AnalyticsService.update_bot_description_with_count(
                bot_instance=None,
                config=config
            )
            
            self.assertFalse(result['success'])
            self.assertIn('error', result)
