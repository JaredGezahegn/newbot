"""Test settings that use SQLite instead of PostgreSQL"""
import os

# Set environment variables before importing settings
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
os.environ.setdefault("WEB_HOOK_URL", "http://localhost/webhook/")
os.environ.setdefault("PGDATABASE", "test")
os.environ.setdefault("PGUSER", "test")
os.environ.setdefault("PGPASSWORD", "test")
os.environ.setdefault("PGHOST", "localhost")

from .settings import *

# Override database to use SQLite for testing
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Disable debug for tests
DEBUG = True
