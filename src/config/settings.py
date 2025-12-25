import os
from pathlib import Path

import environ
from dotenv import load_dotenv

# Minimal Django settings to bootstrap project as in refactor-plan
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent  # c:\dev\ea-cli-django (root of project)

# Load .env using python-dotenv (handles spaces around = better)
load_dotenv(PROJECT_ROOT / ".env")

# Default DEBUG to True for development convenience if .env is missing
env = environ.Env(DEBUG=(bool, True))
# Note: we intentionally do not call django-environ's `read_env()` here because
# it is stricter about whitespace around '=' than python-dotenv, and can emit
# noisy warnings. Values from `.env` are already loaded into `os.environ`.

SECRET_KEY = env("SECRET_KEY", default="dev-secret-key")
DEBUG = env("DEBUG")

# Redirects
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Custom apps
    "apps.users",  # Must be first for AUTH_USER_MODEL
    "apps.core",
    "apps.ingest",
    "apps.dashboard",
    "apps.api",
    "apps.documents",
    "apps.enrichment",
    "apps.classification",
    "apps.steps",
    "apps.settings",  # Settings management
    "django_tasks",
    "django_rq",
]

# Custom User Model
AUTH_USER_MODEL = "users.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Allow same-origin iframes for PDF preview
X_FRAME_OPTIONS = "SAMEORIGIN"

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "config.wsgi.application"


# =============================================================================
# DATABASE Configuration
# =============================================================================
# Supports DATABASE_URL for Docker/Postgres environments
# When running from host, Docker hostnames ('db', 'redis') won't resolve
# Auto-detects Docker environment and adjusts hostnames accordingly

RUNNING_IN_DOCKER = os.path.exists("/.dockerenv")

# Get database URL from environment, or use sensible defaults
# Format: postgres://user:password@host:port/database
_db_url = env(
    "DATABASE_URL",
    default="postgres://admin:dev_password@db:5432/copyright_db"
    if RUNNING_IN_DOCKER
    else "postgres://admin:dev_password@localhost:5432/copyright_db",
)

# Get Redis URL from environment, or use sensible defaults
# Format: redis://host:port/database
_redis_url = env(
    "REDIS_URL",
    default="redis://redis:6379/0" if RUNNING_IN_DOCKER else "redis://localhost:6379/0",
)

# =============================================================================
# REDIS CACHING Configuration
# =============================================================================
# Multi-backend caching strategy:
# - 'default': General caching (sessions, flash messages, temporary data)
# - 'queries': Expensive database query results (filter counts, aggregations)
#
# Both backends use django-redis with compression to minimize memory usage.
# Cache failures are ignored gracefully (app continues working, just slower).
# =============================================================================
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": _redis_url,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # Use environment-specific key prefix to avoid conflicts
            "KEY_PREFIX": f"ea_platform_default_{env('ENV', default='dev')}",
            # Compress large values to save memory (~60% reduction)
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            # Ignore connection errors gracefully (fallback to no cache)
            "IGNORE_EXCEPTIONS": True,
        },
        "TIMEOUT": 300,  # 5 minutes default
    },
    # Separate cache for expensive query results
    "queries": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": _redis_url,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "KEY_PREFIX": f"ea_platform_queries_{env('ENV', default='dev')}",
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "IGNORE_EXCEPTIONS": True,
        },
        # Query results can be cached longer (15 minutes)
        "TIMEOUT": 900,
    },
}

# Cache key prefix for easy identification in Redis CLI
CACHE_KEY_PREFIX = "ea_platform"

# Cache statistics flag (enable for development debugging)
REDIS_CACHE_STATS = env.bool("REDIS_CACHE_STATS", default=True)

DATABASES = {"default": env.db_url_config(_db_url)}
DATABASES["default"]["TEST"] = {
    "NAME": "test_copyright_db_isolated",
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# TASKS configuration
# Django 6 Tasks with django-tasks RQ backend
# Fallback to ImmediateBackend if Redis is not configured
# Use ImmediateBackend for tests or if Redis is not configured
import sys

IS_TESTING = "pytest" in sys.modules

TASKS = {
    "default": {
        "BACKEND": "django_tasks.backends.rq.RQBackend"
        if (_redis_url and not IS_TESTING)
        else "django_tasks.backends.immediate.ImmediateBackend",
    },
}

# RQ_QUEUES for django-rq
RQ_QUEUES = {
    "default": {
        "URL": _redis_url,
        "DEFAULT_TIMEOUT": 3600,
        "JOB_CLASS": "django_tasks.backends.rq.Job",
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

# =============================================================================
# External API Configuration
# =============================================================================

# Canvas LMS API (for PDF downloads and metadata)
# Set CANVAS_API_URL to your Canvas instance URL
# Set CANVAS_API_TOKEN to your Canvas API access token
CANVAS_API_URL = env("CANVAS_API_URL", default="https://utwente.instructure.com/api/v1")
# Support both CANVAS_API_TOKEN and CANVAS_API_KEY (legacy name)
CANVAS_API_TOKEN = env("CANVAS_API_TOKEN", default="") or env(
    "CANVAS_API_KEY", default=""
)

# Osiris Scraper Settings (University of Twente course/teacher data)
# OSIRIS_BASE_URL: The Osiris student portal URL
OSIRIS_BASE_URL = env("OSIRIS_BASE_URL", default="https://utwente.osiris-student.nl")
# OSIRIS_HEADERS: HTTP headers required by the Osiris API
# These are technical headers for API communication and typically don't need changes
OSIRIS_HEADERS = {
    "sec-ch-ua-platform": '"Windows"',
    "authorization": "undefined undefined",
    "cache-control": "no-cache, no-store, must-revalidate, private",
    "pragma": "no-cache",
    "client_type": "web",
    "release_version": "c0d3b6a1d72bf1610166027c903b46fc10580f30",
    "manifest": "24.46_B346_c0d3b6a1",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "taal": "NL",
    "origin": "https//utwente.osiris-student.nl",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "referer": "https//utwente.osiris-student.nl/onderwijscatalogus/extern/cursussen",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
}

# PDF Download Directory
PDF_DOWNLOAD_DIR = BASE_DIR / "documents" / "downloads"
# Ensure directory exists
PDF_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# File Existence Check Settings
FILE_EXISTS_TTL_DAYS = env.int("FILE_EXISTS_TTL_DAYS", default=7)
FILE_EXISTS_RATE_LIMIT_DELAY = env.float("FILE_EXISTS_RATE_LIMIT_DELAY", default=0.05)
