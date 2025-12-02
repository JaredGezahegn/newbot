# Bot Utilities Documentation

## Database Retry Decorator

The `retry_db_operation` decorator provides automatic retry logic with exponential backoff for database operations that may fail due to connection issues.

### Usage

```python
from bot.utils import retry_db_operation

@retry_db_operation(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
def my_database_operation():
    # Your database operation here
    user = User.objects.get(telegram_id=12345)
    return user
```

### Parameters

- `max_retries` (int, default=3): Maximum number of retry attempts
- `initial_delay` (float, default=1.0): Initial delay in seconds before first retry
- `backoff_factor` (float, default=2.0): Multiplier for delay between retries

### Behavior

1. If a database operation raises `OperationalError` or `InterfaceError`, the decorator will:
   - Close the existing connection if it's unusable
   - Wait for the specified delay
   - Retry the operation
   - Increase the delay by the backoff factor for subsequent retries

2. After `max_retries` attempts, the original exception is raised

3. All retry attempts are logged with warnings, and final failures are logged as errors

### Example with Custom Parameters

```python
from bot.utils import retry_db_operation

@retry_db_operation(max_retries=5, initial_delay=0.5, backoff_factor=3.0)
def critical_database_operation():
    # This will retry up to 5 times with delays: 0.5s, 1.5s, 4.5s, 13.5s, 40.5s
    return Confession.objects.filter(status='pending').count()
```

### When to Use

Use this decorator for:
- Critical database operations that must succeed
- Operations that may fail due to temporary connection issues
- Operations in serverless environments where connections may be dropped
- Startup operations that need to establish database connectivity

### When NOT to Use

Avoid using this decorator for:
- Operations that are expected to fail for business logic reasons
- Operations where retrying doesn't make sense (e.g., unique constraint violations)
- Operations that should fail fast
- Operations in tight loops (may cause performance issues)

### Testing

The retry logic is tested with property-based tests that verify:
- Correct number of retry attempts
- Exponential backoff timing
- Successful recovery after transient failures
- Proper exception raising after all retries exhausted

See `bot/tests.py` - `DatabaseRetryTests` for test implementation.
