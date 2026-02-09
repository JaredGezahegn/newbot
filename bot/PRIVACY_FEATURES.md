# Privacy-Preserving Analytics Features

## Overview

The monthly users count feature is designed with privacy as a core principle. This document outlines the privacy-preserving measures implemented in the system.

## Privacy-Preserving Data Storage

### UserInteraction Model

The `UserInteraction` model stores only the minimum necessary metadata:

- **user**: Foreign key reference to User model (no direct PII storage)
- **interaction_type**: Category of interaction (e.g., 'message', 'command', 'button_click')
- **timestamp**: When the interaction occurred

**What is NOT stored:**
- Message content
- User's first name, last name, or username directly
- IP addresses
- Device information
- Location data
- Any other personally identifiable information

### Data Retention Policies

The system implements automatic data retention policies to minimize data storage:

- **Default retention period**: 90 days
- **Automatic cleanup**: Old interaction data is automatically deleted
- **Manual cleanup**: Administrators can run cleanup commands as needed

#### Running Data Cleanup

```bash
# Clean up interactions older than 90 days (default)
python manage.py cleanup_old_interactions

# Clean up interactions older than 60 days
python manage.py cleanup_old_interactions --days 60

# Dry run to see what would be deleted
python manage.py cleanup_old_interactions --dry-run
```

#### Programmatic Cleanup

```python
from bot.services.analytics_service import AnalyticsService

# Clean up interactions older than 90 days
deleted_count = AnalyticsService.cleanup_old_interactions(days=90)
```

## Admin Analytics Without User Exposure

### Anonymous Aggregate Reporting

The `get_admin_analytics_report()` method provides insights without exposing individual user identities:

```python
from bot.services.analytics_service import AnalyticsService

# Get privacy-preserving analytics report
report = AnalyticsService.get_admin_analytics_report()

# Report contains only aggregate data:
# - total_interactions: Total count
# - monthly_active_users: Unique users in last 30 days
# - daily_active_users: Unique users in last 24 hours
# - weekly_active_users: Unique users in last 7 days
# - interaction_types_breakdown: Count by interaction type
```

**Privacy guarantees:**
- No individual user identities are exposed
- No telegram IDs, usernames, or names in reports
- Only aggregate statistics are provided
- All data is anonymized

### Admin Interface

The Django admin interface for UserInteraction is designed with privacy in mind:

- **Read-only access**: Prevents manual manipulation of interaction data
- **Limited display**: Shows only user_id (FK), not full user details
- **Aggregate summary**: Displays privacy-preserving analytics on the admin page
- **Restricted permissions**: Only superusers can delete records

## Testing

The privacy features are validated through property-based tests:

### Property 9: Privacy-preserving interaction storage
Verifies that UserInteraction records contain only necessary metadata and no PII.

### Property 10: Admin analytics anonymity preservation
Verifies that admin analytics reports provide insights without exposing individual user identities.

## Compliance

These privacy features help ensure compliance with:
- GDPR (General Data Protection Regulation)
- CCPA (California Consumer Privacy Act)
- Other privacy regulations requiring data minimization and retention policies

## Best Practices

1. **Regular cleanup**: Schedule regular cleanup of old interaction data
2. **Monitor retention**: Adjust retention periods based on your needs
3. **Audit access**: Regularly audit who has access to interaction data
4. **Document policies**: Maintain clear documentation of data retention policies
5. **User transparency**: Inform users about what data is collected and how long it's retained
