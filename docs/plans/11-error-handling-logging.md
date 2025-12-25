# Task 11: Error Handling & Logging

## Overview

Improve error handling in async tasks and standardize logging throughout the codebase using loguru.

**Current Status:** ❌ **NOT STARTED**
**Priority:** **MEDIUM** (Technical Debt)

## Issues Addressed

### 1. Silent Exception Handling in Tasks (Medium)
**File:** `src/apps/enrichment/tasks.py:287-302`

**Problem:**
The critical error handler silently swallows exceptions without proper logging or propagation.

```python
except Exception as e:
    logger.error(f"Critical error in enrich_item for {item_id}: {e}")
    try:
        item = await CopyrightItem.objects.aget(material_id=item_id)
        item.enrichment_status = EnrichmentStatus.FAILED
        await item.asave(update_fields=["enrichment_status"])
    except Exception:
        pass  # ❌ Silent failure - no logging, no re-raise
```

**Issues:**
- Uses `logger.error()` without traceback - harder to debug
- Inner exception completely silent
- Task system doesn't know about the failure
- No monitoring/alerting possible

**Fix:**
```python
except Exception as e:
    logger.exception(f"Critical error in enrich_item for {item_id}")  # ✅ Full traceback
    try:
        item = await CopyrightItem.objects.aget(material_id=item_id)
        item.enrichment_status = EnrichmentStatus.FAILED
        await item.asave(update_fields=["enrichment_status"])
    except Exception as inner_e:
        logger.error(f"Failed to update error status for item {item_id}: {inner_e}")
        raise  # ✅ Re-raise so task system knows
```

### 2. Inconsistent Logging (Medium)

**Problem:**
The codebase mixes `loguru` and standard `logging` module usage.

**Files affected:**
- `src/apps/documents/services/download.py:17` - uses `logging`
- `src/apps/settings/models.py:311` - uses `logging` inline

**Project standard:** Use `loguru` (as per CLAUDE.md)

**Fix:** Standardize on loguru throughout.

### 3. Missing Password Validators (Medium)
**File:** `src/config/settings.py:163`

**Problem:**
Empty password validators allow weak passwords.

```python
AUTH_PASSWORD_VALIDATORS = []  # ❌ No validation
```

**Fix:**
```python
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
```

### 4. Minimal Logging Configuration (Medium)

**Problem:**
Logging configuration lacks structured logging for production.

**Fix:** Add structured JSON logging and proper handlers.

## Implementation Steps

### Step 1: Fix Task Error Handling

**File:** `src/apps/enrichment/tasks.py`

**Find and update the critical error handler:**

```python
# BEFORE (around line 287-302)
except Exception as e:
    logger.error(f"Critical error in enrich_item for {item_id}: {e}")
    try:
        item = await CopyrightItem.objects.aget(material_id=item_id)
        item.enrichment_status = EnrichmentStatus.FAILED
        await item.asave(update_fields=["enrichment_status"])
    except Exception:
        pass

# AFTER
except Exception as e:
    # Use logger.exception() to capture full traceback
    logger.exception(f"Critical error in enrich_item for item_id={item_id}")

    # Try to mark item as failed
    try:
        item = await CopyrightItem.objects.aget(material_id=item_id)
        item.enrichment_status = EnrichmentStatus.FAILED
        await item.asave(update_fields=["enrichment_status"])
        logger.info(f"Marked item {item_id} as failed due to enrichment error")
    except Exception as inner_e:
        # Log but don't suppress - re-raise for task system
        logger.error(f"Failed to update error status for item_id={item_id}: {inner_e}")
        # Re-raise so task system knows about the failure
        raise  # or raise inner_e
```

**Also check for other places with bare `except:` or `except Exception: pass`:**

```bash
# Find all instances
grep -r "except.*pass" src/apps/
grep -r "except Exception:" src/apps/ | grep -v "logger"
```

### Step 2: Standardize on Loguru

**File:** `src/apps/documents/services/download.py`

**Current import:**
```python
import logging
logger = logging.getLogger(__name__)
```

**Replace with:**
```python
from loguru import logger
```

**File:** `src/apps/settings/models.py`

**Find inline logging usage (around line 311):**
```python
# If there's inline logging like:
import logging
logger = logging.getLogger(__name__)

# Replace with:
from loguru import logger
```

**Search for all logging usage:**
```bash
# Find all files using logging module
grep -r "import logging" src/
grep -r "logging.getLogger" src/
```

**Replace all with loguru.**

### Step 3: Add Password Validators

**File:** `src/config/settings.py`

**Find AUTH_PASSWORD_VALIDATORS (around line 163):**

```python
# BEFORE
AUTH_PASSWORD_VALIDATORS = []

# AFTER
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"
    },
]
```

### Step 4: Improve Logging Configuration

**File:** `src/config/settings.py`

**Current LOGGING config (lines 201-213):**

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
```

**Enhanced LOGGING config:**

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": env("LOG_FILE", default="logs/django.log"),
            "maxBytes": 1024 * 1024 * 50,  # 50MB
            "backupCount": 10,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"] if DEBUG else ["console", "file"],
        "level": "DEBUG" if DEBUG else "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"] if DEBUG else ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"] if DEBUG else ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"] if DEBUG else ["console", "file"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}
```

### Step 5: Configure Loguru (Optional Enhancement)

**File:** `src/config/settings.py` or create `src/config/logging.py`

```python
# Optional: Use Loguru's advanced features
from loguru import logger
import sys

# Remove default handler
logger.remove()

# Add console handler with format
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG" if DEBUG else "INFO",
)

# Add file handler for production
if not DEBUG:
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # New file at midnight
        retention="30 days",  # Keep logs for 30 days
        compression="zip",  # Compress old logs
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

# Intercept standard logging
import logging

class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
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

# Intercept standard logging
logging.basicConfig(handlers=[InterceptHandler()], level=0)
```

**Or use `loguru-django` package:**

```bash
# Add to pyproject.toml
uv add loguru-django
```

### Step 6: Add Logging to Views

**File:** `src/apps/dashboard/views.py` and other views

**Add request logging for debugging:**

```python
from loguru import logger

@login_required
def item_list(request):
    logger.info(f"User {request.user.username} accessed item list")
    # ... view code ...
```

**Add error logging:**

```python
from loguru import logger

@login_required
def item_detail(request, material_id):
    try:
        item = CopyrightItem.objects.get(material_id=material_id)
        logger.debug(f"Fetching details for item {material_id}")
        # ... view code ...
    except CopyrightItem.DoesNotExist:
        logger.warning(f"Item {material_id} not found for user {request.user.username}")
        raise Http404("Item not found")
    except Exception as e:
        logger.exception(f"Unexpected error fetching item {material_id}")
        raise
```

## Testing

### 1. Test Task Error Handling

```python
# Test that exceptions are properly logged and propagated
import asyncio
from apps.enrichment.tasks import enrich_item

async def test_error_handling():
    # Try to enrich with invalid data
    try:
        await enrich_item({"material_id": -1})  # Invalid ID
    except Exception as e:
        print(f"Exception properly raised: {e}")
        # Check logs for full traceback

asyncio.run(test_error_handling())
```

### 2. Test Password Validation

```python
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

# Test weak password rejection
try:
    validate_password("password")
    assert False, "Should have raised ValidationError"
except ValidationError as e:
    print(f"Good: Weak password rejected - {e.messages}")

# Test strong password acceptance
try:
    validate_password("Str0ng!Pass@w0rd123")
    print("Good: Strong password accepted")
except ValidationError as e:
    print(f"Bad: Strong password rejected - {e.messages}")
```

### 3. Test Logging Output

```python
from loguru import logger

# Test logging
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
try:
    1 / 0
except ZeroDivisionError:
    logger.exception("Exception message")  # Should include traceback
```

**Check console output includes:**
- Timestamps
- Log levels
- Module/function/line numbers
- Tracebacks for exceptions

### 4. Test Log Rotation

```bash
# Generate logs and verify rotation
# In production mode, logs should rotate at midnight and compress

# Check for log files
ls -la logs/

# Should see:
# logs/app_2025-12-24.log
# logs/app_2025-12-25.log
# logs/app_2025-12-25.log.zip (if configured)
```

## Best Practices

### 1. Always Use logger.exception() for Errors

```python
# ❌ BAD
except Exception as e:
    logger.error(f"Error: {e}")

# ✅ GOOD
except Exception as e:
    logger.exception(f"Error occurred")  # Includes full traceback
```

### 2. Add Context to Log Messages

```python
# ❌ BAD
logger.error("Download failed")

# ✅ GOOD
logger.error(f"PDF download failed for material_id={material_id}, url={url}")
```

### 3. Use Appropriate Log Levels

```python
logger.debug("Detailed diagnostic info")  # Development only
logger.info("Normal operation messages")  # Production
logger.warning("Something unexpected but recoverable")  # Production
logger.error("Error occurred, operation failed")  # Production
logger.exception("Error with traceback")  # Production
```

### 4. Never Use Bare except

```python
# ❌ BAD
except:
    pass

# ✅ GOOD
except SpecificException as e:
    logger.exception(f"Specific error: {e}")
    # Handle or re-raise
```

### 5. Re-raise After Logging in Tasks

```python
# ❌ BAD - Task system doesn't know about failure
except Exception:
    logger.exception("Error")
    pass  # Swallowed

# ✅ GOOD - Task system knows about failure
except Exception:
    logger.exception("Error")
    raise  # Re-raise for task system
```

## Success Criteria

- [ ] Task error handling uses `logger.exception()`
- [ ] Tasks re-raise exceptions after logging
- [ ] All `import logging` replaced with `from loguru import logger`
- [ ] Password validators configured
- [ ] Logging configuration enhanced with file handler
- [ ] Logs include timestamps, levels, module names
- [ ] Error logs include full tracebacks
- [ ] Log rotation configured for production
- [ ] All tests pass
- [ ] Manual testing confirms proper logging

## Files Modified

- `src/apps/enrichment/tasks.py` - Fix error handling with logger.exception()
- `src/apps/documents/services/download.py` - Replace logging with loguru
- `src/apps/settings/models.py` - Replace logging with loguru (if needed)
- `src/config/settings.py` - Enhanced LOGGING config, password validators
- Any other files with `import logging`

## Benefits

1. **Better debugging** - Full tracebacks in logs
2. **Better monitoring** - Tasks properly report failures
3. **Consistency** - All logging uses loguru
4. **Security** - Password strength enforced
5. **Production ready** - File logs with rotation
6. **Easier troubleshooting** - Contextual log messages

---

**Next Task:** [Task 12: API Validation & Documentation](12-api-validation-documentation.md)
