# Task 1: Redis Caching Infrastructure

## Overview

Configure Redis as Django's cache backend and apply caching to expensive operations.

**Current Status:** ⚠️ **PARTIALLY IMPLEMENTED (40%)**
- ✅ Cache service module exists with decorators
- ❌ CACHES not configured in settings.py
- ❌ Cache decorators not applied to services

## What's Already Done

### Cache Service Infrastructure ✅

**File:** `src/apps/core/services/cache_service.py` (COMPLETE)

The cache service module provides:
- `@cache_query_result` - For synchronous functions
- `@cache_async_result` - For async functions
- `invalidate_pattern()` - Clear cache by pattern
- `invalidate_key()` - Clear specific key
- Proper cache key generation with argument hashing
- Comprehensive tests in `test_cache_service.py`

This is well-designed and ready to use.

## What's Missing

### Step 1: Configure Django CACHES Setting

**File:** `src/config/settings.py`

**Current State:** No CACHES configuration exists

**Add after line 109 (after _redis_url definition):**

```python
# =============================================================================
# CACHE Configuration (Redis)
# =============================================================================
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": _redis_url,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "PARSER_CLASS": "redis.connection.HParser",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "CONNECTION_POOL_KWARGS": {"max_connections": 50},
        },
        "KEY_PREFIX": "ea_platform",
        "VERSION": 1,
    },
    # Session cache for expensive queries
    "queries": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": _redis_url,
        "TIMEOUT": 300,  # 5 minutes
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "ea_queries",
    }
}
```

**Dependencies:**
- Add `django-redis` to requirements:
  ```bash
  uv add django-redis
  ```

### Step 2: Apply Caching to Query Service

**File:** `src/apps/dashboard/services/query_service.py`

**Current State:** No caching used

**Add caching to expensive operations:**

```python
from apps.core.services.cache_service import cache_query_result

class ItemQueryService:
    @cache_query_result(timeout=300, key_prefix="filter_counts", cache_name="queries")
    def _get_filter_counts(self, base_qs) -> dict[str, int]:
        """Cache expensive filter count aggregations."""
        # Existing implementation
        ...

    @cache_query_result(timeout=600, key_prefix="faculties", cache_name="default")
    def get_faculties(self):
        """Faculty list rarely changes - cache for 10 minutes."""
        # Existing implementation
        ...
```

### Step 3: Cache External API Results

**File:** `src/apps/core/services/osiris.py`

**Current State:** No caching

**Add async caching:**

```python
from apps.core.services.cache_service import cache_async_result

class OsirisScraperService:
    @cache_async_result(timeout=86400, key_prefix="osiris_course")  # 24 hours
    async def fetch_course_details(self, course_code: int):
        """Course data changes infrequently."""
        # Existing implementation
        ...

    @cache_async_result(timeout=86400, key_prefix="osiris_person")
    async def fetch_person_data(self, name: str):
        """People data changes infrequently."""
        # Existing implementation
        ...
```

**File:** `src/apps/core/services/canvas.py`

**Current State:** No caching

**Add caching:**

```python
from apps.core.services.cache_service import cache_async_result

@cache_async_result(timeout=3600, key_prefix="file_exists")  # 1 hour
async def check_single_file_existence(item_data: Item, client: httpx.AsyncClient):
    """File existence status rarely changes within hour."""
    # Existing implementation
    ...
```

### Step 4: Implement Cache Invalidation

**File:** `src/apps/ingest/services/qlik_processor.py`

**Current State:** No cache invalidation

**Add invalidation when data changes:**

```python
from apps.core.services.cache_service import invalidate_pattern

async def process_qlik_entry(entry: QlikEntry, batch: IngestionBatch):
    """Process a staged Qlik entry."""
    # ... existing processing logic ...

    # Invalidate related caches
    invalidate_pattern("filter_counts")
    invalidate_pattern("faculties")
```

## Cache Strategy Table

| Data Type | TTL | Cache | Invalidation Trigger |
|-----------|-----|-------|---------------------|
| Filter counts | 5 min | queries | On ingest/update |
| Faculty list | 10 min | default | On faculty change |
| Osiris courses | 24 hrs | default | Time-based only |
| Osiris people | 24 hrs | default | Time-based only |
| Canvas file existence | 1 hr | default | Time-based only |

## Testing

### Integration Tests (New)

**File:** `src/apps/dashboard/tests/test_query_service_caching.py` (NEW)

```python
import pytest
from apps.dashboard.services.query_service import ItemQueryService

@pytest.mark.django_db
class TestQueryServiceCaching:
    def test_filter_counts_caching(self):
        """Test that filter counts are properly cached."""
        service = ItemQueryService()

        # First call - cache miss
        counts1 = service._get_filter_counts(base_qs)

        # Second call should hit cache
        counts2 = service._get_filter_counts(base_qs)

        assert counts1 == counts2
```

## Monitoring

Add cache metrics logging:

**File:** `src/config/settings.py`

```python
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.core.cache': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'apps.core.services.cache_service': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

## Rollback Strategy

If caching causes issues, disable via environment variable:

**File:** `src/config/settings.py`

```python
# Add at top with other env variables
USE_CACHE = env("USE_CACHE", default=True)

# Modify CACHES configuration
if USE_CACHE:
    CACHES = {
        # ... Redis configuration
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    }
```

## Success Criteria

- [ ] CACHES configured in settings.py with Redis backend
- [ ] django-redis package added to requirements
- [ ] Filter counts cached (5 min TTL)
- [ ] Faculty lists cached (10 min TTL)
- [ ] Osiris API results cached (24 hr TTL)
- [ ] Canvas file existence cached (1 hr TTL)
- [ ] Cache invalidation implemented for data changes
- [ ] Integration tests pass
- [ ] Cache hit/miss metrics logged

## Estimated Time

**Total: 1-2 days** (Infrastructure already exists, just needs integration)

- **Configuration:** 2 hours
- **Apply caching to services:** 4 hours
- **Testing:** 4 hours
- **Documentation:** 2 hours

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Cache serves stale data | Appropriate TTLs, invalidation on updates |
| Redis connection failure | Feature flag (USE_CACHE) to disable |
| Memory exhaustion | Monitor Redis memory usage, set max TTLs |

---

**Next Task:** [Task 4: Template Partials](04-template-partials.md) (Needs revised approach)
