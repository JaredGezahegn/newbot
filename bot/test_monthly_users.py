"""
Property-based tests for monthly users count feature
"""
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase
from bot.models import User, UserInteraction
from django.db import models


class MessageInteractionTrackingTests(TestCase):
    """Tests for message interaction tracking"""
    
    # Feature: monthly-users-count, Property 2: Message interaction tracking
    @given(
        telegram_id=st.integers(min_value=1, max_value=9999999999),
        first_name=st.text(min_size=1, max_size=50)
    )
    @settings(max_examples=20)
    def test_message_interaction_tracking(self, telegram_id, first_name):
        """
        Property 2: Message interaction tracking
        For any user message sent to the bot, the system should record exactly one 
        interaction record with the correct user and timestamp.
        Validates: Requirements 2.1
        """
        from bot.services.user_service import register_user
        from bot.services.analytics_service import AnalyticsService
        
        # Register a user
        user = register_user(telegram_id, first_name)
        
        # Count interactions before tracking
        initial_count = UserInteraction.objects.filter(user=user, interaction_type='message').count()
        
        # Track a message interaction
        AnalyticsService.track_user_interaction(user, 'message')
        
        # Verify exactly one interaction was created
        final_count = UserInteraction.objects.filter(user=user, interaction_type='message').count()
        self.assertEqual(final_count, initial_count + 1)
        
        # Verify the interaction has the correct type
        interaction = UserInteraction.objects.filter(user=user, interaction_type='message').latest('timestamp')
        self.assertEqual(interaction.interaction_type, 'message')
        
        # Verify the interaction is linked to the correct user
        self.assertEqual(interaction.user, user)
        
        # Verify the timestamp is set
        self.assertIsNotNone(interaction.timestamp)



class ButtonInteractionTrackingTests(TestCase):
    """Tests for button and command interaction tracking"""
    
    # Feature: monthly-users-count, Property 3: Button and command interaction tracking
    @given(
        telegram_id=st.integers(min_value=1, max_value=9999999999),
        first_name=st.text(min_size=1, max_size=50),
        interaction_type=st.sampled_from(['button_click', 'command'])
    )
    @settings(max_examples=20)
    def test_button_and_command_interaction_tracking(self, telegram_id, first_name, interaction_type):
        """
        Property 3: Button and command interaction tracking
        For any button click or command execution, the system should record exactly one 
        interaction record with the correct user and timestamp.
        Validates: Requirements 2.2
        """
        from bot.services.user_service import register_user
        from bot.services.analytics_service import AnalyticsService
        
        # Register a user
        user = register_user(telegram_id, first_name)
        
        # Count interactions before tracking
        initial_count = UserInteraction.objects.filter(user=user, interaction_type=interaction_type).count()
        
        # Track the interaction
        AnalyticsService.track_user_interaction(user, interaction_type)
        
        # Verify exactly one interaction was created
        final_count = UserInteraction.objects.filter(user=user, interaction_type=interaction_type).count()
        self.assertEqual(final_count, initial_count + 1)
        
        # Verify the interaction has the correct type
        interaction = UserInteraction.objects.filter(user=user, interaction_type=interaction_type).latest('timestamp')
        self.assertEqual(interaction.interaction_type, interaction_type)
        
        # Verify the interaction is linked to the correct user
        self.assertEqual(interaction.user, user)
        
        # Verify the timestamp is set
        self.assertIsNotNone(interaction.timestamp)



class MAUCalculationTests(TestCase):
    """Tests for monthly active users calculation"""
    
    # Feature: monthly-users-count, Property 4: Monthly active users calculation accuracy
    @given(
        num_users=st.integers(min_value=1, max_value=20),
        # Use clear boundaries: 0-25 days (definitely in) and 35-60 days (definitely out)
        days_ago=st.lists(
            st.one_of(
                st.integers(min_value=0, max_value=25),
                st.integers(min_value=35, max_value=60)
            ),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=20, deadline=None)
    def test_mau_calculation_accuracy(self, num_users, days_ago):
        """
        Property 4: Monthly active users calculation accuracy
        For any set of user interactions, the monthly active users count should include 
        only unique users who interacted within the last 30 days.
        Validates: Requirements 2.3
        """
        from bot.services.user_service import register_user
        from bot.services.analytics_service import AnalyticsService
        from django.utils import timezone
        from datetime import timedelta
        from unittest.mock import patch
        
        # Clear all existing interactions to ensure clean state
        UserInteraction.objects.all().delete()
        
        # Clear cache to ensure fresh calculation
        AnalyticsService.clear_cache()
        
        # Use a fixed reference time for consistency
        fixed_now = timezone.now()
        
        # Create users and interactions at various times
        users_within_30_days = set()
        
        for i in range(num_users):
            # Create a unique user
            user = register_user(1000000 + i, f"User{i}")
            
            # Get the days_ago value for this user (cycle through the list)
            days_offset = days_ago[i % len(days_ago)]
            
            # Calculate the interaction timestamp
            interaction_timestamp = fixed_now - timedelta(days=days_offset)
            
            # Create an interaction and manually update the timestamp
            # We can't pass timestamp to create() because auto_now_add=True overrides it
            interaction = UserInteraction.objects.create(
                user=user,
                interaction_type='message'
            )
            # Update the timestamp using update() to bypass auto_now_add
            UserInteraction.objects.filter(id=interaction.id).update(timestamp=interaction_timestamp)
            
            # Track which users should be counted (within 30 days)
            # A user is active if their interaction is less than 30 days old
            if days_offset < 30:
                users_within_30_days.add(user.id)
        
        # Mock timezone.now() in the analytics_service module to return the same fixed time
        with patch('bot.services.analytics_service.timezone.now', return_value=fixed_now):
            # Calculate MAU count
            mau_count = AnalyticsService.get_monthly_active_users_count()
        
        # Verify the count matches users who interacted within 30 days
        expected_count = len(users_within_30_days)
        self.assertEqual(mau_count, expected_count)



class UserUniquenessTests(TestCase):
    """Tests for user uniqueness in monthly count"""
    
    # Feature: monthly-users-count, Property 5: User uniqueness in monthly count
    @given(
        num_interactions=st.integers(min_value=2, max_value=50)
    )
    @settings(max_examples=20, deadline=None)
    def test_user_uniqueness_in_monthly_count(self, num_interactions):
        """
        Property 5: User uniqueness in monthly count
        For any user with multiple interactions in a month, that user should be counted 
        exactly once in the monthly active users total.
        Validates: Requirements 2.4
        """
        from bot.services.user_service import register_user
        from bot.services.analytics_service import AnalyticsService
        from django.utils import timezone
        from datetime import timedelta
        
        # Clear all existing interactions to ensure clean state
        UserInteraction.objects.all().delete()
        
        # Clear cache to ensure fresh calculation
        AnalyticsService.clear_cache()
        
        # Create a single user
        user = register_user(9999999, "TestUser")
        
        # Create multiple interactions for the same user within the last 30 days
        now = timezone.now()
        for i in range(num_interactions):
            # Create interactions at various times within the last 25 days
            days_offset = i % 25  # Cycle through 0-24 days
            interaction_timestamp = now - timedelta(days=days_offset)
            UserInteraction.objects.create(
                user=user,
                interaction_type='message',
                timestamp=interaction_timestamp
            )
        
        # Calculate MAU count
        mau_count = AnalyticsService.get_monthly_active_users_count()
        
        # Verify the user is counted exactly once, regardless of number of interactions
        self.assertEqual(mau_count, 1)



class CachingBehaviorTests(TestCase):
    """Tests for count caching behavior"""
    
    # Feature: monthly-users-count, Property 6: Count caching behavior
    @given(
        num_users=st.integers(min_value=1, max_value=10),
        num_requests=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=20, deadline=None)
    def test_caching_behavior(self, num_users, num_requests):
        """
        Property 6: Count caching behavior
        For any repeated requests for the monthly users count within the cache timeout period, 
        the system should return the cached result without recalculating.
        Validates: Requirements 3.3
        """
        from bot.services.user_service import register_user
        from bot.services.analytics_service import AnalyticsService
        from django.utils import timezone
        from datetime import timedelta
        from unittest.mock import patch
        
        # Clear all existing interactions to ensure clean state
        UserInteraction.objects.all().delete()
        
        # Clear cache to start fresh
        AnalyticsService.clear_cache()
        
        # Create users with interactions within the last 30 days
        now = timezone.now()
        for i in range(num_users):
            user = register_user(8000000 + i, f"CacheUser{i}")
            interaction_timestamp = now - timedelta(days=i % 25)
            UserInteraction.objects.create(
                user=user,
                interaction_type='message',
                timestamp=interaction_timestamp
            )
        
        # First call should calculate and cache the result
        first_count = AnalyticsService.get_monthly_active_users_count()
        
        # Subsequent calls should return the same cached value
        # We'll verify this by checking that the database query is not executed again
        with patch('bot.models.UserInteraction.objects.filter') as mock_filter:
            for _ in range(num_requests - 1):
                cached_count = AnalyticsService.get_monthly_active_users_count()
                self.assertEqual(cached_count, first_count)
            
            # Verify that the database was not queried (cache was used)
            mock_filter.assert_not_called()
        
        # Clear cache and verify a new calculation is performed
        AnalyticsService.clear_cache()
        new_count = AnalyticsService.get_monthly_active_users_count()
        self.assertEqual(new_count, first_count)



class CountFormattingTests(TestCase):
    """Tests for count formatting consistency"""
    
    # Feature: monthly-users-count, Property 1: Count formatting consistency
    @given(
        count=st.integers(min_value=0, max_value=10000000)
    )
    @settings(max_examples=20)
    def test_count_formatting_consistency(self, count):
        """
        Property 1: Count formatting consistency
        For any user count value, the formatting function should produce a readable string 
        that follows the specified format rules (K for thousands, M for millions).
        Validates: Requirements 1.2, 1.3
        """
        from bot.services.analytics_service import AnalyticsService
        
        # Format the count
        formatted = AnalyticsService.format_user_count(count)
        
        # Verify the result is a string
        self.assertIsInstance(formatted, str)
        
        # Verify formatting rules based on count value
        if count < 1000:
            # For counts under 1000, should be the exact number as a string
            self.assertEqual(formatted, str(count))
        elif count < 1000000:
            # For counts 1K-999K, should end with 'K' and have one decimal place
            self.assertTrue(formatted.endswith('K'))
            # Remove 'K' and verify it's a valid number
            numeric_part = formatted[:-1]
            try:
                value = float(numeric_part)
                # Verify the value is in the correct range
                self.assertGreaterEqual(value, 1.0)
                self.assertLess(value, 1000.0)
                # Verify it has at most one decimal place
                if '.' in numeric_part:
                    decimal_places = len(numeric_part.split('.')[1])
                    self.assertLessEqual(decimal_places, 1)
            except ValueError:
                self.fail(f"Invalid numeric format: {numeric_part}")
        else:
            # For counts 1M+, should end with 'M' and have one decimal place
            self.assertTrue(formatted.endswith('M'))
            # Remove 'M' and verify it's a valid number
            numeric_part = formatted[:-1]
            try:
                value = float(numeric_part)
                # Verify the value is at least 1.0
                self.assertGreaterEqual(value, 1.0)
                # Verify it has at most one decimal place
                if '.' in numeric_part:
                    decimal_places = len(numeric_part.split('.')[1])
                    self.assertLessEqual(decimal_places, 1)
            except ValueError:
                self.fail(f"Invalid numeric format: {numeric_part}")
        
        # Verify the formatted string is not empty
        self.assertGreater(len(formatted), 0)



class DisplayConfigurationTests(TestCase):
    """Tests for display configuration flexibility"""
    
    # Feature: monthly-users-count, Property 8: Display configuration flexibility
    @given(
        count=st.integers(min_value=0, max_value=100000),
        format_type=st.sampled_from(['abbreviated', 'full']),
        position=st.sampled_from(['inline', 'separate_line']),
        show_label=st.booleans(),
        hide_low_counts=st.booleans(),
        low_count_threshold=st.integers(min_value=5, max_value=20)
    )
    @settings(max_examples=20)
    def test_display_configuration_flexibility(self, count, format_type, position, show_label, hide_low_counts, low_count_threshold):
        """
        Property 8: Display configuration flexibility
        For any valid display configuration settings, the system should format and position 
        the count according to those settings.
        Validates: Requirements 4.1
        """
        from bot.services.analytics_service import AnalyticsService
        
        # Create configuration
        config = {
            'format': format_type,
            'position': position,
            'label': 'monthly active users',
            'show_label': show_label,
            'hide_low_counts': hide_low_counts,
            'low_count_threshold': low_count_threshold
        }
        
        # Format the display
        display = AnalyticsService.format_display(count, config)
        
        # Verify the result is a string
        self.assertIsInstance(display, str)
        
        # If hiding low counts and count is below threshold, should return empty string
        if hide_low_counts and count < low_count_threshold:
            self.assertEqual(display, '')
            return
        
        # Otherwise, verify the display contains the count in some form
        if format_type == 'full':
            # Full format should contain the exact count
            self.assertIn(str(count), display)
        else:
            # Abbreviated format should contain the formatted count
            formatted_count = AnalyticsService.format_user_count(count)
            self.assertIn(formatted_count, display)
        
        # Verify label presence based on show_label setting
        if show_label:
            self.assertIn('monthly active users', display)
        else:
            # If label is not shown, display should only be the count
            if format_type == 'full':
                self.assertEqual(display, str(count))
            else:
                self.assertEqual(display, AnalyticsService.format_user_count(count))
        
        # Verify position formatting
        if show_label:
            if position == 'separate_line':
                # Should contain a newline
                self.assertIn('\n', display)
                # Label should come before the count
                parts = display.split('\n')
                self.assertEqual(len(parts), 2)
                self.assertIn('monthly active users', parts[0])
            else:  # inline
                # Should not contain newline
                self.assertNotIn('\n', display)
                # Count should come before label
                if format_type == 'full':
                    self.assertTrue(display.startswith(str(count)))
                else:
                    formatted_count = AnalyticsService.format_user_count(count)
                    self.assertTrue(display.startswith(formatted_count))



class PrivacyPreservationTests(TestCase):
    """Tests for privacy-preserving interaction storage"""
    
    # Feature: monthly-users-count, Property 9: Privacy-preserving interaction storage
    @given(
        telegram_id=st.integers(min_value=1, max_value=9999999999),
        first_name=st.text(min_size=1, max_size=50),
        interaction_type=st.sampled_from(['message', 'command', 'button_click', 'confession_submit', 'comment_add'])
    )
    @settings(max_examples=20)
    def test_privacy_preserving_interaction_storage(self, telegram_id, first_name, interaction_type):
        """
        Property 9: Privacy-preserving interaction storage
        For any user interaction record, the stored data should contain only interaction 
        metadata and not personally identifiable information.
        Validates: Requirements 4.3
        """
        from bot.services.user_service import register_user
        from bot.services.analytics_service import AnalyticsService
        
        # Register a user
        user = register_user(telegram_id, first_name)
        
        # Track an interaction
        AnalyticsService.track_user_interaction(user, interaction_type)
        
        # Retrieve the interaction record
        interaction = UserInteraction.objects.filter(user=user, interaction_type=interaction_type).latest('timestamp')
        
        # Verify the interaction record exists
        self.assertIsNotNone(interaction)
        
        # Verify only necessary metadata is stored
        # The UserInteraction model should only have: user (FK), interaction_type, timestamp
        interaction_fields = [field.name for field in UserInteraction._meta.get_fields()]
        
        # Expected fields: id, user, interaction_type, timestamp
        expected_fields = {'id', 'user', 'interaction_type', 'timestamp'}
        actual_fields = set(interaction_fields)
        
        # Verify no extra fields that could contain PII
        # We allow the expected fields and nothing more
        self.assertTrue(actual_fields.issubset(expected_fields | {'user_id'}), 
                       f"Unexpected fields found: {actual_fields - expected_fields}")
        
        # Verify the interaction_type is stored correctly (metadata only)
        self.assertEqual(interaction.interaction_type, interaction_type)
        
        # Verify timestamp is present
        self.assertIsNotNone(interaction.timestamp)
        
        # Verify the interaction record does NOT contain:
        # - Message content
        # - User's first name, last name, username directly
        # - IP addresses
        # - Device information
        # - Location data
        # These should not be fields on the UserInteraction model
        pii_fields = ['message_content', 'content', 'text', 'first_name', 'last_name', 
                     'username', 'ip_address', 'device', 'location', 'email', 'phone']
        
        for pii_field in pii_fields:
            self.assertFalse(hasattr(interaction, pii_field), 
                           f"UserInteraction should not have PII field: {pii_field}")
        
        # Verify that user reference is via FK only (not storing user data directly)
        self.assertEqual(interaction.user.id, user.id)
        self.assertIsInstance(interaction.user_id, int)



class AdminAnalyticsAnonymityTests(TestCase):
    """Tests for admin analytics anonymity preservation"""
    
    # Feature: monthly-users-count, Property 10: Admin analytics anonymity preservation
    @given(
        num_users=st.integers(min_value=1, max_value=20),
        days_ago_list=st.lists(
            st.integers(min_value=0, max_value=60),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=20, deadline=None)
    def test_admin_analytics_anonymity_preservation(self, num_users, days_ago_list):
        """
        Property 10: Admin analytics anonymity preservation
        For any admin analytics report, the data should provide insights without 
        exposing individual user identities.
        Validates: Requirements 4.5
        """
        from bot.services.user_service import register_user
        from bot.services.analytics_service import AnalyticsService
        from django.utils import timezone
        from datetime import timedelta
        from unittest.mock import patch
        
        # Clear all existing interactions to ensure clean state
        UserInteraction.objects.all().delete()
        
        # Clear cache to ensure fresh calculation
        AnalyticsService.clear_cache()
        
        # Use a fixed reference time for consistency
        fixed_now = timezone.now()
        
        # Create users with interactions at various times
        users_created = []
        
        for i in range(num_users):
            # Create a unique user with identifiable information
            user = register_user(2000000 + i, f"AdminTestUser{i}")
            users_created.append(user)
            
            # Get the days_ago value for this user (cycle through the list)
            days_offset = days_ago_list[i % len(days_ago_list)]
            
            # Create an interaction
            interaction_timestamp = fixed_now - timedelta(days=days_offset)
            interaction = UserInteraction.objects.create(
                user=user,
                interaction_type='message'
            )
            # Update the timestamp
            UserInteraction.objects.filter(id=interaction.id).update(timestamp=interaction_timestamp)
        
        # Mock timezone.now() to return the same fixed time
        with patch('bot.services.analytics_service.timezone.now', return_value=fixed_now):
            # Get admin analytics report
            analytics_report = AnalyticsService.get_admin_analytics_report()
        
        # Verify the report exists and is a dictionary
        self.assertIsInstance(analytics_report, dict)
        
        # Verify the report contains aggregate data
        self.assertIn('total_interactions', analytics_report)
        self.assertIn('monthly_active_users', analytics_report)
        self.assertIn('interaction_types_breakdown', analytics_report)
        
        # Verify the report does NOT contain individual user identities
        # Check that no user-specific PII is in the report
        report_str = str(analytics_report)
        
        # Verify no telegram IDs are exposed
        for user in users_created:
            self.assertNotIn(str(user.telegram_id), report_str,
                           f"Report should not expose telegram_id {user.telegram_id}")
        
        # Verify no usernames or first names are exposed
        for user in users_created:
            if user.first_name:
                self.assertNotIn(user.first_name, report_str,
                               f"Report should not expose first_name {user.first_name}")
            if user.username:
                self.assertNotIn(user.username, report_str,
                               f"Report should not expose username {user.username}")
        
        # Verify the report contains only aggregate statistics
        self.assertIsInstance(analytics_report['total_interactions'], int)
        self.assertIsInstance(analytics_report['monthly_active_users'], int)
        self.assertIsInstance(analytics_report['interaction_types_breakdown'], dict)
        
        # Verify aggregate data is accurate
        total_interactions = UserInteraction.objects.count()
        self.assertEqual(analytics_report['total_interactions'], total_interactions)
        
        # Verify MAU count is accurate (using the same fixed time)
        thirty_days_ago = fixed_now - timedelta(days=30)
        expected_mau = UserInteraction.objects.filter(
            timestamp__gte=thirty_days_ago
        ).values('user').distinct().count()
        self.assertEqual(analytics_report['monthly_active_users'], expected_mau)
        
        # Verify interaction types breakdown is accurate
        interaction_types = UserInteraction.objects.values('interaction_type').annotate(
            count=models.Count('id')
        )
        for item in interaction_types:
            interaction_type = item['interaction_type']
            count = item['count']
            self.assertEqual(analytics_report['interaction_types_breakdown'][interaction_type], count)



class DataPersistenceTests(TestCase):
    """Tests for data persistence across restarts"""
    
    # Feature: monthly-users-count, Property 7: Data persistence across restarts
    @given(
        num_users=st.integers(min_value=1, max_value=20),
        days_ago_list=st.lists(
            st.integers(min_value=0, max_value=25),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=20, deadline=None)
    def test_data_persistence_across_restarts(self, num_users, days_ago_list):
        """
        Property 7: Data persistence across restarts
        For any set of user interactions, the monthly active users count should remain 
        accurate after a system restart.
        Validates: Requirements 3.4
        """
        from bot.services.user_service import register_user
        from bot.services.analytics_service import AnalyticsService
        from django.utils import timezone
        from datetime import timedelta
        from unittest.mock import patch
        from django.core.cache import cache
        
        # Clear all existing interactions to ensure clean state
        UserInteraction.objects.all().delete()
        
        # Clear cache to start fresh
        AnalyticsService.clear_cache()
        
        # Use a fixed reference time for consistency
        fixed_now = timezone.now()
        
        # Create users with interactions at various times
        users_within_30_days = set()
        
        for i in range(num_users):
            # Create a unique user
            user = register_user(3000000 + i, f"PersistUser{i}")
            
            # Get the days_ago value for this user (cycle through the list)
            days_offset = days_ago_list[i % len(days_ago_list)]
            
            # Calculate the interaction timestamp
            interaction_timestamp = fixed_now - timedelta(days=days_offset)
            
            # Create an interaction
            interaction = UserInteraction.objects.create(
                user=user,
                interaction_type='message'
            )
            # Update the timestamp
            UserInteraction.objects.filter(id=interaction.id).update(timestamp=interaction_timestamp)
            
            # Track which users should be counted (within 30 days)
            if days_offset < 30:
                users_within_30_days.add(user.id)
        
        # Mock timezone.now() to return the same fixed time
        with patch('bot.services.analytics_service.timezone.now', return_value=fixed_now):
            # Calculate MAU count before "restart"
            mau_count_before = AnalyticsService.get_monthly_active_users_count()
            
            # Simulate a system restart by:
            # 1. Clearing the cache (simulates cache being lost on restart)
            cache.clear()
            
            # 2. Calculate MAU count after "restart"
            # The data should still be in the database and the count should be accurate
            mau_count_after = AnalyticsService.get_monthly_active_users_count()
        
        # Verify the count is the same before and after restart
        expected_count = len(users_within_30_days)
        self.assertEqual(mau_count_before, expected_count)
        self.assertEqual(mau_count_after, expected_count)
        self.assertEqual(mau_count_before, mau_count_after)
        
        # Verify the data persisted in the database
        # Count interactions that should still be there
        thirty_days_ago = fixed_now - timedelta(days=30)
        persisted_interactions = UserInteraction.objects.filter(
            timestamp__gte=thirty_days_ago
        ).values('user').distinct().count()
        
        self.assertEqual(persisted_interactions, expected_count)
