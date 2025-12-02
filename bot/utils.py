"""
Utility functions for the bot application.
"""
import time
import logging
from functools import wraps
from django.db import OperationalError, InterfaceError, connection

logger = logging.getLogger(__name__)


def check_database_connection():
    """
    Check if database connection is working.
    
    This function can be decorated with @retry_db_operation to ensure
    database connectivity with automatic retries.
    
    Returns:
        bool: True if connection is successful
    
    Raises:
        OperationalError: If database connection fails
    """
    connection.ensure_connection()
    return True


def retry_db_operation(max_retries=3, initial_delay=1.0, backoff_factor=2.0):
    """
    Decorator to retry database operations with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        backoff_factor: Multiplier for delay between retries (default: 2.0)
    
    Returns:
        Decorated function that retries on database connection errors
    
    Raises:
        OperationalError or InterfaceError: If all retry attempts fail
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    # Close existing connection if it's unusable
                    if connection.connection is not None and not connection.is_usable():
                        connection.close()
                    
                    # Execute the function
                    return func(*args, **kwargs)
                    
                except (OperationalError, InterfaceError) as e:
                    last_exception = e
                    attempt_num = attempt + 1
                    
                    if attempt_num < max_retries:
                        logger.warning(
                            f"Database operation failed (attempt {attempt_num}/{max_retries}): {str(e)}. "
                            f"Retrying in {delay} seconds..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"Database operation failed after {max_retries} attempts: {str(e)}"
                        )
            
            # If we've exhausted all retries, raise the last exception
            raise last_exception
        
        return wrapper
    return decorator
