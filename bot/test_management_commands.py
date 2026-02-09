"""
Unit tests for management commands.
Tests for cleanup_old_interactions, update_mau_count, and regenerate_mau_cache commands.
"""
import os
import django
from io import StringIO

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.test_settings')
django.setup()

from django.test import TestCase
from django.core.management import call_command
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from bot.models import User, UserInteraction
from bot.services.analytics_service import AnalyticsService


class CleanupOldInteractionsCommandTests(TestCase):
    """Tests for cleanup_old_interactions management command"""
    
    def setUp(self):
        """Set up test data"""
        # Clear all existing interactions
        UserInteraction.objects.all().delete()
        
        # Create test users
        self.user1 = User.objects.create(
            telegram_id=100001,
            username='cleanup_user1',
            first_name='Cleanup1',
            password='test'
        )
        self.user2 = User.objects.create(
            telegram_id=100002,
            username='cleanup_user2',
            first_name='Cleanup2',
            password='test'
        )
    
    def tearDown(self):
        """Clean up test data"""
        UserInteraction.objects.all().delete()
        self.user1.delete()
        self.user2.delete()
    
    def test_cleanup_old_interactions_default_retention(self):
        """Test cleanup with default 90-day retention"""
        # Create interactions at various ages
        now = timezone.now()
        
        # Recent interaction (10 days old) - should NOT be deleted
        recent_interaction = UserInteraction.objects.create(
            user=self.user1,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=recent_interaction.id).update(
            timestamp=now - timedelta(days=10)
        )
        
        # Old interaction (100 days old) - should be deleted
        old_interaction = UserInteraction.objects.create(
            user=self.user2,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=old_interaction.id).update(
            timestamp=now - timedelta(days=100)
        )
        
        # Count before cleanup
        count_before = UserInteraction.objects.count()
        self.assertEqual(count_before, 2)
        
        # Run cleanup command
        out = StringIO()
        call_command('cleanup_old_interactions', stdout=out)
        
        # Verify old interaction was deleted
        count_after = UserInteraction.objects.count()
        self.assertEqual(count_after, 1)
        
        # Verify recent interaction still exists
        self.assertTrue(UserInteraction.objects.filter(id=recent_interaction.id).exists())
        
        # Verify old interaction was deleted
        self.assertFalse(UserInteraction.objects.filter(id=old_interaction.id).exists())
        
        # Check output
        output = out.getvalue()
        self.assertIn('Successfully deleted 1 interactions', output)
    
    def test_cleanup_custom_retention_period(self):
        """Test cleanup with custom retention period"""
        # Create interactions at various ages
        now = timezone.now()
        
        # Interaction 20 days old - should NOT be deleted with 30-day retention
        recent_interaction = UserInteraction.objects.create(
            user=self.user1,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=recent_interaction.id).update(
            timestamp=now - timedelta(days=20)
        )
        
        # Interaction 40 days old - should be deleted with 30-day retention
        old_interaction = UserInteraction.objects.create(
            user=self.user2,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=old_interaction.id).update(
            timestamp=now - timedelta(days=40)
        )
        
        # Run cleanup with 30-day retention
        out = StringIO()
        call_command('cleanup_old_interactions', days=30, stdout=out)
        
        # Verify only old interaction was deleted
        self.assertEqual(UserInteraction.objects.count(), 1)
        self.assertTrue(UserInteraction.objects.filter(id=recent_interaction.id).exists())
        self.assertFalse(UserInteraction.objects.filter(id=old_interaction.id).exists())
    
    def test_cleanup_dry_run(self):
        """Test cleanup with dry-run flag"""
        # Create old interaction
        now = timezone.now()
        old_interaction = UserInteraction.objects.create(
            user=self.user1,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=old_interaction.id).update(
            timestamp=now - timedelta(days=100)
        )
        
        # Run cleanup with dry-run
        out = StringIO()
        call_command('cleanup_old_interactions', dry_run=True, stdout=out)
        
        # Verify nothing was deleted
        self.assertEqual(UserInteraction.objects.count(), 1)
        self.assertTrue(UserInteraction.objects.filter(id=old_interaction.id).exists())
        
        # Check output mentions dry run
        output = out.getvalue()
        self.assertIn('DRY RUN', output)
        self.assertIn('Would delete 1 interactions', output)
    
    def test_cleanup_no_old_interactions(self):
        """Test cleanup when there are no old interactions"""
        # Create only recent interactions
        now = timezone.now()
        recent_interaction = UserInteraction.objects.create(
            user=self.user1,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=recent_interaction.id).update(
            timestamp=now - timedelta(days=10)
        )
        
        # Run cleanup
        out = StringIO()
        call_command('cleanup_old_interactions', stdout=out)
        
        # Verify nothing was deleted
        self.assertEqual(UserInteraction.objects.count(), 1)
        
        # Check output
        output = out.getvalue()
        self.assertIn('Successfully deleted 0 interactions', output)


class UpdateMAUCountCommandTests(TestCase):
    """Tests for update_mau_count management command"""
    
    def setUp(self):
        """Set up test data"""
        # Clear all existing interactions
        UserInteraction.objects.all().delete()
        
        # Clear cache
        AnalyticsService.clear_cache()
        
        # Create test users
        self.user1 = User.objects.create(
            telegram_id=200001,
            username='mau_user1',
            first_name='MAU1',
            password='test'
        )
        self.user2 = User.objects.create(
            telegram_id=200002,
            username='mau_user2',
            first_name='MAU2',
            password='test'
        )
    
    def tearDown(self):
        """Clean up test data"""
        UserInteraction.objects.all().delete()
        self.user1.delete()
        self.user2.delete()
        AnalyticsService.clear_cache()
    
    def test_update_mau_count_basic(self):
        """Test basic MAU count update"""
        # Create interactions within last 30 days
        now = timezone.now()
        
        interaction1 = UserInteraction.objects.create(
            user=self.user1,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=interaction1.id).update(
            timestamp=now - timedelta(days=10)
        )
        
        interaction2 = UserInteraction.objects.create(
            user=self.user2,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=interaction2.id).update(
            timestamp=now - timedelta(days=20)
        )
        
        # Run update command
        out = StringIO()
        call_command('update_mau_count', stdout=out)
        
        # Check output
        output = out.getvalue()
        self.assertIn('Monthly Active Users: 2', output)
        self.assertIn('✅', output)
    
    def test_update_mau_count_verbose(self):
        """Test MAU count update with verbose output"""
        # Create interactions
        now = timezone.now()
        
        # Recent interaction
        interaction1 = UserInteraction.objects.create(
            user=self.user1,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=interaction1.id).update(
            timestamp=now - timedelta(days=5)
        )
        
        # Run update command with verbose flag
        out = StringIO()
        call_command('update_mau_count', verbose=True, stdout=out)
        
        # Check output contains detailed statistics
        output = out.getvalue()
        self.assertIn('DETAILED STATISTICS', output)
        self.assertIn('Daily Active Users', output)
        self.assertIn('Weekly Active Users', output)
        self.assertIn('Monthly Active Users', output)
        self.assertIn('Total Interactions', output)
    
    def test_update_mau_count_no_cache(self):
        """Test MAU count update with no-cache flag"""
        # Create interaction
        now = timezone.now()
        interaction = UserInteraction.objects.create(
            user=self.user1,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=interaction.id).update(
            timestamp=now - timedelta(days=5)
        )
        
        # First call to populate cache
        AnalyticsService.get_monthly_active_users_count()
        
        # Verify cache is set
        cached_value = cache.get(AnalyticsService.CACHE_KEY_MAU)
        self.assertIsNotNone(cached_value)
        
        # Run update command with no-cache flag
        out = StringIO()
        call_command('update_mau_count', no_cache=True, stdout=out)
        
        # Command should still work and show correct count
        output = out.getvalue()
        self.assertIn('Monthly Active Users: 1', output)
    
    def test_update_mau_count_zero_users(self):
        """Test MAU count update when there are no active users"""
        # Don't create any interactions
        
        # Run update command
        out = StringIO()
        call_command('update_mau_count', stdout=out)
        
        # Check output shows zero
        output = out.getvalue()
        self.assertIn('Monthly Active Users: 0', output)


class RegenerateMAUCacheCommandTests(TestCase):
    """Tests for regenerate_mau_cache management command"""
    
    def setUp(self):
        """Set up test data"""
        # Clear all existing interactions
        UserInteraction.objects.all().delete()
        
        # Clear cache
        AnalyticsService.clear_cache()
        
        # Create test user
        self.user = User.objects.create(
            telegram_id=300001,
            username='cache_user',
            first_name='Cache',
            password='test'
        )
    
    def tearDown(self):
        """Clean up test data"""
        UserInteraction.objects.all().delete()
        self.user.delete()
        AnalyticsService.clear_cache()
    
    def test_regenerate_cache_basic(self):
        """Test basic cache regeneration"""
        # Create interaction
        now = timezone.now()
        interaction = UserInteraction.objects.create(
            user=self.user,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=interaction.id).update(
            timestamp=now - timedelta(days=10)
        )
        
        # Verify cache is empty
        cached_value = cache.get(AnalyticsService.CACHE_KEY_MAU)
        self.assertIsNone(cached_value)
        
        # Run regenerate command
        out = StringIO()
        call_command('regenerate_mau_cache', stdout=out)
        
        # Verify cache is now set
        cached_value = cache.get(AnalyticsService.CACHE_KEY_MAU)
        self.assertIsNotNone(cached_value)
        self.assertEqual(cached_value, 1)
        
        # Check output
        output = out.getvalue()
        self.assertIn('Cache cleared successfully', output)
        self.assertIn('Cache regenerated successfully', output)
        self.assertIn('Monthly Active Users: 1', output)
        self.assertIn('Cache verification passed', output)
    
    def test_regenerate_cache_clear_only(self):
        """Test cache regeneration with clear-only flag"""
        # Create interaction and populate cache
        now = timezone.now()
        interaction = UserInteraction.objects.create(
            user=self.user,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=interaction.id).update(
            timestamp=now - timedelta(days=10)
        )
        
        # Populate cache
        AnalyticsService.get_monthly_active_users_count()
        
        # Verify cache is set
        cached_value = cache.get(AnalyticsService.CACHE_KEY_MAU)
        self.assertIsNotNone(cached_value)
        
        # Run regenerate with clear-only flag
        out = StringIO()
        call_command('regenerate_mau_cache', clear_only=True, stdout=out)
        
        # Verify cache is cleared
        cached_value = cache.get(AnalyticsService.CACHE_KEY_MAU)
        self.assertIsNone(cached_value)
        
        # Check output
        output = out.getvalue()
        self.assertIn('Cache cleared successfully', output)
        self.assertIn('Cache will be regenerated on next request', output)
        self.assertNotIn('Cache regenerated', output)
    
    def test_regenerate_cache_replaces_old_value(self):
        """Test that cache regeneration replaces old cached value"""
        # Create interaction
        now = timezone.now()
        interaction = UserInteraction.objects.create(
            user=self.user,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=interaction.id).update(
            timestamp=now - timedelta(days=10)
        )
        
        # Set incorrect cache value manually
        cache.set(AnalyticsService.CACHE_KEY_MAU, 999, AnalyticsService.CACHE_TIMEOUT)
        
        # Verify incorrect value is cached
        cached_value = cache.get(AnalyticsService.CACHE_KEY_MAU)
        self.assertEqual(cached_value, 999)
        
        # Run regenerate command
        out = StringIO()
        call_command('regenerate_mau_cache', stdout=out)
        
        # Verify cache now has correct value
        cached_value = cache.get(AnalyticsService.CACHE_KEY_MAU)
        self.assertEqual(cached_value, 1)
        
        # Check output
        output = out.getvalue()
        self.assertIn('Cache verification passed', output)
    
    def test_regenerate_cache_with_no_interactions(self):
        """Test cache regeneration when there are no interactions"""
        # Don't create any interactions
        
        # Run regenerate command
        out = StringIO()
        call_command('regenerate_mau_cache', stdout=out)
        
        # Verify cache is set to 0
        cached_value = cache.get(AnalyticsService.CACHE_KEY_MAU)
        self.assertEqual(cached_value, 0)
        
        # Check output
        output = out.getvalue()
        self.assertIn('Monthly Active Users: 0', output)


if __name__ == '__main__':
    import unittest
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(CleanupOldInteractionsCommandTests))
    suite.addTests(loader.loadTestsFromTestCase(UpdateMAUCountCommandTests))
    suite.addTests(loader.loadTestsFromTestCase(RegenerateMAUCacheCommandTests))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    exit(0 if result.wasSuccessful() else 1)
