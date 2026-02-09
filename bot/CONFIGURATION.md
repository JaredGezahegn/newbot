# Monthly Users Count Feature - Configuration Guide

This document describes the configuration options for the monthly users count feature.

## Cache Configuration

The MAU (Monthly Active Users) count is cached to improve performance and reduce database load.

### Cache Timeout

**Setting**: `AnalyticsService.CACHE_TIMEOUT`  
**Default**: `3600` seconds (1 hour)  
**Location**: `bot/services/analytics_service.py`

To modify the cache timeout, update the `CACHE_TIMEOUT` constant in the `AnalyticsService` class:

```python
class AnalyticsService:
    CACHE_KEY_MAU = 'monthly_active_users_count'
    CACHE_TIMEOUT = 3600  # Change this value (in seconds)
```

**Recommendations**:
- For high-traffic bots: 1800-3600 seconds (30 minutes to 1 hour)
- For low-traffic bots: 7200-14400 seconds (2-4 hours)
- For development/testing: 60-300 seconds (1-5 minutes)

## Display Configuration

The feature provides flexible display options for showing the monthly users count.

### Default Display Configuration

**Location**: `bot/services/analytics_service.py`

```python
DEFAULT_DISPLAY_CONFIG = {
    'format': 'abbreviated',  # 'abbreviated' (1.2K) or 'full' (1200)
    'position': 'inline',  # 'inline' or 'separate_line'
    'label': 'monthly active users',  # Label text to display
    'show_label': True,  # Whether to show the label
    'hide_low_counts': False,  # Hide counts under threshold
    'low_count_threshold': 10  # Threshold for low counts
}
```

### Display Options

#### Format
- **abbreviated**: Displays counts with K/M suffixes (e.g., "1.5K", "2.3M")
- **full**: Displays the exact count (e.g., "1500", "2300000")

#### Position
- **inline**: Displays count and label on the same line (e.g., "1.5K monthly active users")
- **separate_line**: Displays label and count on separate lines

#### Hide Low Counts
- **hide_low_counts**: When `True`, hides the count if it's below the threshold
- **low_count_threshold**: The minimum count to display (default: 10)

### Usage Example

```python
from bot.services.analytics_service import AnalyticsService

# Get MAU count
mau_count = AnalyticsService.get_monthly_active_users_count()

# Format with custom configuration
display = AnalyticsService.format_display(mau_count, {
    'format': 'full',
    'position': 'separate_line',
    'show_label': True,
    'hide_low_counts': True,
    'low_count_threshold': 50
})
```

## Bot Description Updates

The feature can automatically update the bot's description to include the monthly users count.

### Bot Description Configuration

**Setting**: `BOT_DESCRIPTION_CONFIG`  
**Location**: `core/settings.py`

```python
BOT_DESCRIPTION_CONFIG = {
    'enabled': False,  # Set to True to enable automatic description updates
    'description_template': 'Anonymous Confession Bot - {count} monthly active users',
    'update_interval': 3600,  # Minimum seconds between updates (1 hour)
    'retry_attempts': 3,  # Number of retry attempts on failure
    'retry_delay': 60,  # Seconds to wait between retries
}
```

### Configuration Options

- **enabled**: Enable/disable automatic bot description updates
- **description_template**: Template string with `{count}` placeholder for the formatted count
- **update_interval**: Minimum time (in seconds) between description updates to avoid rate limiting
- **retry_attempts**: Number of times to retry if the update fails
- **retry_delay**: Delay (in seconds) between retry attempts

### Usage

```python
from bot.services.analytics_service import AnalyticsService

# Update bot description with current MAU count
result = AnalyticsService.update_bot_description_with_count()

if result['success']:
    print(f"Description updated: {result['message']}")
else:
    print(f"Update failed: {result['message']}")
```

## Database Indexes

The `UserInteraction` model includes optimized indexes for efficient querying.

### Existing Indexes

**Location**: `bot/models.py`

```python
class UserInteraction(models.Model):
    # ... fields ...
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]
```

### Production Recommendations

For production deployments with high traffic:

1. **Monitor query performance**: Use Django Debug Toolbar or database query logs
2. **Consider composite indexes**: If filtering by interaction_type frequently
3. **Partition by date**: For very large datasets, consider table partitioning by month

### Adding Custom Indexes

If you need additional indexes, create a new migration:

```bash
python manage.py makemigrations bot --empty --name add_custom_indexes
```

Then edit the migration file to add your indexes.

## Monitoring

### Logging Configuration

The analytics service uses Django's logging framework. Logs are configured in `core/settings.py`:

```python
LOGGING = {
    # ... other config ...
    'loggers': {
        'bot.services.analytics_service': {
            'handlers': ['console', 'file_analytics', 'file_error'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

### Log Files

- **Analytics logs**: `logs/analytics.log` - Contains MAU calculation and caching events
- **Error logs**: `logs/error.log` - Contains error messages and stack traces

### Monitoring Metrics

Key metrics to monitor:

1. **Cache hit rate**: Check logs for "Returning cached MAU count" vs "Calculated MAU count"
2. **Interaction tracking failures**: Monitor error logs for failed `track_user_interaction` calls
3. **Database query performance**: Monitor query execution time for MAU calculations
4. **Bot description update failures**: Check for rate limiting or permission errors

### Performance Monitoring

```python
# Example: Monitor cache performance
from django.core.cache import cache
from bot.services.analytics_service import AnalyticsService

# Check if cache is working
cache_key = AnalyticsService.CACHE_KEY_MAU
cached_value = cache.get(cache_key)

if cached_value is not None:
    print(f"Cache hit: {cached_value}")
else:
    print("Cache miss - will query database")
```

## Data Retention

### Cleanup Old Interactions

To prevent database bloat, periodically clean up old interaction records:

```python
from bot.services.analytics_service import AnalyticsService

# Clean up interactions older than 90 days
deleted_count = AnalyticsService.cleanup_old_interactions(days=90)
print(f"Deleted {deleted_count} old interactions")
```

### Automated Cleanup

Use Django management commands for automated cleanup:

```bash
# Clean up interactions older than 90 days
python manage.py cleanup_old_interactions --days 90

# Regenerate MAU cache
python manage.py regenerate_mau_cache

# Update MAU count manually
python manage.py update_mau_count
```

### Recommended Retention Periods

- **Minimum**: 60 days (to ensure 30-day MAU calculation has buffer)
- **Recommended**: 90 days (provides historical data for analysis)
- **Maximum**: 180 days (for long-term trend analysis)

## Testing

### Running Tests

```bash
# Run all integration tests
python manage.py test bot.test_integration_workflow --settings=core.test_settings

# Run specific test class
python manage.py test bot.test_integration_workflow.CompleteWorkflowIntegrationTests --settings=core.test_settings

# Run specific test method
python manage.py test bot.test_integration_workflow.CompleteWorkflowIntegrationTests.test_end_to_end_interaction_tracking_and_display --settings=core.test_settings
```

### Test Configuration

Tests use a separate settings file (`core/test_settings.py`) with:
- SQLite database for faster test execution
- Simplified logging configuration
- Disabled external API calls

## Deployment Checklist

Before deploying to production:

- [ ] Configure cache timeout based on traffic patterns
- [ ] Set up database indexes (already included in migrations)
- [ ] Configure logging and monitoring
- [ ] Set up automated cleanup cron job
- [ ] Test bot description updates (if enabled)
- [ ] Verify privacy settings (no PII in UserInteraction model)
- [ ] Run integration tests
- [ ] Monitor initial performance and adjust cache timeout if needed

## Troubleshooting

### Cache Not Working

**Symptom**: Every MAU request queries the database

**Solutions**:
1. Check cache backend configuration in `settings.py`
2. Verify cache service is running (Redis, Memcached, etc.)
3. Check logs for cache errors

### High Database Load

**Symptom**: Slow MAU calculations, high database CPU

**Solutions**:
1. Increase cache timeout
2. Verify indexes are created: `python manage.py sqlmigrate bot 0005`
3. Consider database query optimization
4. Implement read replicas for analytics queries

### Bot Description Updates Failing

**Symptom**: Description not updating, rate limit errors

**Solutions**:
1. Increase `update_interval` in configuration
2. Check bot permissions with BotFather
3. Verify `BOT_TOKEN` is correct
4. Check logs for specific error messages

## Support

For issues or questions:
1. Check logs in `logs/analytics.log` and `logs/error.log`
2. Review this configuration guide
3. Check the design document at `.kiro/specs/monthly-users-count/design.md`
4. Review test cases in `bot/test_integration_workflow.py` for usage examples
