#!/usr/bin/env python
"""
Check if Feedback table exists and run migrations if needed
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection
from django.core.management import call_command

def check_table_exists(table_name):
    """Check if a table exists in the database"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            );
        """, [table_name])
        return cursor.fetchone()[0]

if __name__ == '__main__':
    print("Checking if bot_feedback table exists...")
    
    if check_table_exists('bot_feedback'):
        print("✅ bot_feedback table exists!")
    else:
        print("❌ bot_feedback table does NOT exist!")
        print("\nRunning migrations...")
        try:
            call_command('migrate', 'bot', verbosity=2)
            print("\n✅ Migrations completed successfully!")
        except Exception as e:
            print(f"\n❌ Error running migrations: {e}")
            print("\nPlease run manually:")
            print("python manage.py migrate bot")
