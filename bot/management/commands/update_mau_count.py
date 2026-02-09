"""
Django management command to manually update the monthly active users count.
This command recalculates the MAU count and displays statistics.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from bot.models import UserInteraction
from bot.services.analytics_service import AnalyticsService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Manually update and display the monthly active users count'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Display detailed statistics',
        )
        parser.add_argument(
            '--no-cache',
            action='store_true',
            help='Skip caching the result',
        )

    def handle(self, *args, **options):
        """Execute the command"""
        verbose = options['verbose']
        no_cache = options['no_cache']
        
        self.stdout.write('Calculating monthly active users count...')
        
        try:
            # Clear cache if no-cache option is set
            if no_cache:
                AnalyticsService.clear_cache()
            
            # Get the MAU count
            mau_count = AnalyticsService.get_monthly_active_users_count()
            formatted_count = AnalyticsService.format_user_count(mau_count)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Monthly Active Users: {mau_count} ({formatted_count})'
                )
            )
            
            if verbose:
                # Display detailed statistics
                self.stdout.write('\n' + '='*50)
                self.stdout.write('DETAILED STATISTICS')
                self.stdout.write('='*50)
                
                # Calculate time boundaries
                now = timezone.now()
                one_day_ago = now - timedelta(days=1)
                seven_days_ago = now - timedelta(days=7)
                thirty_days_ago = now - timedelta(days=30)
                
                # Daily active users
                dau = UserInteraction.objects.filter(
                    timestamp__gte=one_day_ago
                ).values('user').distinct().count()
                
                # Weekly active users
                wau = UserInteraction.objects.filter(
                    timestamp__gte=seven_days_ago
                ).values('user').distinct().count()
                
                # Total interactions in last 30 days
                total_interactions = UserInteraction.objects.filter(
                    timestamp__gte=thirty_days_ago
                ).count()
                
                # Interaction types breakdown
                from django.db.models import Count
                interaction_types = UserInteraction.objects.filter(
                    timestamp__gte=thirty_days_ago
                ).values('interaction_type').annotate(
                    count=Count('id')
                ).order_by('-count')
                
                self.stdout.write(f'\nDaily Active Users (24h): {dau}')
                self.stdout.write(f'Weekly Active Users (7d): {wau}')
                self.stdout.write(f'Monthly Active Users (30d): {mau_count}')
                self.stdout.write(f'\nTotal Interactions (30d): {total_interactions}')
                
                if mau_count > 0:
                    avg_interactions = total_interactions / mau_count
                    self.stdout.write(f'Avg Interactions per User: {avg_interactions:.2f}')
                
                self.stdout.write('\nInteraction Types (30d):')
                for item in interaction_types:
                    interaction_type = item['interaction_type']
                    count = item['count']
                    percentage = (count / total_interactions * 100) if total_interactions > 0 else 0
                    self.stdout.write(f'  {interaction_type}: {count} ({percentage:.1f}%)')
                
                # All-time statistics
                self.stdout.write('\n' + '-'*50)
                self.stdout.write('ALL-TIME STATISTICS')
                self.stdout.write('-'*50)
                
                total_users = UserInteraction.objects.values('user').distinct().count()
                total_all_time = UserInteraction.objects.count()
                
                self.stdout.write(f'Total Users (all-time): {total_users}')
                self.stdout.write(f'Total Interactions (all-time): {total_all_time}')
                
                if total_users > 0:
                    avg_all_time = total_all_time / total_users
                    self.stdout.write(f'Avg Interactions per User (all-time): {avg_all_time:.2f}')
                
                # Oldest and newest interactions
                oldest = UserInteraction.objects.order_by('timestamp').first()
                newest = UserInteraction.objects.order_by('-timestamp').first()
                
                if oldest:
                    self.stdout.write(f'\nOldest Interaction: {oldest.timestamp}')
                if newest:
                    self.stdout.write(f'Newest Interaction: {newest.timestamp}')
                
                self.stdout.write('='*50 + '\n')
            
            logger.info(f'MAU count updated: {mau_count}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error calculating MAU count: {str(e)}')
            )
            logger.error(f'Error calculating MAU count: {e}', exc_info=True)
