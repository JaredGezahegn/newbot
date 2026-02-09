"""
Integration tests for the complete monthly users count workflow.
Tests the full interaction tracking and display workflow, system behavior
under various load conditions, and configuration changes.

Requirements tested: 1.1, 2.1, 2.2, 2.3

NOTE: These tests require Django to be properly configured. Run with:
    python manage.py test bot.test_integration_workflow
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from unittest.mock import Mock, patch
from bot.models import User, UserInteraction
from bot.services.analytics_service import AnalyticsService
from bot.services.user_service import register_user


class CompleteWorkflowIntegrationTests(TestCase):
    """Integration tests for complete interaction tracking and display workflow."""
    
    def setUp(self):
        """Set up test environment."""
        # Clear all interactions
        UserInteraction.objects.all().delete()
        # Clear cache
        AnalyticsService.clear_cache()
    
    def test_end_to_end_interaction_tracking_and_display(self):
        """
        Test complete workflow: user interaction -> tracking -> MAU calculation -> display.
        Validates: Requirements 1.1, 2.1, 2.2, 2.3
        """
        # Step 1: Register users
        user1 = register_user(100001, "User1")
        user2 = register_user(100002, "User2")
        user3 = register_user(100003, "User3")
        
        # Step 2: Track various interactions
        AnalyticsService.track_user_interaction(user1, 'message')
        AnalyticsService.track_user_interaction(user1, 'command')
        AnalyticsService.track_user_interaction(user2, 'button_click')
        AnalyticsService.track_user_interaction(user3, 'message')
        
        # Step 3: Calculate MAU count
        mau_count = AnalyticsService.get_monthly_active_users_count()
        
        # Verify count is correct (3 unique users)
        self.assertEqual(mau_count, 3)
        
        # Step 4: Format for display
        formatted = AnalyticsService.format_user_count(mau_count)
        self.assertEqual(formatted, "3")
        
        # Step 5: Format with display configuration
        display = AnalyticsService.format_display(mau_count, {
            'format': 'full',
            'position': 'inline',
            'show_label': True
        })
        self.assertIn("3", display)
        self.assertIn("monthly active users", display)
        
        # Step 6: Verify caching works
        # Clear database but keep cache
        with patch('bot.models.UserInteraction.objects.filter') as mock_filter:
            cached_count = AnalyticsService.get_monthly_active_users_count()
            self.assertEqual(cached_count, mau_count)
            # Database should not be queried (cache hit)
            mock_filter.assert_not_called()
    
    def test_multiple_users_multiple_interactions_workflow(self):
        """
        Test workflow with multiple users having multiple interactions.
        Validates: Requirements 2.1, 2.2, 2.3
        """
        # Create 5 users with various interaction patterns
        users = []
        for i in range(5):
            user = register_user(200000 + i, f"MultiUser{i}")
            users.append(user)
        
        # User 0: 3 messages
        for _ in range(3):
            AnalyticsService.track_user_interaction(users[0], 'message')
        
        # User 1: 2 commands
        for _ in range(2):
            AnalyticsService.track_user_interaction(users[1], 'command')
        
        # User 2: 1 button click
        AnalyticsService.track_user_interaction(users[2], 'button_click')
        
        # User 3: mixed interactions
        AnalyticsService.track_user_interaction(users[3], 'message')
        AnalyticsService.track_user_interaction(users[3], 'command')
        AnalyticsService.track_user_interaction(users[3], 'button_click')
        
        # User 4: confession submit
        AnalyticsService.track_user_interaction(users[4], 'confession_submit')
        
        # Calculate MAU
        mau_count = AnalyticsService.get_monthly_active_users_count()
        
        # Should count 5 unique users despite multiple interactions
        self.assertEqual(mau_count, 5)
        
        # Verify total interactions
        total_interactions = UserInteraction.objects.count()
        self.assertEqual(total_interactions, 10)  # 3+2+1+3+1
    
    def test_time_based_filtering_workflow(self):
        """
        Test workflow with interactions at different times.
        Validates: Requirements 2.3
        """
        # Create users with interactions at different times
        now = timezone.now()
        
        # User with recent interaction (5 days ago)
        user1 = register_user(300001, "RecentUser")
        interaction1 = UserInteraction.objects.create(
            user=user1,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=interaction1.id).update(
            timestamp=now - timedelta(days=5)
        )
        
        # User with interaction 25 days ago (within 30 days)
        user2 = register_user(300002, "WithinMonthUser")
        interaction2 = UserInteraction.objects.create(
            user=user2,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=interaction2.id).update(
            timestamp=now - timedelta(days=25)
        )
        
        # User with old interaction (35 days ago - outside 30 days)
        user3 = register_user(300003, "OldUser")
        interaction3 = UserInteraction.objects.create(
            user=user3,
            interaction_type='message'
        )
        UserInteraction.objects.filter(id=interaction3.id).update(
            timestamp=now - timedelta(days=35)
        )
        
        # Calculate MAU with mocked time
        with patch('bot.services.analytics_service.timezone.now', return_value=now):
            mau_count = AnalyticsService.get_monthly_active_users_count()
        
        # Should only count users within 30 days (user1 and user2)
        self.assertEqual(mau_count, 2)


class LoadConditionIntegrationTests(TestCase):
    """Integration tests for system behavior under various load conditions."""
    
    def setUp(self):
        """Set up test environment."""
        UserInteraction.objects.all().delete()
        AnalyticsService.clear_cache()
    
    def test_high_volume_interaction_tracking(self):
        """
        Test system behavior with high volume of interactions.
        Validates: Requirements 2.1, 2.2
        """
        # Create 50 users
        users = []
        for i in range(50):
            user = register_user(400000 + i, f"LoadUser{i}")
            users.append(user)
        
        # Track 200 interactions (4 per user on average)
        interaction_count = 0
        for i in range(200):
            user = users[i % len(users)]
            interaction_type = ['message', 'command', 'button_click'][i % 3]
            result = AnalyticsService.track_user_interaction(user, interaction_type)
            if result is not None:
                interaction_count += 1
        
        # Verify all interactions were tracked
        self.assertEqual(interaction_count, 200)
        
        # Verify MAU count is correct
        mau_count = AnalyticsService.get_monthly_active_users_count()
        self.assertEqual(mau_count, 50)
    
    def test_concurrent_interaction_tracking(self):
        """
        Test system behavior with concurrent interaction tracking.
        Validates: Requirements 2.1, 2.2
        """
        # Create 10 users
        users = []
        for i in range(10):
            user = register_user(500000 + i, f"ConcurrentUser{i}")
            users.append(user)
        
        # Simulate concurrent interactions
        # In a real scenario, these would be parallel requests
        for user in users:
            # Each user performs multiple actions "simultaneously"
            AnalyticsService.track_user_interaction(user, 'message')
            AnalyticsService.track_user_interaction(user, 'command')
            AnalyticsService.track_user_interaction(user, 'button_click')
        
        # Verify all interactions were tracked
        total_interactions = UserInteraction.objects.count()
        self.assertEqual(total_interactions, 30)  # 10 users * 3 interactions
        
        # Verify MAU count is correct
        mau_count = AnalyticsService.get_monthly_active_users_count()
        self.assertEqual(mau_count, 10)
    
    def test_cache_performance_under_load(self):
        """
        Test cache performance with repeated MAU calculations.
        Validates: Requirements 2.3
        """
        # Create users with interactions
        for i in range(20):
            user = register_user(600000 + i, f"CacheUser{i}")
            AnalyticsService.track_user_interaction(user, 'message')
        
        # First call calculates and caches
        first_count = AnalyticsService.get_monthly_active_users_count()
        self.assertEqual(first_count, 20)
        
        # Subsequent calls should use cache (no database queries)
        with patch('bot.models.UserInteraction.objects.filter') as mock_filter:
            for _ in range(100):
                cached_count = AnalyticsService.get_monthly_active_users_count()
                self.assertEqual(cached_count, first_count)
            
            # Verify database was not queried
            mock_filter.assert_not_called()


class ConfigurationChangeIntegrationTests(TestCase):
    """Integration tests for configuration changes and their effects."""
    
    def setUp(self):
        """Set up test environment."""
        UserInteraction.objects.all().delete()
        AnalyticsService.clear_cache()
    
    def test_display_format_configuration_changes(self):
        """
        Test different display format configurations.
        Validates: Requirements 1.1
        """
        # Create users and track interactions
        for i in range(1500):
            user = register_user(700000 + i, f"FormatUser{i}")
            AnalyticsService.track_user_interaction(user, 'message')
        
        # Get MAU count
        mau_count = AnalyticsService.get_monthly_active_users_count()
        self.assertEqual(mau_count, 1500)
        
        # Test abbreviated format
        abbreviated = AnalyticsService.format_display(mau_count, {
            'format': 'abbreviated',
            'show_label': False
        })
        self.assertEqual(abbreviated, "1.5K")
        
        # Test full format
        full = AnalyticsService.format_display(mau_count, {
            'format': 'full',
            'show_label': False
        })
        self.assertEqual(full, "1500")
        
        # Test with label inline
        inline = AnalyticsService.format_display(mau_count, {
            'format': 'abbreviated',
            'position': 'inline',
            'show_label': True
        })
        self.assertIn("1.5K", inline)
        self.assertIn("monthly active users", inline)
        self.assertNotIn("\n", inline)
        
        # Test with label on separate line
        separate = AnalyticsService.format_display(mau_count, {
            'format': 'abbreviated',
            'position': 'separate_line',
            'show_label': True
        })
        self.assertIn("1.5K", separate)
        self.assertIn("monthly active users", separate)
        self.assertIn("\n", separate)
    
    def test_low_count_hiding_configuration(self):
        """
        Test low count hiding configuration.
        Validates: Requirements 1.1
        """
        # Create 5 users
        for i in range(5):
            user = register_user(800000 + i, f"LowCountUser{i}")
            AnalyticsService.track_user_interaction(user, 'message')
        
        mau_count = AnalyticsService.get_monthly_active_users_count()
        self.assertEqual(mau_count, 5)
        
        # Test with hiding disabled
        display_shown = AnalyticsService.format_display(mau_count, {
            'hide_low_counts': False,
            'low_count_threshold': 10
        })
        self.assertNotEqual(display_shown, '')
        self.assertIn("5", display_shown)
        
        # Test with hiding enabled
        display_hidden = AnalyticsService.format_display(mau_count, {
            'hide_low_counts': True,
            'low_count_threshold': 10
        })
        self.assertEqual(display_hidden, '')
        
        # Test with count above threshold
        for i in range(10):
            user = register_user(800100 + i, f"MoreUser{i}")
            AnalyticsService.track_user_interaction(user, 'message')
        
        AnalyticsService.clear_cache()
        mau_count = AnalyticsService.get_monthly_active_users_count()
        self.assertEqual(mau_count, 15)
        
        display_shown_above = AnalyticsService.format_display(mau_count, {
            'hide_low_counts': True,
            'low_count_threshold': 10
        })
        self.assertNotEqual(display_shown_above, '')
        self.assertIn("15", display_shown_above)
    
    def test_cache_timeout_configuration(self):
        """
        Test cache timeout configuration effects.
        Validates: Requirements 2.3
        """
        # Create initial users
        for i in range(10):
            user = register_user(900000 + i, f"TimeoutUser{i}")
            AnalyticsService.track_user_interaction(user, 'message')
        
        # Get initial count (caches result)
        initial_count = AnalyticsService.get_monthly_active_users_count()
        self.assertEqual(initial_count, 10)
        
        # Add more users
        for i in range(5):
            user = register_user(900100 + i, f"NewUser{i}")
            AnalyticsService.track_user_interaction(user, 'message')
        
        # Count should still be cached (returns old value)
        cached_count = AnalyticsService.get_monthly_active_users_count()
        self.assertEqual(cached_count, initial_count)
        
        # Clear cache to simulate timeout
        AnalyticsService.clear_cache()
        
        # Now should get updated count
        updated_count = AnalyticsService.get_monthly_active_users_count()
        self.assertEqual(updated_count, 15)
    
    def test_admin_analytics_configuration(self):
        """
        Test admin analytics report generation.
        Validates: Requirements 2.3
        """
        # Create users with various interaction types
        now = timezone.now()
        
        # Daily active users (last 24 hours)
        for i in range(5):
            user = register_user(1000000 + i, f"DailyUser{i}")
            interaction = UserInteraction.objects.create(
                user=user,
                interaction_type='message'
            )
            UserInteraction.objects.filter(id=interaction.id).update(
                timestamp=now - timedelta(hours=12)
            )
        
        # Weekly active users (last 7 days)
        for i in range(10):
            user = register_user(1000100 + i, f"WeeklyUser{i}")
            interaction = UserInteraction.objects.create(
                user=user,
                interaction_type='command'
            )
            UserInteraction.objects.filter(id=interaction.id).update(
                timestamp=now - timedelta(days=5)
            )
        
        # Monthly active users (last 30 days)
        for i in range(15):
            user = register_user(1000200 + i, f"MonthlyUser{i}")
            interaction = UserInteraction.objects.create(
                user=user,
                interaction_type='button_click'
            )
            UserInteraction.objects.filter(id=interaction.id).update(
                timestamp=now - timedelta(days=20)
            )
        
        # Get admin analytics report
        with patch('bot.services.analytics_service.timezone.now', return_value=now):
            report = AnalyticsService.get_admin_analytics_report()
        
        # Verify report structure
        self.assertIn('total_interactions', report)
        self.assertIn('monthly_active_users', report)
        self.assertIn('daily_active_users', report)
        self.assertIn('weekly_active_users', report)
        self.assertIn('interaction_types_breakdown', report)
        
        # Verify counts
        self.assertEqual(report['total_interactions'], 30)
        self.assertEqual(report['daily_active_users'], 5)
        self.assertEqual(report['weekly_active_users'], 15)  # 5 daily + 10 weekly
        self.assertEqual(report['monthly_active_users'], 30)  # 5 + 10 + 15
        
        # Verify interaction types breakdown
        self.assertEqual(report['interaction_types_breakdown']['message'], 5)
        self.assertEqual(report['interaction_types_breakdown']['command'], 10)
        self.assertEqual(report['interaction_types_breakdown']['button_click'], 15)
