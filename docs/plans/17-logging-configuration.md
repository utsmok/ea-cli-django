# Task 17: Logging & Configuration Hardcoding

## Overview

Fix logging inconsistencies (standardize on loguru), remove hardcoded configuration values, and fix the GPU/PDF extraction issue with a quick fallback to defaults.

**Current Status:** ❌ **NOT STARTED**
**Priority:** **MEDIUM** (Technical Debt)

## Issues Addressed

### 1. Inconsistent Logging Configuration (High)

**Problem:** The codebase mixes stdlib `logging` and `loguru`. Settings.py uses stdlib logging while services import `from loguru import logger`.

**Files affected:**
- `src/config/settings.py:201-213` - Uses stdlib LOGGING config
- `src/apps/documents/services/download.py:17` - Uses `logging`
- `src/apps/settings/models.py:311` - Uses `logging` inline

**Project standard:** Use `loguru` throughout (as per CLAUDE.md)

### 2. PDF Extraction GPU Hardcoding (Medium)

**File:** `src/apps/documents/services/parse.py:68`

**Problem:**
```python
config = ExtractionConfig(
    ocr_backend="paddleocr",
    ocr_config=PaddleOCRConfig(use_gpu=True, device="cuda"),  # Assumes CUDA available
```

Forces GPU usage without checking availability. Crashes in environments without GPU/CUDA.

**Quick Fix (per user request):** Remove most arguments to let kreuzberg fall back to defaults.

### 3. Hardcoded External Dependency URLs (Medium)

**Files:**
- `src/config/settings.py` - URLs like OSIRIS URLs
- `src/apps/enrichment/services/osiris_scraper.py` - `https://people.utwente.nl`

**Problem:** URLs hardcoded in multiple places, difficult to change for different environments.

### 4. Missing Media Files Serving Configuration (Low)

**File:** `src/config/urls.py:16-18`

**Problem:** Media files only served in DEBUG mode. No guidance for production media serving (nginx/AWS S3/etc).

## Implementation Steps

### Step 1: Verify and Configure Loguru

**First, check if loguru is properly installed and configured:**

```bash
# Check if loguru is installed
uv show loguru

# If not installed, add it
uv add loguru
```

**Check current loguru setup:**

```bash
# Search for loguru imports
grep -r "from loguru import logger" src/
```

**Create proper loguru configuration:**

**File:** `src/config/logging.py` (NEW)

```python
"""
Loguru logging configuration for Easy Access Platform.

Replaces Django's stdlib logging with loguru for better formatting,
structured logging, and easier configuration.
"""

import sys
from pathlib import Path
from loguru import logger

# Remove default handler
logger.remove()

# Determine log level from environment
import os
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if os.getenv("DEBUG") else "INFO")

# Console handler with colors
logger.add(
    sys.stdout,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    ),
    level=LOG_LEVEL,
    colorize=True,
    backtrace=True,
    diagnose=True,
)

# File handler for production (only in non-DEBUG mode)
if not os.getenv("DEBUG"):
    # Ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Rotation: New file at midnight
    # Retention: Keep logs for 30 days
    # Compression: Compress old logs with zip
    logger.add(
        logs_dir / "app_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="INFO",
        rotation="00:00",  # New file at midnight
        retention="30 days",  # Keep logs for 30 days
        compression="zip",  # Compress old logs
        enqueue=True,  # Thread-safe logging
    )

# Error log file (separate file for errors)
if not os.getenv("DEBUG"):
    logger.add(
        logs_dir / "errors_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        level="ERROR",
        rotation="00:00",
        retention="90 days",  # Keep error logs longer
        compression="zip",
        enqueue=True,
    )


def intercept_standard_logging():
    """
    Intercept standard logging messages and redirect to loguru.

    This ensures all Django and third-party library logs go through loguru.
    """
    import logging

    class InterceptHandler(logging.Handler):
        def emit(self, record):
            # Get corresponding loguru level if it exists
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno

            # Find caller from where originated the logged message
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1

            logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )

    # Set up interception
    logging.basicConfig(handlers=[InterceptHandler()], level=0)

    # Disable Django's default logging
    for logger_name in ["django", "django.request", "django.db.backends"]:
        logging_logger = logging.getLogger(logger_name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False


# Apply interception
intercept_standard_logging()
```

**Update settings.py:**

**File:** `src/config/settings.py`

**Remove old LOGGING config (lines 201-213):**

```python
# DELETE THIS SECTION:
# LOGGING = {
#     "version": 1,
#     "disable_existing_loggers": False,
#     # ...
# }
```

**Add loguru initialization:**

```python
# At the bottom of settings.py (after all other config)

# Configure loguru logging
try:
    from .logging import intercept_standard_logging
    intercept_standard_logging()
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Loguru logging configured for {ENV}")
except ImportError:
    # Fallback to standard logging if loguru not available
    import logging
    logging.basicConfig(level=logging.INFO)
```

**Or better, in `src/config/__init__.py`:**

```python
"""
Initialize logging when Django config is loaded.
"""
from config.logging import intercept_standard_logging

# Configure loguru to intercept all logging
intercept_standard_logging()
```

### Step 2: Fix PDF Extraction GPU Issue (Quick Fix)

**File:** `src/apps/documents/services/parse.py`

**Current code (around line 68):**
```python
config = ExtractionConfig(
    ocr_backend="paddleocr",
    ocr_config=PaddleOCRConfig(
        use_gpu=True,  # ❌ Hardcoded to True
        device="cuda",  # ❌ Hardcoded to CUDA
    ),
)
```

**Quick fix (per user request):**

```python
# Quick fix: Remove GPU arguments, let kreuzberg use defaults
# Kreuzberg will auto-detect GPU availability and fall back to CPU
config = ExtractionConfig(
    ocr_backend="paddleocr",
    # ocr_config defaults to PaddleOCRConfig() which auto-detects GPU
)
```

**Or even simpler:**
```python
# Let kreuzberg use all defaults
config = ExtractionConfig(ocr_backend="paddleocr")
```

**Note:** This is a quick fix. Proper implementation will add environment variable to control GPU usage:

```python
# Future enhancement (not part of this quick fix):
import os
USE_GPU = os.getenv("USE_GPU", "auto").lower() == "true"

if USE_GPU:
    config = ExtractionConfig(
        ocr_backend="paddleocr",
        ocr_config=PaddleOCRConfig(use_gpu=True, device="cuda")
    )
else:
    config = ExtractionConfig(ocr_backend="paddleocr")
```

### Step 3: Extract Hardcoded URLs to Settings

**Audit hardcoded URLs:**

```bash
# Find all hardcoded URLs
grep -r "https://" src/apps/ --include="*.py" | grep -v migrations | grep -v tests
```

**Common URLs to extract:**
- OSIRIS URLs
- People pages URL
- Canvas API URL

**File:** `src/config/settings.py`

**Add URL configuration section:**

```python
# External Service URLs
# These should be environment-specific

# Osiris (University course system)
OSIRIS_BASE_URL = env("OSIRIS_BASE_URL", default="https://osiris.utwente.nl")
OSIRIS_API_URL = env("OSIRIS_API_URL", default="https://osiris-api.utwente.nl")

# People pages (University directory)
PEOPLE_PAGES_BASE_URL = env(
    "PEOPLE_PAGES_BASE_URL",
    default="https://people.utwente.nl"
)

# Canvas LMS
CANVAS_API_URL = env("CANVAS_API_URL", default="https://utwente.instructure.com")
CANVAS_BASE_URL = env("CANVAS_BASE_URL", default="https://utwente.instructure.com")

# Copyright database
COPYRIGHT_DB_URL = env(
    "COPYRIGHT_DB_URL",
    default="https://copyright.utwente.nl"
)
```

**Update services to use settings:**

**File:** `src/apps/enrichment/services/osiris_scraper.py`

```python
from django.conf import settings

# Before:
# url = "https://people.utwente.nl" + person_path

# After:
url = settings.PEOPLE_PAGES_BASE_URL + person_path
```

**File:** `src/apps/core/services/osiris.py`

```python
# Before:
# OSIRIS_SEARCH_URL = "https://osiris.utwente.nl/..."

# After:
from django.conf import settings
OSIRIS_SEARCH_URL = f"{settings.OSIRIS_API_URL}/search"
```

**File:** `src/apps/core/services/canvas.py`

```python
# Before:
# API_BASE = "https://utwente.instructure.com/api/v1"

# After:
from django.conf import settings
API_BASE = f"{settings.CANVAS_API_URL}/api/v1"
```

### Step 4: Configure Media Files Serving

**For Development (DEBUG mode):**

**File:** `src/config/urls.py` (already exists, keep as-is)

```python
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

**For Production:**

**Option A: Nginx (Recommended for traditional deployments)**

**File:** `nginx.conf` (NEW)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /static/ {
        alias /app/src/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /app/media/;
        expires 1y;
        add_header Cache-Control "public";

        # Security: Prevent executing uploaded files
        location ~* \.(php|pl|py|jsp|asp|sh|cgi)$ {
            deny all;
        }
    }

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Option B: AWS S3 / CloudFront (Recommended for cloud deployments)**

**Install:**
```bash
uv add django-storages[boto3]
```

**Update settings:**

```python
# .env
USE_S3=True
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_STORAGE_BUCKET_NAME=your-bucket
AWS_S3_REGION_NAME=eu-central-1
AWS_S3_CUSTOM_DOMAIN=%s.cloudfront.net" % AWS_STORAGE_BUCKET_NAME
```

```python
# settings.py
if env("USE_S3", default=False):
    # S3 static files
    STATICFILES_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    STATIC_URL = f"https://{env('AWS_S3_CUSTOM_DOMAIN')}/static/"

    # S3 media files
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    MEDIA_URL = f"https://{env('AWS_S3_CUSTOM_DOMAIN')}/media/"

    # AWS config
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME")
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = "public-read"
    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=86400",
    }
```

**Add deployment documentation:**

**File:** `docs/deployment.md` (NEW)

```markdown
# Media Files Serving in Production

## Development
Media files served by Django at `/media/`

## Production Options

### Option 1: Nginx (Traditional)
- Configure nginx to serve `/media/` directly
- See `nginx.conf` for configuration

### Option 2: AWS S3 + CloudFront (Cloud)
- Set USE_S3=True in .env
- Configure AWS credentials
- Media files uploaded to S3 automatically
- Served via CloudFront CDN

## Security Notes
- Prevent execution of uploaded files (nginx config)
- Use separate domain for media files (cookie-less requests)
- Enable CloudFront for better performance
```

## Testing

### 1. Verify Loguru Setup

```bash
# Run Django shell
uv run python src/manage.py shell

# Test logging
from loguru import logger
logger.info("Test info message")
logger.error("Test error message")
logger.warning("Test warning")

# Expected: Formatted output with colors in console
```

### 2. Test Standard Logging Interception

```bash
# Trigger a Django request
curl http://localhost:8000/

# Check logs - should see Django logs formatted by loguru
# Expected: Loguru-formatted Django logs, not stdlib format
```

### 3. Test PDF Extraction (GPU Fix)

```bash
# Test PDF extraction without GPU
uv run python src/manage.py shell

from apps.documents.services.parse import extract_pdf_details
from pathlib import Path

# This should work on CPU now (not crash)
result = extract_pdf_details(Path("/path/to/test.pdf"))
print(result)
```

### 4. Test URL Configuration

```bash
# Test that services use configured URLs
uv run python src/manage.py shell

from django.conf import settings
print(f"OSIRIS: {settings.OSIRIS_BASE_URL}")
print(f"People: {settings.PEOPLE_PAGES_BASE_URL}")
print(f"Canvas: {settings.CANVAS_API_URL}")

# Expected: Configured URLs, not hardcoded
```

## Success Criteria

- [ ] Loguru is properly configured and installed
- [ ] Standard logging intercepted and redirected to loguru
- [ ] All `import logging` replaced with `from loguru import logger`
- [ ] PDF extraction GPU issue fixed (quick fix with defaults)
- [ ] External URLs moved to settings with env() defaults
- [ ] Services updated to use settings URLs
- [ ] Media serving documented (nginx or S3 options)
- [ ] Loguru formatting verified in console
- [ ] PDF extraction works on CPU-only environments
- [ ] .env.example updated with new URL variables

## Files Created/Modified

- `src/config/logging.py` - NEW: Loguru configuration
- `src/config/__init__.py` - Initialize loguru
- `src/config/settings.py` - Remove LOGGING dict, add URL config
- `src/apps/documents/services/parse.py` - Fix GPU hardcoding
- `src/apps/enrichment/services/osiris_scraper.py` - Use settings URLs
- `src/apps/core/services/osiris.py` - Use settings URLs
- `src/apps/core/services/canvas.py` - Use settings URLs
- `src/apps/documents/services/download.py` - Replace logging with loguru
- `src/apps/settings/models.py` - Replace logging with loguru
- `nginx.conf` - NEW: Nginx config (if using nginx)
- `docs/deployment.md` - NEW: Deployment documentation

## Related Tasks

- **Task 11:** Error Handling & Logging (comprehensive logging strategy)
- **Task 08:** Security Hardening (production configuration)

## Benefits

1. **Consistent logging** - All logs use loguru formatting
2. **Structured logs** - Easier parsing and analysis
3. **CPU compatibility** - PDF extraction works without GPU
4. **Environment flexibility** - URLs configurable per environment
5. **Production ready** - Media serving documented

---

**Next Task:** [Task 18: Incomplete Enrichment Data Extraction](18-incomplete-enrichment-data.md)
