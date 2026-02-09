"""
Management command to clean up old interaction data.
This implements data retention policies for privacy compliance.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from bot.models import UserInteraction
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up old user interaction data based on retention policy'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days to retain interaction data (default: 90)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        retention_days = options['days']
        dry_run = options['dry_run']
        
        # Calculate the cutoff date
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        # Find interactions older than the retention period
        old_interactions = UserInteraction.objects.filter(timestamp__lt=cutoff_date)
        count = old_interactions.count()
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would delete {count} interactions older than {retention_days} days'
                )
            )
            if count > 0:
                oldest = old_interactions.order_by('timestamp').first()
                newest = old_interactions.order_by('-timestamp').first()
                self.stdout.write(
                    f'  Oldest: {oldest.timestamp}'
                )
                self.stdout.write(
                    f'  Newest: {newest.timestamp}'
                )
        else:
            # Delete old interactions
            deleted_count, _ = old_interactions.delete()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deleted {deleted_count} interactions older than {retention_days} days'
                )
            )
            
            logger.info(f'Cleaned up {deleted_count} old interactions (retention: {retention_days} days)')
        
        # Show current statistics
        remaining_count = UserInteraction.objects.count()
        self.stdout.write(
            f'Remaining interactions in database: {remaining_count}'
        )
