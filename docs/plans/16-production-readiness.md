# Task 16: Production Readiness Essentials

## Overview

Implement essential production infrastructure components: health checks, ASGI configuration, rate limiting, and database connection pooling.

**Current Status:** ✅ **COMPLETE**
**Priority:** **HIGH** (Fix Soon)

## Issues Addressed

### 1. Missing ASGI Configuration (Critical)

**Problem:** Django 6.0 has improved async support but there is no `asgi.py` configuration. The codebase uses async views and tasks but lacks proper async deployment configuration.

**Impact:** Async features may not work correctly in production deployments.

### 2. Missing Health Check Endpoint (High)

**Problem:** No dedicated health check endpoint for orchestration (Kubernetes, load balancers).

**Impact:** Cannot properly detect if application is healthy in production environments.

### 3. No Request Rate Limiting (High)

**Problem:** No rate limiting on API endpoints or views.

**Impact:** Vulnerable to brute force attacks, API abuse, DoS.

### 4. Missing Database Connection Pooling (Medium)

**Problem:** No database connection pooling configured for PostgreSQL.

**Impact:** Connection overhead on high-load scenarios, potential connection exhaustion.

## Implementation Steps

### Step 1: Create ASGI Configuration

**File:** `src/config/asgi.py` (NEW)

```python
"""
ASGI config for Easy Access Platform.

Django 6.0 native async configuration.
For production, use uvicorn or daphne.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_asgi_application()

# For Django Channels (if WebSockets needed in future)
# from channels.routing import get_default_application
# application = get_default_application()
```

**Update `.env.example`:**

```bash
# ASGI Application Server
# For production, use uvicorn:
# uvicorn config.asgi:application --host 0.0.0.0 --port 8000

# Or daphne (for WebSockets):
# daphne config.asgi:application --bind 0.0.0.0 --port 8000
```

**Update `docker-compose.yml` (if using Docker):**

```yaml
services:
  web:
    # ...
    command: uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --workers 4
```

### Step 2: Create Health Check Endpoint

**File:** `src/apps/api/views.py` (add to existing)

```python
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
from loguru import logger
import time


def health_check(request):
    """
    Health check endpoint for orchestration systems.

    Checks:
    - Django is running
    - Database connection
    - Redis/cache connection

    Returns:
        200 OK if all checks pass
        503 Service Unavailable if any check fails
    """
    status = {
        "status": "healthy",
        "timestamp": time.time(),
        "checks": {}
    }

    overall_healthy = True

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        status["checks"]["database"] = "ok"
    except Exception as e:
        status["checks"]["database"] = f"error: {str(e)}"
        overall_healthy = False
        logger.error(f"Health check database failed: {e}")

    # Check cache/redis
    try:
        cache.set("health_check", "ok", timeout=10)
        cache.get("health_check")
        status["checks"]["cache"] = "ok"
    except Exception as e:
        status["checks"]["cache"] = f"error: {str(e)}"
        overall_healthy = False
        logger.error(f"Health check cache failed: {e}")

    # Check RQ workers (optional)
    try:
        from django_rq import get_queue
        queue = get_queue('default')
        workers = queue.workers
        worker_count = len(workers)
        status["checks"]["rq_workers"] = f"{worker_count} workers"
        if worker_count == 0:
            status["checks"]["rq_workers"] += " (WARNING: no workers)"
    except Exception as e:
        status["checks"]["rq_workers"] = f"error: {str(e)}"
        logger.warning(f"Health check RQ workers failed: {e}")

    # Set overall status
    status["status"] = "unhealthy" if not overall_healthy else "healthy"

    response_code = 200 if overall_healthy else 503
    return JsonResponse(status, status=response_code)


def readiness_check(request):
    """
    Readiness check - is the app ready to serve traffic?

    More thorough than health check, checks if app can process requests.
    """
    try:
        # Try a simple query
        from apps.core.models import CopyrightItem
        count = CopyrightItem.objects.count()  # Uses cached count hopefully

        return JsonResponse({
            "status": "ready",
            "timestamp": time.time(),
            "items_in_db": count
        })
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JsonResponse({
            "status": "not_ready",
            "timestamp": time.time(),
            "error": str(e)
        }, status=503)
```

**Add URLs:**

**File:** `src/apps/api/urls.py`

```python
from django.urls import path
from . import views

urlpatterns = [
    # Health checks
    path("health/", views.health_check, name="health_check"),
    path("readiness/", views.readiness_check, name="readiness_check"),

    # Existing API routes...
]
```

**Main URLs:**

**File:** `src/config/urls.py`

```python
urlpatterns = [
    path("api/", include("apps.api.urls")),  # Includes health checks
    # ... other patterns ...
]
```

**Usage:**

```bash
# Health check
curl http://localhost:8000/api/health/

# Readiness check
curl http://localhost:8000/api/readiness/

# Kubernetes probe configuration (in deployment.yaml)
livenessProbe:
  httpGet:
    path: /api/health/
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /api/readiness/
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

### Step 3: Implement Rate Limiting

**Option A: Django Ratelimit (Recommended)**

**Install:**
```bash
uv add django-ratelimit
```

**Update settings:**

**File:** `src/config/settings.py`

```python
INSTALLED_APPS = [
    # ...
    "django_ratelimit",
]

# Rate limiting configuration
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = "default"  # Use Redis for rate limiting
RATELIMIT_VIEW = "api.views.rate_limited"

# Rate limits (requests per time window)
RATELIMIT_RATE = "100/h"  # 100 requests per hour per user
```

**Apply to views:**

**File:** `src/apps/api/views.py`

```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key='user', rate='100/h', method='POST')
@require_POST
@login_required
def trigger_ingest(request: HttpRequest):
    """Trigger ingestion with rate limiting."""
    # ... existing code ...

@ratelimit(key='ip', rate='1000/h', method='GET')
def item_list(request):
    """Rate limited item list endpoint."""
    # ... existing code ...

# Custom rate limit exceeded response
def rate_limited(request, exception):
    """Custom response when rate limit is exceeded."""
    return JsonResponse({
        "error": "Rate limit exceeded",
        "detail": "Too many requests. Please try again later.",
        "retry_after": f"{exception.time_until} seconds"
    }, status=429)
```

**Option B: Custom Rate Limiting Middleware**

**File:** `src/apps/api/middleware.py` (NEW)

```python
from django.core.cache import cache
from django.http import JsonResponse
from loguru import logger
import time


class RateLimitMiddleware:
    """
    Simple rate limiting middleware for API endpoints.

    Usage: Add to MIDDLEWARE in settings
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only rate limit API endpoints
        if request.path.startswith("/api/"):
            # Skip health checks
            if request.path in ["/api/health/", "/api/readiness/"]:
                return self.get_response(request)

            # Rate limit: 100 requests per minute per user/IP
            user_id = request.user.id if request.user.is_authenticated else request.META.get("REMOTE_ADDR")
            key = f"rate_limit:{user_id}"

            # Get current count
            count = cache.get(key, 0)

            if count >= 100:
                logger.warning(f"Rate limit exceeded for user {user_id}")
                return JsonResponse(
                    {"error": "Rate limit exceeded", "retry_after": "60 seconds"},
                    status=429
                )

            # Increment counter with 60s expiry
            cache.set(key, count + 1, timeout=60)

        return self.get_response(request)
```

**Add to settings:**

```python
MIDDLEWARE = [
    # ... existing middleware ...
    "apps.api.middleware.RateLimitMiddleware",  # Add before CommonMiddleware
]
```

### Step 4: Configure Database Connection Pooling

**For PostgreSQL with pgbouncer (Recommended):**

**File:** `docker-compose.yml`

```yaml
services:
  # Add pgbouncer connection pooler
  pgbouncer:
    image: pgbouncer/pgbouncer:latest
    environment:
      - DATABASES_HOST=postgres
      - DATABASES_PORT=5432
      - DATABASES_NAME=${DATABASE_NAME}
      - DATABASES_USER=${DATABASE_USER}
      - DATABASES_PASSWORD=${DATABASE_PASSWORD}
      - POOL_MODE=transaction
      - MAX_CLIENT_CONN=1000
      - DEFAULT_POOL_SIZE=25
    ports:
      - "6432:6432"
    depends_on:
      - postgres

  web:
    # ...
    environment:
      - DATABASE_URL=postgres://${DATABASE_USER}:${DATABASE_PASSWORD}@pgbouncer:6432/${DATABASE_NAME}
```

**For Django built-in pooling (simpler):**

**File:** `src/config/settings.py`

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _db_name,
        "USER": _db_user,
        "PASSWORD": _db_password,
        "HOST": _db_host,
        "PORT": _db_port,
        "OPTIONS": {
            # Connection pool settings
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000",
        },
        "CONN_MAX_AGE": 600,  # Persistent connections for 10 minutes
        "CONN_HEALTH_CHECKS": True,  # Django 4.1+
    }
}

# For async connections (if using async ORM)
DATABASES["default"]["OPTIONS"] = {
    **DATABASES["default"].get("OPTIONS", {}),
    "pool_size": 20,  # Max connections in pool
    "max_overflow": 10,  # Additional connections when pool is full
}
```

**Note:** Django's built-in CONN_MAX_AGE provides basic connection reuse. For production with high load, use pgbouncer.

## Testing

### 1. Test ASGI Configuration

```bash
# Test uvicorn serves the app
uv run uvicorn config.asgi:application --host localhost --port 8000

# Visit http://localhost:8000/api/health/
# Should return JSON with status
```

### 2. Test Health Check

```bash
curl http://localhost:8000/api/health/
# Expected: {"status": "healthy", "checks": {"database": "ok", "cache": "ok"}}

curl http://localhost:8000/api/readiness/
# Expected: {"status": "ready", "items_in_db": N}
```

### 3. Test Rate Limiting

```bash
# Make 101 requests (should hit rate limit)
for i in {1..101}; do
  curl -X POST http://localhost:8000/api/ingest/ \
    -H "Authorization: Token YOUR_TOKEN" \
    -F "file=@test.xlsx"
done

# Expected: First 100 succeed, 101st returns 429
```

### 4. Test Connection Pooling

```bash
# Check database connection count
docker exec -it postgres psql -U user -d dbname -c "
SELECT count(*) FROM pg_stat_activity WHERE datname = 'dbname';
"

# Should see persistent connections being reused
```

## Success Criteria

- [ ] ASGI configuration created
- [ ] Health check endpoint working (/api/health/)
- [ ] Readiness check endpoint working (/api/readiness/)
- [ ] Rate limiting implemented (django-ratelimit or custom middleware)
- [ ] Database connection pooling configured (pgbouncer or CONN_MAX_AGE)
- [ ] Health checks tested with curl
- [ ] Rate limiting tested with multiple requests
- [ ] Connection pooling verified with pg_stat_activity
- [ ] Documentation updated with deployment commands

## Files Created/Modified

- `src/config/asgi.py` - NEW: ASGI application entry point
- `src/apps/api/views.py` - Add health_check and readiness_check
- `src/apps/api/urls.py` - Add health check URLs
- `src/apps/api/middleware.py` - NEW: Rate limiting middleware (if using custom)
- `src/config/settings.py` - Configure rate limiting, connection pooling
- `docker-compose.yml` - Add pgbouncer service (optional)
- `.env.example` - Add ASGI/RATE_LIMIT settings

## Related Tasks

- **Task 08:** Security Hardening (production security settings)
- **Task 11:** Error Handling & Logging (monitoring)

## Benefits

1. **Health monitoring** - K8s/orchestration can detect failures
2. **DoS protection** - Rate limiting prevents abuse
3. **Better performance** - Connection pooling reduces overhead
4. **Production ready** - Proper async deployment configuration

---

**Next Task:** [Task 17: Logging & Configuration](17-logging-configuration.md)
