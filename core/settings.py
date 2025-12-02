from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

def get_env(key, default=None):
    """Get environment variable with validation"""
    value = os.environ.get(key, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {key}")
    return value

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = get_env("SECRET_KEY")
BOT_TOKEN = get_env("BOT_TOKEN")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "your_bot")  # Bot username without @
WEB_HOOK_URL = os.environ.get("WEB_HOOK_URL", "https://newbot-drab.vercel.app/webhook/")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
ADMINS = [int(admin_id.strip()) for admin_id in os.environ.get("ADMINS", "").split(",") if admin_id.strip()]

DEBUG = False  # Vercel = always production

ALLOWED_HOSTS = [
    "newbot-drab.vercel.app",
    ".vercel.app",
    "localhost",
    "127.0.0.1"
]

CSRF_TRUSTED_ORIGINS = [
    "https://newbot-drab.vercel.app",
    "https://*.vercel.app",
]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "bot",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

AUTH_USER_MODEL = "bot.User"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"


# -----------------------------
# 🔥 FORCE POSTGRES ON VERCEL
# -----------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": get_env("PGDATABASE"),
        "USER": get_env("PGUSER"),
        "PASSWORD": get_env("PGPASSWORD"),
        "HOST": get_env("PGHOST"),
        "PORT": os.environ.get("PGPORT", "5432"),  # Support both direct (5432) and pooler (6543)
        "OPTIONS": {
            "sslmode": "require",
            "connect_timeout": 10,
        },
        "CONN_MAX_AGE": 0,  # Don't persist connections in serverless
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# -----------------------------
# 🔥 STATIC FILES (Vercel Safe)
# -----------------------------
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
