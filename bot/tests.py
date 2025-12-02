import time
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase
from django.db import IntegrityError, transaction
from bot.models import User


class UserRegistrationTests(TestCase):
    """Tests for user registration functionality"""
    
    # Feature: anonymous-confession-bot, Property 1: User registration creates unique profiles
    @given(telegram_id=st.integers(min_value=1, max_value=9999999999))
    @settings(max_examples=100)
    def test_user_registration_uniqueness(self, telegram_id):
        """
        Property 1: User registration creates unique profiles
        For any Telegram user ID, registering multiple times should result in 
        only one user profile in the database.
        Validates: Requirements 1.1
        """
        # Create first user with this telegram_id
        user1 = User.objects.create(
            username=f"user_{telegram_id}",
            telegram_id=telegram_id,
            first_name="Test",
        )
        
        # Attempt to create second user with same telegram_id should fail
        # due to unique constraint
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create(
                    username=f"user_{telegram_id}_duplicate",
                    telegram_id=telegram_id,
                    first_name="Test2",
                )
        
        # Verify only one user exists with this telegram_id
        user_count = User.objects.filter(telegram_id=telegram_id).count()
        self.assertEqual(user_count, 1)
        
        # Verify the first user is still in the database
        self.assertTrue(User.objects.filter(id=user1.id).exists())


class AnonymityToggleTests(TestCase):
    """Tests for anonymity toggle functionality"""
    
    # Feature: anonymous-confession-bot, Property 2: Anonymity toggle updates user setting
    @given(
        telegram_id=st.integers(min_value=1, max_value=9999999999),
        first_name=st.text(min_size=1, max_size=50)
    )
    @settings(max_examples=100)
    def test_anonymity_toggle_round_trip(self, telegram_id, first_name):
        """
        Property 2: Anonymity toggle updates user setting
        For any registered user, toggling anonymity mode on then off should 
        return the user to non-anonymous mode.
        Validates: Requirements 1.2, 1.3
        """
        from bot.services.user_service import register_user, toggle_anonymity
        
        # Register a user (default is anonymous mode = True)
        user = register_user(telegram_id, first_name)
        
        # Verify initial state is anonymous
        self.assertTrue(user.is_anonymous_mode)
        
        # Toggle anonymity off
        user = toggle_anonymity(user, False)
        user.refresh_from_db()
        self.assertFalse(user.is_anonymous_mode)
        
        # Toggle anonymity on
        user = toggle_anonymity(user, True)
        user.refresh_from_db()
        self.assertTrue(user.is_anonymous_mode)
        
        # Toggle anonymity off again (round trip)
        user = toggle_anonymity(user, False)
        user.refresh_from_db()
        self.assertFalse(user.is_anonymous_mode)



class ImpactPointsTests(TestCase):
    """Tests for impact points calculation"""
    
    # Feature: anonymous-confession-bot, Property 9: Impact points calculation accuracy
    @given(
        telegram_id=st.integers(min_value=1, max_value=9999999999),
        num_confessions=st.integers(min_value=0, max_value=10),
        num_comments=st.integers(min_value=0, max_value=10),
        num_likes=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100)
    def test_impact_points_calculation(self, telegram_id, num_confessions, num_comments, num_likes):
        """
        Property 9: Impact points calculation accuracy
        For any user, the impact points should equal the sum of approved confessions count, 
        comments count, and positive reactions received.
        Validates: Requirements 6.4
        """
        from bot.services.user_service import register_user, calculate_impact_points
        from bot.models import Confession, Comment, Reaction
        
        # Register a user
        user = register_user(telegram_id, "Test User")
        
        # Create approved confessions
        for i in range(num_confessions):
            Confession.objects.create(
                user=user,
                text=f"Confession {i}",
                status='approved',
                is_anonymous=True
            )
        
        # Create comments
        # We need a confession to comment on (create by a different user to not affect count)
        if num_comments > 0:
            # Create a different user for the target confession
            other_user = User.objects.create(
                username=f"other_user_{telegram_id}",
                telegram_id=telegram_id + 999999999,
                first_name="Other User"
            )
            target_confession = Confession.objects.create(
                user=other_user,
                text="Target confession",
                status='approved',
                is_anonymous=True
            )
            
            for i in range(num_comments):
                Comment.objects.create(
                    confession=target_confession,
                    user=user,
                    text=f"Comment {i}"
                )
        
        # Create likes on user's comments
        if num_likes > 0 and num_comments > 0:
            user_comments = Comment.objects.filter(user=user)[:num_likes]
            
            for idx, comment in enumerate(user_comments):
                # Create a different user to like the comment
                liker = User.objects.create(
                    username=f"liker_{telegram_id}_{idx}",
                    telegram_id=telegram_id + idx + 1000000,
                    first_name="Liker"
                )
                Reaction.objects.create(
                    comment=comment,
                    user=liker,
                    reaction_type='like'
                )
        
        # Calculate impact points
        impact_points = calculate_impact_points(user)
        
        # Expected impact points
        expected_impact = num_confessions + num_comments + min(num_likes, num_comments)
        
        # Verify the calculation
        self.assertEqual(impact_points, expected_impact)


class ConfessionSubmissionTests(TestCase):
    """Tests for confession submission functionality"""
    
    # Feature: anonymous-confession-bot, Property 3: Confession submission creates pending record
    @given(
        telegram_id=st.integers(min_value=1, max_value=9999999999),
        confession_text=st.text(min_size=1, max_size=4096)
    )
    @settings(max_examples=100)
    def test_confession_submission_creates_pending(self, telegram_id, confession_text):
        """
        Property 3: Confession submission creates pending record
        For any valid confession text from a registered user, submitting the confession 
        should create exactly one confession record with status 'pending'.
        Validates: Requirements 2.2
        """
        from bot.services.user_service import register_user
        from bot.services.confession_service import create_confession
        from bot.models import Confession
        
        # Register a user
        user = register_user(telegram_id, "Test User")
        
        # Count confessions before submission
        initial_count = Confession.objects.filter(user=user).count()
        
        # Submit confession
        confession = create_confession(user, confession_text)
        
        # Verify exactly one confession was created
        final_count = Confession.objects.filter(user=user).count()
        self.assertEqual(final_count, initial_count + 1)
        
        # Verify the confession has pending status
        self.assertEqual(confession.status, 'pending')
        
        # Verify the confession is linked to the user
        self.assertEqual(confession.user, user)
        
        # Verify the confession text matches
        self.assertEqual(confession.text, confession_text)


class CharacterLimitTests(TestCase):
    """Tests for character limit enforcement"""
    
    # Feature: anonymous-confession-bot, Property 4: Character limit enforcement
    @given(
        telegram_id=st.integers(min_value=1, max_value=9999999999),
        extra_chars=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=100)
    def test_character_limit_enforcement(self, telegram_id, extra_chars):
        """
        Property 4: Character limit enforcement
        For any confession text exceeding 4096 characters, the system should reject the submission.
        Validates: Requirements 2.5
        """
        from bot.services.user_service import register_user
        from bot.services.confession_service import create_confession
        
        # Register a user
        user = register_user(telegram_id, "Test User")
        
        # Create text that exceeds the limit
        long_text = "a" * (4096 + extra_chars)
        
        # Attempt to submit confession should raise ValueError
        with self.assertRaises(ValueError) as context:
            create_confession(user, long_text)
        
        # Verify the error message mentions character limit
        self.assertIn("4096", str(context.exception))


class AdminApprovalTests(TestCase):
    """Tests for admin approval functionality"""
    
    # Feature: anonymous-confession-bot, Property 5: Admin approval publishes to channel
    @given(
        user_telegram_id=st.integers(min_value=1, max_value=9999999999),
        admin_telegram_id=st.integers(min_value=1, max_value=9999999999),
        confession_text=st.text(min_size=1, max_size=4096)
    )
    @settings(max_examples=100)
    def test_admin_approval_changes_status(self, user_telegram_id, admin_telegram_id, confession_text):
        """
        Property 5: Admin approval publishes to channel
        For any pending confession, when an admin approves it, the confession status 
        should change to 'approved' and a message should be posted to the configured channel.
        
        Note: This test verifies the status change. Channel publishing requires a bot instance
        and is tested separately.
        
        Validates: Requirements 3.2, 4.1
        """
        from bot.services.user_service import register_user
        from bot.services.confession_service import create_confession, approve_confession
        
        # Ensure user and admin have different telegram IDs
        if user_telegram_id == admin_telegram_id:
            admin_telegram_id = user_telegram_id + 1
        
        # Register a user and an admin
        user = register_user(user_telegram_id, "Test User")
        admin = register_user(admin_telegram_id, "Admin User")
        admin.is_admin = True
        admin.save()
        
        # Create a pending confession
        confession = create_confession(user, confession_text)
        self.assertEqual(confession.status, 'pending')
        
        # Get initial confession count
        initial_count = user.total_confessions
        
        # Approve the confession (without bot instance for testing)
        approved_confession = approve_confession(confession, admin, bot_instance=None)
        
        # Verify status changed to approved
        self.assertEqual(approved_confession.status, 'approved')
        
        # Verify reviewed_by is set to admin
        self.assertEqual(approved_confession.reviewed_by, admin)
        
        # Verify reviewed_at is set
        self.assertIsNotNone(approved_confession.reviewed_at)
        
        # Verify user's confession count incremented
        user.refresh_from_db()
        self.assertEqual(user.total_confessions, initial_count + 1)


class AdminRejectionTests(TestCase):
    """Tests for admin rejection functionality"""
    
    # Feature: anonymous-confession-bot, Property 6: Admin rejection notifies user
    @given(
        user_telegram_id=st.integers(min_value=1, max_value=9999999999),
        admin_telegram_id=st.integers(min_value=1, max_value=9999999999),
        confession_text=st.text(min_size=1, max_size=4096)
    )
    @settings(max_examples=100)
    def test_admin_rejection_changes_status(self, user_telegram_id, admin_telegram_id, confession_text):
        """
        Property 6: Admin rejection notifies user
        For any pending confession, when an admin rejects it, the confession status 
        should change to 'rejected' and the submitting user should receive a notification.
        
        Note: This test verifies the status change. User notification requires a bot instance
        and is tested separately.
        
        Validates: Requirements 3.3
        """
        from bot.services.user_service import register_user
        from bot.services.confession_service import create_confession, reject_confession
        
        # Ensure user and admin have different telegram IDs
        if user_telegram_id == admin_telegram_id:
            admin_telegram_id = user_telegram_id + 1
        
        # Register a user and an admin
        user = register_user(user_telegram_id, "Test User")
        admin = register_user(admin_telegram_id, "Admin User")
        admin.is_admin = True
        admin.save()
        
        # Create a pending confession
        confession = create_confession(user, confession_text)
        self.assertEqual(confession.status, 'pending')
        
        # Reject the confession
        rejected_confession = reject_confession(confession, admin)
        
        # Verify status changed to rejected
        self.assertEqual(rejected_confession.status, 'rejected')
        
        # Verify reviewed_by is set to admin
        self.assertEqual(rejected_confession.reviewed_by, admin)
        
        # Verify reviewed_at is set
        self.assertIsNotNone(rejected_confession.reviewed_at)
        
        # Verify the confession is still in the database
        from bot.models import Confession
        self.assertTrue(Confession.objects.filter(id=confession.id).exists())



class CommentCreationTests(TestCase):
    """Tests for comment creation functionality"""
    
    # Feature: anonymous-confession-bot, Property 7: Comment creation links to confession
    @given(
        user_telegram_id=st.integers(min_value=1, max_value=9999999999),
        confession_text=st.text(min_size=1, max_size=4096),
        comment_text=st.text(min_size=1, max_size=1000)
    )
    @settings(max_examples=100)
    def test_comment_creation_links_to_confession(self, user_telegram_id, confession_text, comment_text):
        """
        Property 7: Comment creation links to confession
        For any approved confession and registered user, creating a comment should 
        result in a comment record linked to both the confession and the user.
        Validates: Requirements 5.3
        """
        from bot.services.user_service import register_user
        from bot.services.confession_service import create_confession, approve_confession
        from bot.services.comment_service import create_comment
        from bot.models import Comment
        
        # Register a user
        user = register_user(user_telegram_id, "Test User")
        
        # Create and approve a confession
        confession = create_confession(user, confession_text)
        admin = User.objects.create(
            username=f"admin_{user_telegram_id}",
            telegram_id=user_telegram_id + 1,
            first_name="Admin",
            is_admin=True
        )
        approve_confession(confession, admin)
        
        # Get initial comment count
        initial_comment_count = Comment.objects.filter(confession=confession).count()
        initial_user_comments = user.total_comments
        
        # Create a comment
        comment = create_comment(user, confession, comment_text)
        
        # Verify exactly one comment was created
        final_comment_count = Comment.objects.filter(confession=confession).count()
        self.assertEqual(final_comment_count, initial_comment_count + 1)
        
        # Verify the comment is linked to the confession
        self.assertEqual(comment.confession, confession)
        
        # Verify the comment is linked to the user
        self.assertEqual(comment.user, user)
        
        # Verify the comment text matches
        self.assertEqual(comment.text, comment_text)
        
        # Verify user's comment count incremented
        user.refresh_from_db()
        self.assertEqual(user.total_comments, initial_user_comments + 1)



class ReactionUniquenessTests(TestCase):
    """Tests for reaction uniqueness functionality"""
    
    # Feature: anonymous-confession-bot, Property 8: Reaction uniqueness per user
    @given(
        user_telegram_id=st.integers(min_value=1, max_value=9999999999),
        commenter_telegram_id=st.integers(min_value=1, max_value=9999999999),
        confession_text=st.text(min_size=1, max_size=4096),
        comment_text=st.text(min_size=1, max_size=1000),
        reactions=st.lists(
            st.sampled_from(['like', 'dislike', 'report']),
            min_size=2,
            max_size=5
        )
    )
    @settings(max_examples=100)
    def test_reaction_uniqueness_per_user(self, user_telegram_id, commenter_telegram_id, 
                                          confession_text, comment_text, reactions):
        """
        Property 8: Reaction uniqueness per user
        For any comment and user, adding multiple reactions should result in only 
        the most recent reaction being stored.
        Validates: Requirements 5.6, 5.7
        """
        from bot.services.user_service import register_user
        from bot.services.confession_service import create_confession, approve_confession
        from bot.services.comment_service import create_comment, add_reaction
        from bot.models import Reaction
        
        # Ensure user and commenter have different telegram IDs
        if user_telegram_id == commenter_telegram_id:
            commenter_telegram_id = user_telegram_id + 1
        
        # Register users
        user = register_user(user_telegram_id, "Test User")
        commenter = register_user(commenter_telegram_id, "Commenter")
        
        # Create and approve a confession
        confession = create_confession(commenter, confession_text)
        admin = User.objects.create(
            username=f"admin_{user_telegram_id}",
            telegram_id=user_telegram_id + 999999,
            first_name="Admin",
            is_admin=True
        )
        approve_confession(confession, admin)
        
        # Create a comment
        comment = create_comment(commenter, confession, comment_text)
        
        # Add multiple reactions from the same user
        for reaction_type in reactions:
            add_reaction(user, comment, reaction_type)
        
        # Verify only one reaction exists for this user-comment pair
        reaction_count = Reaction.objects.filter(comment=comment, user=user).count()
        self.assertEqual(reaction_count, 1)
        
        # Verify the stored reaction is the most recent one
        stored_reaction = Reaction.objects.get(comment=comment, user=user)
        self.assertEqual(stored_reaction.reaction_type, reactions[-1])
        
        # Verify the comment's reaction counts are correct
        comment.refresh_from_db()
        
        # Count expected reactions based on the sequence
        expected_likes = 1 if reactions[-1] == 'like' else 0
        expected_dislikes = 1 if reactions[-1] == 'dislike' else 0
        expected_reports = 1 if reactions[-1] == 'report' else 0
        
        self.assertEqual(comment.like_count, expected_likes)
        self.assertEqual(comment.dislike_count, expected_dislikes)
        self.assertEqual(comment.report_count, expected_reports)


class InvalidCommandTests(TestCase):
    """Tests for invalid command handling"""
    
    # Feature: anonymous-confession-bot, Property 11: Invalid command provides helpful feedback
    @given(
        command_suffix=st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122),  # lowercase letters
            min_size=1, 
            max_size=20
        )
    )
    @settings(max_examples=100)
    def test_invalid_command_provides_feedback(self, command_suffix):
        """
        Property 11: Invalid command provides helpful feedback
        For any unrecognized command sent by a user, the system should respond with 
        an error message and suggest valid commands.
        Validates: Requirements 8.1
        """
        from unittest.mock import Mock, MagicMock
        from bot.bot import handle_unknown_command
        
        # Create an invalid command by prefixing with /invalid_
        invalid_command = f"/invalid_{command_suffix}"
        
        # Skip if by chance we generated a valid command
        valid_commands = [
            '/start', '/help', '/register', '/confess', '/anonymous_on', 
            '/anonymous_off', '/profile', '/myconfessions', '/mycomments',
            '/pending', '/stats', '/delete', '/comment', '/comments'
        ]
        if invalid_command in valid_commands:
            return
        
        # Create a mock message object
        mock_message = Mock()
        mock_message.text = invalid_command
        mock_message.from_user = Mock()
        mock_message.from_user.id = 12345
        mock_message.from_user.first_name = "Test User"
        
        # Create a mock bot to capture the response
        response_text = None
        
        def capture_reply(message, text):
            nonlocal response_text
            response_text = text
        
        # Temporarily replace bot.reply_to
        import bot.bot as bot_module
        original_reply_to = bot_module.bot.reply_to
        bot_module.bot.reply_to = capture_reply
        
        try:
            # Call the handler
            handle_unknown_command(mock_message)
            
            # Verify response was sent
            self.assertIsNotNone(response_text)
            
            # Verify response contains error indication
            self.assertTrue(
                'unknown' in response_text.lower() or 
                'not recognize' in response_text.lower() or
                'invalid' in response_text.lower() or
                "don't recognize" in response_text.lower(),
                f"Response should indicate command is unknown: {response_text}"
            )
            
            # Verify response suggests valid commands
            self.assertTrue(
                '/register' in response_text or 
                '/help' in response_text or
                'available commands' in response_text.lower(),
                f"Response should suggest valid commands: {response_text}"
            )
            
        finally:
            # Restore original bot.reply_to
            bot_module.bot.reply_to = original_reply_to


class AdminPermissionTests(TestCase):
    """Tests for admin permission enforcement"""
    
    # Feature: anonymous-confession-bot, Property 12: Admin-only actions enforce permissions
    @given(
        non_admin_telegram_id=st.integers(min_value=1, max_value=9999999999),
        admin_command=st.sampled_from(['pending', 'stats', 'delete'])
    )
    @settings(max_examples=100)
    def test_admin_only_actions_enforce_permissions(self, non_admin_telegram_id, admin_command):
        """
        Property 12: Admin-only actions enforce permissions
        For any admin-only command sent by a non-admin user, the system should reject 
        the action and inform the user of insufficient permissions.
        Validates: Requirements 8.3
        """
        from unittest.mock import Mock
        from bot.bot import pending_command, stats_command, delete_command
        from bot.services.user_service import register_user
        from django.conf import settings
        
        # Ensure the test user is not in the ADMINS list
        # We'll create a user that is definitely not an admin
        if non_admin_telegram_id in settings.ADMINS:
            non_admin_telegram_id = non_admin_telegram_id + 1
            # Keep incrementing until we find a non-admin ID
            while non_admin_telegram_id in settings.ADMINS:
                non_admin_telegram_id += 1
        
        # Register a non-admin user
        user = register_user(non_admin_telegram_id, "Non Admin User")
        user.is_admin = False
        user.save()
        
        # Create a mock message object
        mock_message = Mock()
        mock_message.text = f"/{admin_command}"
        mock_message.from_user = Mock()
        mock_message.from_user.id = non_admin_telegram_id
        mock_message.from_user.first_name = "Non Admin User"
        
        # Create a mock bot to capture the response
        response_text = None
        
        def capture_reply(message, text):
            nonlocal response_text
            response_text = text
        
        # Temporarily replace bot.reply_to
        import bot.bot as bot_module
        original_reply_to = bot_module.bot.reply_to
        bot_module.bot.reply_to = capture_reply
        
        try:
            # Call the appropriate handler based on the command
            if admin_command == 'pending':
                pending_command(mock_message)
            elif admin_command == 'stats':
                stats_command(mock_message)
            elif admin_command == 'delete':
                delete_command(mock_message)
            
            # Verify response was sent
            self.assertIsNotNone(response_text, f"No response for /{admin_command} command")
            
            # Verify response indicates permission denied
            self.assertTrue(
                'permission' in response_text.lower() or 
                'admin' in response_text.lower() or
                "don't have" in response_text.lower() or
                'not allowed' in response_text.lower() or
                'insufficient' in response_text.lower(),
                f"Response should indicate permission denied for /{admin_command}: {response_text}"
            )
            
            # Verify response contains error indicator (❌)
            self.assertTrue(
                '❌' in response_text,
                f"Response should contain error indicator for /{admin_command}: {response_text}"
            )
            
        finally:
            # Restore original bot.reply_to
            bot_module.bot.reply_to = original_reply_to



class DatabaseRetryTests(TestCase):
    """Tests for database connection retry functionality"""
    
    # Feature: anonymous-confession-bot, Property 10: Database connection retry on failure
    @given(
        num_failures=st.integers(min_value=1, max_value=2),
        initial_delay=st.floats(min_value=0.01, max_value=0.1),
        backoff_factor=st.floats(min_value=1.5, max_value=3.0)
    )
    @settings(max_examples=100, deadline=None)
    def test_database_retry_on_failure(self, num_failures, initial_delay, backoff_factor):
        """
        Property 10: Database connection retry on failure
        For any database connection failure, the system should attempt to reconnect 
        up to three times before raising an error.
        Validates: Requirements 7.2
        """
        from bot.utils import retry_db_operation
        from django.db import OperationalError
        from unittest.mock import Mock
        
        # Track call count and timing
        call_count = 0
        call_times = []
        start_time = time.time()
        
        @retry_db_operation(max_retries=3, initial_delay=initial_delay, backoff_factor=backoff_factor)
        def failing_db_operation():
            nonlocal call_count
            call_count += 1
            call_times.append(time.time() - start_time)
            
            if call_count <= num_failures:
                raise OperationalError("Database connection failed")
            
            return "success"
        
        # Test case 1: Operation succeeds after num_failures attempts
        if num_failures < 3:
            result = failing_db_operation()
            
            # Verify the operation was called num_failures + 1 times (failures + success)
            self.assertEqual(call_count, num_failures + 1)
            
            # Verify the operation eventually succeeded
            self.assertEqual(result, "success")
            
            # Verify exponential backoff was applied
            if num_failures > 0:
                # Check that delays increase exponentially
                for i in range(1, len(call_times)):
                    time_diff = call_times[i] - call_times[i-1]
                    # Allow some tolerance for timing variations
                    expected_delay = initial_delay * (backoff_factor ** (i-1))
                    # Verify delay is at least 80% of expected (accounting for execution time)
                    self.assertGreaterEqual(time_diff, expected_delay * 0.8)
        
        # Test case 2: Operation fails all 3 attempts
        else:
            call_count = 0
            call_times = []
            start_time = time.time()
            
            @retry_db_operation(max_retries=3, initial_delay=initial_delay, backoff_factor=backoff_factor)
            def always_failing_db_operation():
                nonlocal call_count
                call_count += 1
                call_times.append(time.time() - start_time)
                raise OperationalError("Database connection failed")
            
            # Verify that after 3 attempts, the exception is raised
            with self.assertRaises(OperationalError):
                always_failing_db_operation()
            
            # Verify the operation was called exactly 3 times
            self.assertEqual(call_count, 3)
            
            # Verify exponential backoff was applied between attempts
            for i in range(1, len(call_times)):
                time_diff = call_times[i] - call_times[i-1]
                expected_delay = initial_delay * (backoff_factor ** (i-1))
                # Verify delay is at least 80% of expected
                self.assertGreaterEqual(time_diff, expected_delay * 0.8)
    
    @given(
        telegram_id=st.integers(min_value=1, max_value=9999999999)
    )
    @settings(max_examples=100)
    def test_retry_decorator_with_real_db_operation(self, telegram_id):
        """
        Test that the retry decorator works with real database operations.
        This test verifies that successful operations complete without retries.
        """
        from bot.utils import retry_db_operation
        from bot.services.user_service import register_user
        
        call_count = 0
        
        @retry_db_operation(max_retries=3)
        def register_user_with_retry():
            nonlocal call_count
            call_count += 1
            return register_user(telegram_id, "Test User")
        
        # Execute the operation
        user = register_user_with_retry()
        
        # Verify the operation succeeded
        self.assertIsNotNone(user)
        self.assertEqual(user.telegram_id, telegram_id)
        
        # Verify the operation was called only once (no retries needed)
        self.assertEqual(call_count, 1)
