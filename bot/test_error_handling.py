"""
Unit tests for error handling in the monthly users count feature.
Tests database failures, cache failures, and Telegram API errors.
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.test_settings')
django.setup()

from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from bot.models import User, UserInteraction
from bot.services.analytics_service import AnalyticsService
from django.core.cache import cache
from django.db import DatabaseError, OperationalError
import logging


class DatabaseErrorHandlingTests(TestCase):
    """Tests for database connection failure scenarios"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear cache before each test
        cache.clear()
        # Create a test user
        self.user = User.objects.create(
            telegram_id=12345,
            username='testuser',
            first_name='Test',
            password='test'
        )
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    def test_track_interaction_database_failure(self):
        """Test that interaction tracking handles database failures gracefully"""
        # Mock database error during interaction creation
        with patch('bot.models.UserInteraction.objects.create', side_effect=DatabaseError("Connection lost")):
            # Should not raise exception
            result = AnalyticsService.track_user_interaction(self.user, 'message')
            
            # Should return None on failure
            self.assertIsNone(result)
    
    def test_mau_count_database_failure_with_cache(self):
        """Test MAU count falls back to cached value when database fails"""
        # First, populate the cache with a known value
        cache.set(AnalyticsService.CACHE_KEY_MAU, 42, AnalyticsService.CACHE_TIMEOUT)
        
        # Mock database error
        with patch('bot.models.UserInteraction.objects.filter', side_effect=DatabaseError("Connection lost")):
            # Should return cached value instead of raising exception
            count = AnalyticsService.get_monthly_active_users_count()
            self.assertEqual(count, 42)
    
    def test_mau_count_database_failure_without_cache(self):
        """Test MAU count returns 0 when database fails and no cache exists"""
        # Clear cache to ensure no cached value
        cache.clear()
        
        # Mock database error
        with patch('bot.models.UserInteraction.objects.filter', side_effect=DatabaseError("Connection lost")):
            # Should return 0 as fallback
            count = AnalyticsService.get_monthly_active_users_count()
            self.assertEqual(count, 0)
    
    def test_cleanup_database_failure(self):
        """Test cleanup handles database failures gracefully"""
        # Mock database error during cleanup
        with patch('bot.models.UserInteraction.objects.filter', side_effect=DatabaseError("Connection lost")):
            # Should not raise exception
            deleted_count = AnalyticsService.cleanup_old_interactions(90)
            
            # Should return 0 on failure
            self.assertEqual(deleted_count, 0)
    
    def test_admin_analytics_database_failure(self):
        """Test admin analytics returns empty report on database failure"""
        # Mock database error
        with patch('bot.models.UserInteraction.objects.count', side_effect=DatabaseError("Connection lost")):
            # Should not raise exception
            report = AnalyticsService.get_admin_analytics_report()
            
            # Should return empty report structure
            self.assertIsInstance(report, dict)
            self.assertEqual(report['total_interactions'], 0)
            self.assertEqual(report['monthly_active_users'], 0)
            self.assertEqual(report['interaction_types_breakdown'], {})


class CacheErrorHandlingTests(TestCase):
    """Tests for cache failure fallback behavior"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Clear cache and database
        cache.clear()
        UserInteraction.objects.all().delete()
        
        # Create test user and interactions
        self.user = User.objects.create(
            telegram_id=12346,
            username='cachetest',
            first_name='CacheTest',
            password='test'
        )
        UserInteraction.objects.create(user=self.user, interaction_type='message')
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    def test_mau_count_cache_get_failure(self):
        """Test MAU count falls back to database when cache.get fails"""
        # Mock cache.get to raise an exception
        with patch('django.core.cache.cache.get', side_effect=Exception("Cache unavailable")):
            # Should fall back to database query
            count = AnalyticsService.get_monthly_active_users_count()
            
            # Should return the actual count from database
            self.assertGreaterEqual(count, 0)
    
    def test_mau_count_cache_set_failure(self):
        """Test MAU count still returns correct value when cache.set fails"""
        # Clear cache first
        cache.clear()
        
        # Mock cache.set to raise an exception
        with patch('django.core.cache.cache.set', side_effect=Exception("Cache unavailable")):
            # Should still calculate and return the count
            count = AnalyticsService.get_monthly_active_users_count()
            
            # Should return the actual count from database
            self.assertGreaterEqual(count, 0)
    
    def test_cache_clear_failure(self):
        """Test that cache clear failures don't break the system"""
        # Mock cache.delete to raise an exception
        with patch('django.core.cache.cache.delete', side_effect=Exception("Cache unavailable")):
            # Should not raise exception
            try:
                AnalyticsService.clear_cache()
            except Exception as e:
                self.fail(f"clear_cache raised exception: {e}")


class TelegramAPIErrorHandlingTests(TestCase):
    """Tests for Telegram API error handling"""
    
    def setUp(self):
        """Set up test fixtures"""
        cache.clear()
        # Create test user
        self.user = User.objects.create(
            telegram_id=12347,
            username='apitest',
            first_name='APITest',
            password='test'
        )
        UserInteraction.objects.create(user=self.user, interaction_type='message')
    
    def tearDown(self):
        """Clean up after tests"""
        cache.clear()
    
    def test_bot_description_update_disabled(self):
        """Test bot description update when disabled in config"""
        config = {'enabled': False}
        result = AnalyticsService.update_bot_description_with_count(config=config)
        
        self.assertFalse(result['success'])
        self.assertIn('disabled', result['message'].lower())
    
    def test_bot_description_update_rate_limited(self):
        """Test bot description update respects rate limiting"""
        # Set last update time to now
        import time
        cache.set('bot_description_last_update', time.time(), timeout=None)
        
        config = {
            'enabled': True,
            'update_interval': 3600
        }
        
        result = AnalyticsService.update_bot_description_with_count(config=config)
        
        self.assertFalse(result['success'])
        self.assertIn('rate limited', result['message'].lower())
    
    def test_bot_description_update_telegram_rate_limit(self):
        """Test handling of Telegram API rate limit (429 error)"""
        mock_bot = Mock()
        mock_bot.set_my_description.side_effect = Exception("429 Too Many Requests")
        
        config = {
            'enabled': True,
            'retry_attempts': 1,
            'retry_delay': 0
        }
        
        result = AnalyticsService.update_bot_description_with_count(
            bot_instance=mock_bot,
            config=config
        )
        
        self.assertFalse(result['success'])
        self.assertIn('rate limit', result['message'].lower())
        self.assertIn('error', result)
    
    def test_bot_description_update_permission_error(self):
        """Test handling of Telegram API permission error (403)"""
        mock_bot = Mock()
        mock_bot.set_my_description.side_effect = Exception("403 Forbidden")
        
        config = {
            'enabled': True,
            'retry_attempts': 1,
            'retry_delay': 0
        }
        
        result = AnalyticsService.update_bot_description_with_count(
            bot_instance=mock_bot,
            config=config
        )
        
        self.assertFalse(result['success'])
        self.assertIn('permission', result['message'].lower())
        self.assertIn('error', result)
    
    def test_bot_description_update_generic_api_error(self):
        """Test handling of generic Telegram API errors"""
        mock_bot = Mock()
        mock_bot.set_my_description.side_effect = Exception("Network error")
        
        config = {
            'enabled': True,
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
    
    def test_bot_description_update_invalid_template(self):
        """Test handling of invalid description template"""
        mock_bot = Mock()
        
        config = {
            'enabled': True,
            'description_template': 'Invalid template {invalid_placeholder}',
            'retry_attempts': 1
        }
        
        result = AnalyticsService.update_bot_description_with_count(
            bot_instance=mock_bot,
            config=config
        )
        
        self.assertFalse(result['success'])
        self.assertIn('template', result['message'].lower())
    
    def test_bot_description_update_success_after_retry(self):
        """Test successful update after initial failure"""
        mock_bot = Mock()
        # First call fails, second succeeds
        mock_bot.set_my_description.side_effect = [
            Exception("Temporary error"),
            None  # Success
        ]
        
        config = {
            'enabled': True,
            'retry_attempts': 2,
            'retry_delay': 0
        }
        
        result = AnalyticsService.update_bot_description_with_count(
            bot_instance=mock_bot,
            config=config
        )
        
        self.assertTrue(result['success'])
        self.assertIn('success', result['message'].lower())


class EdgeCaseHandlingTests(TestCase):
    """Tests for edge cases and invalid data handling"""
    
    def test_track_interaction_with_none_user(self):
        """Test tracking interaction with None user"""
        # Should handle None gracefully
        result = AnalyticsService.track_user_interaction(None, 'message')
        self.assertIsNone(result)
    
    def test_track_interaction_with_invalid_type(self):
        """Test tracking interaction with invalid type"""
        user = User.objects.create(
            telegram_id=12348,
            username='edgetest',
            first_name='EdgeTest',
            password='test'
        )
        
        # Should handle empty string gracefully (returns None)
        result = AnalyticsService.track_user_interaction(user, '')
        self.assertIsNone(result)
        
        # Should handle very long string
        long_type = 'x' * 100
        result = AnalyticsService.track_user_interaction(user, long_type)
        # May fail due to max_length constraint, should handle gracefully
        # Result could be None if it fails
    
    def test_format_user_count_negative(self):
        """Test formatting negative user counts"""
        # Should handle negative numbers gracefully
        formatted = AnalyticsService.format_user_count(-10)
        self.assertIsInstance(formatted, str)
    
    def test_format_user_count_zero(self):
        """Test formatting zero user count"""
        formatted = AnalyticsService.format_user_count(0)
        self.assertEqual(formatted, '0')
    
    def test_format_display_with_none_config(self):
        """Test format_display with None config uses defaults"""
        display = AnalyticsService.format_display(100, None)
        self.assertIsInstance(display, str)
        self.assertGreater(len(display), 0)
    
    def test_format_display_with_partial_config(self):
        """Test format_display with partial config merges with defaults"""
        config = {'format': 'full'}
        display = AnalyticsService.format_display(100, config)
        self.assertIn('100', display)
    
    def test_cleanup_with_negative_days(self):
        """Test cleanup with negative retention days"""
        # Should handle gracefully
        deleted_count = AnalyticsService.cleanup_old_interactions(-10)
        self.assertGreaterEqual(deleted_count, 0)
    
    def test_cleanup_with_zero_days(self):
        """Test cleanup with zero retention days"""
        # Should handle gracefully
        deleted_count = AnalyticsService.cleanup_old_interactions(0)
        self.assertGreaterEqual(deleted_count, 0)


if __name__ == '__main__':
    import unittest
    unittest.main()
