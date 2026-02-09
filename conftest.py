"""
Pytest configuration for Django tests.
"""
import os
import django

# Configure Django settings before running tests
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.test_settings')

# Setup Django
django.setup()
