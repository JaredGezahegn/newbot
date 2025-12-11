#!/usr/bin/env python
"""
Verification script to check if Row Level Security (RLS) is enabled on all tables.
Run this after applying the enable_rls.sql script in Supabase.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection


def check_rls_status():
    """Check if RLS is enabled on all required tables."""
    
    tables_to_check = [
        'bot_user',
        'bot_confession',
        'bot_comment',
        'bot_reaction',
        'django_session',
        'django_admin_log',
        'bot_user_groups',
        'bot_user_user_permissions',
    ]
    
    print("=" * 70)
    print("Row Level Security (RLS) Status Check")
    print("=" * 70)
    print()
    
    query = """
        SELECT 
            tablename, 
            rowsecurity 
        FROM pg_tables 
        WHERE schemaname = 'public' 
          AND tablename = ANY(%s)
        ORDER BY tablename;
    """
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, [tables_to_check])
            results = cursor.fetchall()
            
            if not results:
                print("❌ No tables found. Have you run migrations?")
                print()
                print("Run: python manage.py migrate")
                return False
            
            all_enabled = True
            missing_tables = set(tables_to_check)
            
            print(f"{'Table Name':<35} {'RLS Enabled':<15}")
            print("-" * 70)
            
            for table_name, rls_enabled in results:
                missing_tables.discard(table_name)
                status = "✅ Yes" if rls_enabled else "❌ No"
                print(f"{table_name:<35} {status:<15}")
                
                if not rls_enabled:
                    all_enabled = False
            
            # Check for missing tables
            if missing_tables:
                print()
                print("⚠️  Tables not found in database:")
                for table in sorted(missing_tables):
                    print(f"   - {table}")
                print()
                print("These tables may not exist yet. Run migrations if needed.")
            
            print()
            print("=" * 70)
            
            if all_enabled and not missing_tables:
                print("✅ SUCCESS: RLS is enabled on all tables!")
                print()
                print("Your database is now secure. The Supabase warnings should disappear.")
                return True
            elif all_enabled:
                print("⚠️  PARTIAL: RLS is enabled on existing tables.")
                print()
                print("Some tables don't exist yet. This is normal if you haven't")
                print("run all migrations. Run the RLS script again after migrations.")
                return True
            else:
                print("❌ ACTION REQUIRED: RLS is not enabled on some tables.")
                print()
                print("Next steps:")
                print("1. Open your Supabase SQL Editor")
                print("2. Run the enable_rls.sql script")
                print("3. Run this verification script again")
                return False
                
    except Exception as e:
        print(f"❌ Error checking RLS status: {e}")
        print()
        print("Make sure your database connection is working.")
        return False


def check_policies():
    """Check if RLS policies exist for the tables."""
    
    print()
    print("=" * 70)
    print("Checking RLS Policies")
    print("=" * 70)
    print()
    
    query = """
        SELECT 
            schemaname,
            tablename,
            policyname,
            roles,
            cmd
        FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename LIKE 'bot_%' OR tablename LIKE 'django_%'
        ORDER BY tablename, policyname;
    """
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
            
            if not results:
                print("⚠️  No RLS policies found.")
                print()
                print("You need to run the enable_rls.sql script in Supabase.")
                return False
            
            current_table = None
            policy_count = 0
            
            for schema, table, policy_name, roles, cmd in results:
                if table != current_table:
                    if current_table is not None:
                        print()
                    print(f"📋 Table: {table}")
                    current_table = table
                
                print(f"   └─ {policy_name}")
                print(f"      Roles: {roles}, Command: {cmd}")
                policy_count += 1
            
            print()
            print("=" * 70)
            print(f"✅ Found {policy_count} RLS policies")
            return True
            
    except Exception as e:
        print(f"❌ Error checking policies: {e}")
        return False


if __name__ == "__main__":
    print()
    rls_ok = check_rls_status()
    policies_ok = check_policies()
    
    print()
    print("=" * 70)
    
    if rls_ok and policies_ok:
        print("🎉 All checks passed! Your database security is properly configured.")
        sys.exit(0)
    else:
        print("⚠️  Some checks failed. Review the output above for details.")
        sys.exit(1)
