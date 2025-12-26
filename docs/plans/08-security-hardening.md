# Task 08: Security Hardening

## Overview

Fix critical security vulnerabilities in Django settings and configuration to prevent potential exploits in production.

**Current Status:** ✅ **COMPLETE**
**Priority:** **CRITICAL** (Fix Immediately)

## Issues Addressed

### 1. Default SECRET_KEY (Critical)
**File:** `src/config/settings.py:20`

**Problem:**
```python
SECRET_KEY = env("SECRET_KEY", default="dev-secret-key")
```

If `.env` file is missing in production, the app runs with a known, insecure secret key. This allows:
- Session hijacking
- CSRF token forgery
- Password reset token generation attacks

**Fix:**
```python
SECRET_KEY = env("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        import warnings
        warnings.warn("Using insecure SECRET_KEY in DEBUG mode")
        SECRET_KEY = "dev-only-change-me"
    else:
        raise ImproperlyConfigured("SECRET_KEY must be set in production")
```

### 2. DEBUG Defaults to True (Critical)
**File:** `src/config/settings.py:15`

**Problem:**
```python
env = environ.Env(DEBUG=(bool, True))
```

If `.env` is missing, Django runs in DEBUG mode with:
- Detailed error pages exposed to users
- Stack traces with source code visible
- Configuration data leaked

**Fix:**
```python
# Default to False for security
env = environ.Env(DEBUG=(bool, False))
```

### 3. ALLOWED_HOSTS Wildcard (High)
**File:** `src/config/settings.py:26`

**Problem:**
```python
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])
```

Wildcard allows any host, enabling:
- Host header attacks
- Cache poisoning
- Phishing vulnerabilities

**Fix:**
```python
if DEBUG:
    ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
else:
    ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured("ALLOWED_HOSTS must be configured in production")
```

### 4. Exposed API Headers (High)
**File:** `src/config/settings.py:233-254`

**Problem:**
```python
OSIRIS_HEADERS = {
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "manifest": "24.46_B346_c0d3b6a1",
    # ... more headers ...
}
```

Version-specific fingerprints hardcoded in settings could be:
- Scraped by attackers for reconnaissance
- Used to fingerprint the application
- Leak internal configuration

**Fix:**
```python
# Move to environment configuration
OSIRIS_HEADERS = {
    "sec-ch-ua-platform": env("OSIRIS_PLATFORM", '"Windows"'),
    "authorization": env("OSIRIS_AUTHORIZATION", "undefined undefined"),
    "manifest": env("OSIRIS_MANIFEST", "24.46_B346_c0d3b6a1"),
    "sec-ch-ua": env("OSIRIS_UA", '"Google Chrome";v="131", "Chromium";v="131"'),
    "sec-ch-ua-mobile": env("OSIRIS_UA_MOBILE", "?0"),
    "sec-ch-ua-model": env("OSIRIS_UA_MODEL", '""'),
    "user-agent": env("OSIRIS_USER_AGENT", "Mozilla/5.0 ..."),
}
```

### 5. Missing Password Validators (Medium)
**File:** `src/config/settings.py:163`

**Problem:**
```python
AUTH_PASSWORD_VALIDATORS = []
```

Allows weak passwords that compromise user accounts.

**Fix:**
```python
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

### 6. Missing CSRF Trusted Origins (Low)
**File:** `src/config/settings.py`

**Problem:** For HTMX/API-heavy applications, CSRF trusted origins should be explicitly configured.

**Fix:**
```python
if not DEBUG:
    CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
```

## Implementation Steps

### Step 1: Update SECRET_KEY Handling

**File:** `src/config/settings.py`

```python
# Before (line ~20)
SECRET_KEY = env("SECRET_KEY", default="dev-secret-key")

# After
SECRET_KEY = env("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        import warnings
        warnings.warn("Using insecure SECRET_KEY in DEBUG mode - change this!")
        SECRET_KEY = "dev-only-change-me-" + str(os.getpid())
    else:
        raise ImproperlyConfigured(
            "SECRET_KEY environment variable must be set in production. "
            "Generate one with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
        )
```

### Step 2: Change DEBUG Default

**File:** `src/config/settings.py`

```python
# Before (line ~15)
env = environ.Env(DEBUG=(bool, True))

# After
env = environ.Env(DEBUG=(bool, False))  # Secure by default
DEBUG = env("DEBUG")

# Add warning if DEBUG is True in non-development
if DEBUG and not env("ENV", default="dev") == "dev":
    import warnings
    warnings.warn("DEBUG=True is enabled in a non-development environment!")
```

### Step 3: Secure ALLOWED_HOSTS

**File:** `src/config/settings.py`

```python
# Before (line ~26)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# After
if DEBUG:
    ALLOWED_HOSTS = env.list(
        "ALLOWED_HOSTS",
        default=["localhost", "127.0.0.1", "[::1]"]
    )
else:
    ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            "ALLOWED_HOSTS must be configured in production. "
            "Example: ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com"
        )
```

### Step 4: Move OSIRIS Headers to Environment

**File:** `src/config/settings.py`

```python
# Replace OSIRIS_HEADERS (lines ~233-254)
OSIRIS_HEADERS = {
    "sec-ch-ua-platform": env("OSIRIS_PLATFORM", '"Windows"'),
    "authorization": env("OSIRIS_AUTHORIZATION", "undefined undefined"),
    "manifest": env("OSIRIS_MANIFEST", "24.46_B346_c0d3b6a1"),
    "sec-ch-ua": env("OSIRIS_UA", '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'),
    "sec-ch-ua-mobile": env("OSIRIS_UA_MOBILE", "?0"),
    "sec-ch-ua-model": env("OSIRIS_UA_MODEL", '""'),
    "user-agent": env("OSIRIS_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "referer": env("OSIRIS_REFERER", "https://osiris.utwente.nl/"),
    "origin": env("OSIRIS_ORIGIN", "https://osiris.utwente.nl"),
}
```

### Step 5: Add Password Validators

**File:** `src/config/settings.py`

```python
# Replace AUTH_PASSWORD_VALIDATORS (line ~163)
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

### Step 6: Add Production Security Settings

**File:** `src/config/settings.py` (add after ALLOWED_HOSTS)

```python
# Production security settings
if not DEBUG:
    # HTTPS enforcement
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    # Cookie security
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True

    # HSTS
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # CSRF trusted origins
    CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

    # Content Security Policy (optional, for HTMX/Alpine)
    # CSP_DEFAULT_SRC = ("'self'",)
    # CSP_SCRIPT_SRC = ("'self'", "unsafe-inline", "unsafe-eval")
```

## Update .env.example

**File:** `.env.example`

Add the new required environment variables:

```bash
# REQUIRED IN PRODUCTION
SECRET_KEY=generate-with-python-manage-command
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# CSRF Trusted Origins (for production)
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# OSIRIS API Configuration (moved to environment)
OSIRIS_PLATFORM='"Windows"'
OSIRIS_AUTHORIZATION=undefined undefined
OSIRIS_MANIFEST=24.46_B346_c0d3b6a1
OSIRIS_UA='"Google Chrome";v="131","Chromium";v="131","Not_A Brand";v="24"'
OSIRIS_UA_MOBILE=?0
OSIRIS_UA_MODEL=''
OSIRIS_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
OSIRIS_REFERER=https://osiris.utwente.nl/
OSIRIS_ORIGIN=https://osiris.utwente.nl
```

## Testing

### 1. Test SECRET_KEY Enforcement

```bash
# Should fail in production without SECRET_KEY
DEBUG=False ALLOWED_HOSTS=localhost uv run python src/manage.py check
# Expected: ImproperlyConfigured error

# Should work with SECRET_KEY
SECRET_KEY=test DEBUG=False ALLOWED_HOSTS=localhost uv run python src/manage.py check
# Expected: No errors
```

### 2. Test DEBUG Default

```bash
# Should default to False
uv run python src/manage.py shell -c "from django.conf import settings; print(settings.DEBUG)"
# Expected: False (without DEBUG=True in .env)
```

### 3. Test ALLOWED_HOSTS Validation

```bash
# Should fail with wildcard in production
DEBUG=False ALLOWED_HOSTS='*' uv run python src/manage.py check
# Expected: ImproperlyConfigured error

# Should work with explicit hosts
DEBUG=False ALLOWED_HOSTS=localhost,127.0.0.1 uv run python src/manage.py check
# Expected: No errors
```

### 4. Test Password Validation

```python
# In Django shell
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

# Should reject weak passwords
try:
    validate_password("password")
except ValidationError as e:
    print(f"Good: {e.messages}")  # Expected: validation errors

# Should accept strong passwords
validate_password("Str0ng!Pass@w0rd")  # Expected: no error
```

### 5. Run Django System Checks

```bash
uv run python src/manage.py check --deploy
```

This will check for production security misconfigurations.

## Success Criteria

- [ ] SECRET_KEY required in production (DEBUG=False)
- [ ] DEBUG defaults to False
- [ ] ALLOWED_HOSTS cannot be wildcard in production
- [ ] OSIRIS headers moved to environment variables
- [ ] Password validators configured
- [ ] Production security settings added (HTTPS, HSTS, secure cookies)
- [ ] .env.example updated with new variables
- [ ] All Django system checks pass with `--deploy` flag
- [ ] Application still works in development mode

## Files Modified

- `src/config/settings.py` - All security fixes
- `.env.example` - Add new environment variables

## Post-Implementation Verification

1. **Development Mode:**
   ```bash
   DEBUG=True uv run python src/manage.py runserver
   # Should work with default localhost ALLOWED_HOSTS
   ```

2. **Production Mode (Local Test):**
   ```bash
   DEBUG=False \
   SECRET_KEY=test-secret-key \
   ALLOWED_HOSTS=localhost \
   uv run python src/manage.py runserver
   # Should work with explicit configuration
   ```

3. **Security Check:**
   ```bash
   uv run python src/manage.py check --deploy
   # Should show no security warnings
   ```

## Security Benefits

1. **Prevents session hijacking** - Secure SECRET_KEY
2. **Prevents information disclosure** - DEBUG=False by default
3. **Prevents host header attacks** - Explicit ALLOWED_HOSTS
4. **Prevents fingerprinting** - Environment-based API headers
5. **Prevents weak passwords** - Password validators
6. **Enforces HTTPS** - Production security settings

---

**Next Task:** [Task 09: Database Schema & Indexes](09-database-schema-indexes.md)
