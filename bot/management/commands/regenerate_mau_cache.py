"""
Django management command to regenerate the monthly active users cache.
This command clears the existing cache and recalculates the MAU count.
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache
from bot.services.analytics_service import AnalyticsService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Regenerate the monthly active users cache'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-only',
            action='store_true',
            help='Only clear the cache without regenerating',
        )

    def handle(self, *args, **options):
        """Execute the command"""
        clear_only = options['clear_only']
        
        self.stdout.write('Clearing monthly active users cache...')
        
        # Clear the cache
        AnalyticsService.clear_cache()
        
        self.stdout.write(
            self.style.SUCCESS('✅ Cache cleared successfully')
        )
        
        if clear_only:
            self.stdout.write('Cache will be regenerated on next request')
            return
        
        # Regenerate the cache by calling get_monthly_active_users_count
        self.stdout.write('Regenerating monthly active users count...')
        
        try:
            mau_count = AnalyticsService.get_monthly_active_users_count()
            formatted_count = AnalyticsService.format_user_count(mau_count)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Cache regenerated successfully'
                )
            )
            self.stdout.write(f'Monthly Active Users: {mau_count} ({formatted_count})')
            
            # Verify cache was set
            cached_value = cache.get(AnalyticsService.CACHE_KEY_MAU)
            if cached_value == mau_count:
                self.stdout.write(
                    self.style.SUCCESS('✅ Cache verification passed')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  Cache verification failed: expected {mau_count}, got {cached_value}'
                    )
                )
            
            logger.info(f'MAU cache regenerated: {mau_count}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error regenerating cache: {str(e)}')
            )
            logger.error(f'Error regenerating MAU cache: {e}', exc_info=True)
