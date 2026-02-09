"""
Test interaction tracking integration in bot handlers.
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.test_settings')
django.setup()

import pytest
from unittest.mock import Mock, patch, MagicMock
from bot.models import User, UserInteraction
from bot.services.analytics_service import AnalyticsService
from telebot.types import Message, CallbackQuery
from datetime import datetime


@pytest.mark.django_db
def test_track_interaction_helper():
    """Test the track_interaction helper function."""
    print("Testing track_interaction helper...")
    
    # Create a test user
    user = User.objects.create(
        telegram_id=12345,
        username='testuser',
        first_name='Test',
        password='test'
    )
    
    # Import the tracking function
    from bot.bot import track_interaction
    
    # Track an interaction
    track_interaction(user.telegram_id, 'test_interaction')
    
    # Verify interaction was created
    interactions = UserInteraction.objects.filter(user=user, interaction_type='test_interaction')
    assert interactions.count() == 1, f"Expected 1 interaction, got {interactions.count()}"
    
    print("✓ track_interaction helper works correctly")
    
    # Cleanup
    user.delete()


@pytest.mark.django_db
def test_track_message_interaction():
    """Test message interaction tracking."""
    print("Testing track_message_interaction...")
    
    # Create a test user
    user = User.objects.create(
        telegram_id=12346,
        username='testuser2',
        first_name='Test2',
        password='test'
    )
    
    # Import the tracking function
    from bot.bot import track_message_interaction
    
    # Create a mock message
    mock_message = Mock(spec=Message)
    mock_message.from_user = Mock()
    mock_message.from_user.id = user.telegram_id
    
    # Track the message
    track_message_interaction(mock_message)
    
    # Verify interaction was created
    interactions = UserInteraction.objects.filter(user=user, interaction_type='message')
    assert interactions.count() == 1, f"Expected 1 message interaction, got {interactions.count()}"
    
    print("✓ track_message_interaction works correctly")
    
    # Cleanup
    user.delete()


@pytest.mark.django_db
def test_track_command_interaction():
    """Test command interaction tracking."""
    print("Testing track_command_interaction...")
    
    # Create a test user
    user = User.objects.create(
        telegram_id=12347,
        username='testuser3',
        first_name='Test3',
        password='test'
    )
    
    # Import the tracking function
    from bot.bot import track_command_interaction
    
    # Create a mock message
    mock_message = Mock(spec=Message)
    mock_message.from_user = Mock()
    mock_message.from_user.id = user.telegram_id
    
    # Track the command
    track_command_interaction(mock_message, 'start')
    
    # Verify interaction was created
    interactions = UserInteraction.objects.filter(user=user, interaction_type='command_start')
    assert interactions.count() == 1, f"Expected 1 command interaction, got {interactions.count()}"
    
    print("✓ track_command_interaction works correctly")
    
    # Cleanup
    user.delete()


@pytest.mark.django_db
def test_track_button_interaction():
    """Test button interaction tracking."""
    print("Testing track_button_interaction...")
    
    # Create a test user
    user = User.objects.create(
        telegram_id=12348,
        username='testuser4',
        first_name='Test4',
        password='test'
    )
    
    # Import the tracking function
    from bot.bot import track_button_interaction
    
    # Create a mock callback query
    mock_call = Mock(spec=CallbackQuery)
    mock_call.from_user = Mock()
    mock_call.from_user.id = user.telegram_id
    
    # Track the button click
    track_button_interaction(mock_call, 'like_comment')
    
    # Verify interaction was created
    interactions = UserInteraction.objects.filter(user=user, interaction_type='button_like_comment')
    assert interactions.count() == 1, f"Expected 1 button interaction, got {interactions.count()}"
    
    print("✓ track_button_interaction works correctly")
    
    # Cleanup
    user.delete()


@pytest.mark.django_db
def test_tracking_non_blocking():
    """Test that tracking failures don't block bot operations."""
    print("Testing non-blocking behavior...")
    
    # Import the tracking function
    from bot.bot import track_interaction
    
    # Try to track for a non-existent user - should not raise exception
    try:
        track_interaction(99999999, 'test_interaction')
        print("✓ Tracking failures don't block operations")
    except Exception as e:
        print(f"✗ Tracking raised exception: {e}")
        raise


if __name__ == '__main__':
    print("Running interaction tracking tests...\n")
    
    try:
        test_track_interaction_helper()
        test_track_message_interaction()
        test_track_command_interaction()
        test_track_button_interaction()
        test_tracking_non_blocking()
        
        print("\n✅ All interaction tracking tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
