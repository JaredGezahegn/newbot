"""
Django management command to update bot description with monthly active users count.
"""
from django.core.management.base import BaseCommand
from bot.services.analytics_service import AnalyticsService


class Command(BaseCommand):
    help = 'Update bot description with monthly active users count'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even if rate limited',
        )
        parser.add_argument(
            '--template',
            type=str,
            help='Custom description template (use {count} as placeholder)',
        )

    def handle(self, *args, **options):
        """Execute the command"""
        self.stdout.write('Updating bot description with monthly active users count...')
        
        # Get configuration
        config = AnalyticsService.get_bot_description_config()
        
        # Override with command options
        if options['force']:
            config['update_interval'] = 0  # Bypass rate limiting
        
        if options['template']:
            config['description_template'] = options['template']
        
        # Ensure updates are enabled for this manual command
        config['enabled'] = True
        
        # Update the bot description
        result = AnalyticsService.update_bot_description_with_count(config=config)
        
        if result['success']:
            self.stdout.write(
                self.style.SUCCESS(f"✅ {result['message']}")
            )
            self.stdout.write(f"Monthly Active Users: {result['count']}")
        else:
            self.stdout.write(
                self.style.ERROR(f"❌ {result['message']}")
            )
            if 'error' in result:
                self.stdout.write(f"Error details: {result['error']}")
            
            # Provide fallback suggestions
            self.stdout.write('\nFallback options:')
            self.stdout.write('1. Display count in bot messages (already implemented in /start, /help, /profile)')
            self.stdout.write('2. Add count to bot username or channel description')
            self.stdout.write('3. Use a pinned message in the channel with the count')
