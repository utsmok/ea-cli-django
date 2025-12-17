import os
from pathlib import Path

import environ
from dotenv import load_dotenv

# Minimal Django settings to bootstrap project as in refactor-plan
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent  # c:\dev\ea-cli-django (root of project)

# Load .env using python-dotenv (handles spaces around = better)
load_dotenv(PROJECT_ROOT / ".env")

env = environ.Env(DEBUG=(bool, False))
# Note: we intentionally do not call django-environ's `read_env()` here because
# it is stricter about whitespace around '=' than python-dotenv, and can emit
# noisy warnings. Values from `.env` are already loaded into `os.environ`.

SECRET_KEY = env("SECRET_KEY", default="dev-secret-key")
DEBUG = env("DEBUG")
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


# DATABASE configuration, support DATABASE_URL for Docker/Postgres
# When running from host, 'db' hostname won't resolve, so we replace it with 'localhost'
_db_url = os.getenv(
    "DATABASE_URL", "postgres://admin:dev_password@localhost:5432/copyright_db"
)
# If 'db:' appears in URL (Docker internal hostname), replace with 'localhost:'
if "@db:" in _db_url:
    _db_url = _db_url.replace("@db:", "@localhost:")
DATABASES = {"default": env.db_url_config(_db_url)}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# TASKS configuration as provided in the plan
TASKS = {
    "default": {
        "BACKEND": "django_redis_tasks.backend.RedisBackend",
        "OPTIONS": {
            "connection_string": os.environ.get(
                "REDIS_URL", "redis://localhost:6379/0"
            ),
            "queue_name": "default",
        },
    }
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

# Canvas LMS API Configuration
CANVAS_API_URL = os.getenv("CANVAS_API_URL", "https://utwente.instructure.com/api/v1")
# Support both CANVAS_API_TOKEN and CANVAS_API_KEY (legacy name)
CANVAS_API_TOKEN = os.getenv("CANVAS_API_TOKEN") or os.getenv("CANVAS_API_KEY", "")

# PDF Download Directory
PDF_DOWNLOAD_DIR = BASE_DIR / "documents" / "downloads"
# Ensure directory exists
PDF_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# File Existence Check Settings
FILE_EXISTS_TTL_DAYS = env.int("FILE_EXISTS_TTL_DAYS", default=7)
FILE_EXISTS_RATE_LIMIT_DELAY = env.float("FILE_EXISTS_RATE_LIMIT_DELAY", default=0.05)
