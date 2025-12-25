# Task 12: API Validation & Documentation

## Overview

Improve API input validation and implement Django Shinobi schemas for request/response validation.

**Current Status:** ❌ **NOT STARTED**
**Priority:** **HIGH** (Fix Soon)

## Issues Addressed

### 1. Missing Input Validation on API Endpoints (High)
**File:** `src/apps/api/views.py:21-31`

**Problem:**
The `_parse_item_ids` function catches exceptions broadly but returns generic error messages without distinguishing between different failure modes.

```python
def _parse_item_ids(item_ids_str: list[str]) -> tuple[list[int] | None, str | None]:
    try:
        return [int(i) for i in item_ids_str], None
    except (ValueError, TypeError):
        return None, "Invalid item IDs"
```

**Issues:**
- Too generic - doesn't tell user what's wrong
- Doesn't validate range (positive integers)
- Doesn't check for empty input
- Doesn't remove duplicates

**Fix:** Add detailed validation with specific error messages.

### 2. Missing Django Shinobi Schema Usage (Medium)

**Problem:**
The project lists `django-shinobi` in dependencies but the API views don't use Pydantic schemas for request/response validation.

**Current state:**
```python
# No Pydantic schemas, manual validation
def api_update_items(request):
    item_ids_str = request.POST.getlist("item_ids")
    # Manual parsing...
```

**Fix:** Implement Shinobi schemas for type-safe API validation.

### 3. No API Documentation (Low)

**Problem:**
No OpenAPI/Swagger documentation for API endpoints.

**Fix:** Add schema documentation using Shinobi's OpenAPI integration.

## Implementation Steps

### Step 1: Enhance Input Validation

**File:** `src/apps/api/views.py`

**Current `_parse_item_ids`:**

```python
def _parse_item_ids(item_ids_str: list[str]) -> tuple[list[int] | None, str | None]:
    try:
        return [int(i) for i in item_ids_str], None
    except (ValueError, TypeError):
        return None, "Invalid item IDs"
```

**Enhanced version:**

```python
from typing import tuple
from django.core.exceptions import ValidationError

def _parse_item_ids(item_ids_str: list[str]) -> tuple[list[int] | None, str | None]:
    """
    Parse and validate item IDs from request data.

    Returns:
        (parsed_ids, None) if successful
        (None, error_message) if validation fails

    Validation:
    - Input must not be empty
    - All IDs must be valid positive integers
    - Duplicates are removed
    """
    if not item_ids_str:
        return None, "No item IDs provided"

    if not isinstance(item_ids_str, list):
        return None, f"Invalid input type: expected list, got {type(item_ids_str).__name__}"

    parsed_ids = []
    seen = set()

    for idx, item_id in enumerate(item_ids_str, 1):
        # Check if string
        if not isinstance(item_id, str):
            return None, f"Item ID at position {idx} is not a string: {type(item_id).__name__}"

        # Check if empty
        if not item_id.strip():
            return None, f"Item ID at position {idx} is empty"

        # Try to parse as integer
        try:
            parsed = int(item_id)
        except (ValueError, TypeError):
            return None, f"Invalid item ID at position {idx}: '{item_id}' is not a valid integer"

        # Validate range (must be positive)
        if parsed <= 0:
            return None, f"Invalid item ID at position {idx}: {parsed} (must be positive)"

        # Remove duplicates while preserving order
        if parsed not in seen:
            seen.add(parsed)
            parsed_ids.append(parsed)

    # Validate we got at least one ID
    if not parsed_ids:
        return None, "No valid item IDs found after parsing"

    return parsed_ids, None
```

**Update view to use detailed errors:**

```python
@login_required
def api_update_items(request):
    """Update multiple items at once."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    item_ids_str = request.POST.getlist("item_ids")
    item_ids, error = _parse_item_ids(item_ids_str)

    if error:
        return JsonResponse({"error": error}, status=400)

    # Continue with processing...
```

### Step 2: Create Pydantic Schemas

**File:** `src/apps/api/schemas.py` (NEW)

```python
"""
Pydantic schemas for API request/response validation using Django Shinobi.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from enum import Enum


class ClassificationV2(str, Enum):
    """V2 classification options."""
    NIET_GEANALYSEERD = "Niet geanalyseerd"
    PUBLIC_DOMEIN = "Public Domain"
    GELICENTIEERD = "Gelicentieerd"
    CEILLIMIET = "Ceillimit"
    OVEREENKOMST = "Overeenkomst"


class WorkflowStatus(str, Enum):
    """Workflow status options."""
    TODO = "ToDo"
    IN_PROGRESS = "In Progress"
    DONE = "Done"
    BLOCKED = "Blocked"


# Request Schemas
class UpdateItemRequest(BaseModel):
    """Request schema for updating a single item."""
    material_id: int = Field(..., gt=0, description="Material ID (must be positive)")
    workflow_status: Optional[WorkflowStatus] = Field(None, description="New workflow status")
    v2_manual_classification: Optional[ClassificationV2] = Field(None, description="V2 classification")
    remarks: Optional[str] = Field(None, max_length=5000, description="Optional remarks")

    @field_validator("remarks")
    @classmethod
    def clean_remarks(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from remarks."""
        return v.strip() if v else None


class BulkUpdateRequest(BaseModel):
    """Request schema for bulk updating items."""
    item_ids: list[int] = Field(..., min_length=1, description="List of material IDs")
    workflow_status: Optional[WorkflowStatus] = None
    v2_manual_classification: Optional[ClassificationV2] = None
    remarks: Optional[str] = Field(None, max_length=5000)

    @field_validator("item_ids")
    @classmethod
    def validate_item_ids(cls, v: list[int]) -> list[int]:
        """Validate all item IDs are positive and remove duplicates."""
        if not v:
            raise ValueError("item_ids cannot be empty")

        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for item_id in v:
            if item_id <= 0:
                raise ValueError(f"Invalid item_id: {item_id} (must be positive)")
            if item_id not in seen:
                seen.add(item_id)
                unique_ids.append(item_id)

        return unique_ids


# Response Schemas
class ItemResponse(BaseModel):
    """Response schema for a single item."""
    material_id: int
    filename: Optional[str]
    title: Optional[str]
    workflow_status: WorkflowStatus
    v2_manual_classification: Optional[ClassificationV2]
    faculty: Optional[str]
    file_exists: Optional[bool]

    class Config:
        from_attributes = True  # Allow from ORM objects


class BulkUpdateResponse(BaseModel):
    """Response schema for bulk update operations."""
    success: bool
    updated_count: int
    errors: list[str] = []
    message: str


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error: str
    detail: Optional[str] = None
    status_code: int = Field(..., ge=100, le=599)
```

### Step 3: Update API Views to Use Schemas

**File:** `src/apps/api/views.py`

```python
from shinobi.decorators import schema
from shinobi.responses import JSONResponse
from .schemas import (
    UpdateItemRequest,
    BulkUpdateRequest,
    ItemResponse,
    BulkUpdateResponse,
    ErrorResponse,
)


@login_required
@schema(request=UpdateItemRequest, response=ItemResponse)
def api_update_item(request):
    """Update a single copyright item.

    Request body:
    - material_id: int (required)
    - workflow_status: Optional[WorkflowStatus]
    - v2_manual_classification: Optional[ClassificationV2]
    - remarks: Optional[str]

    Returns:
    - ItemResponse with updated item data
    """
    # Shinobi validates request and puts data in request.validated_data
    data = request.validated_data

    try:
        item = CopyrightItem.objects.get(material_id=data["material_id"])
    except CopyrightItem.DoesNotExist:
        return ErrorResponse(
            error="Item not found",
            detail=f"Material ID {data['material_id']} does not exist",
            status_code=404
        )

    # Update fields
    if data.get("workflow_status"):
        item.workflow_status = data["workflow_status"]
    if data.get("v2_manual_classification"):
        item.v2_manual_classification = data["v2_manual_classification"]
    if data.get("remarks") is not None:
        item.remarks = data["remarks"]

    item.save()

    return ItemResponse.model_validate(item)


@login_required
@schema(request=BulkUpdateRequest, response=BulkUpdateResponse)
def api_bulk_update_items(request):
    """Bulk update copyright items.

    Request body:
    - item_ids: list[int] (required, min_length=1)
    - workflow_status: Optional[WorkflowStatus]
    - v2_manual_classification: Optional[ClassificationV2]
    - remarks: Optional[str]

    Returns:
    - BulkUpdateResponse with success status and count
    """
    data = request.validated_data
    item_ids = data["item_ids"]

    updated_count = 0
    errors = []

    for item_id in item_ids:
        try:
            item = CopyrightItem.objects.get(material_id=item_id)

            if data.get("workflow_status"):
                item.workflow_status = data["workflow_status"]
            if data.get("v2_manual_classification"):
                item.v2_manual_classification = data["v2_manual_classification"]
            if data.get("remarks") is not None:
                item.remarks = data["remarks"]

            item.save()
            updated_count += 1

        except CopyrightItem.DoesNotExist:
            errors.append(f"Item {item_id} not found")
        except Exception as e:
            errors.append(f"Failed to update item {item_id}: {str(e)}")

    return BulkUpdateResponse(
        success=updated_count > 0,
        updated_count=updated_count,
        errors=errors,
        message=f"Updated {updated_count} items"
    )
```

### Step 4: Add OpenAPI Documentation

**File:** `src/apps/api/urls.py`

```python
from django.urls import path
from shinobi.docs import schema_view
from . import views

urlpatterns = [
    # API endpoints
    path("items/<int:material_id>/", views.api_update_item, name="update_item"),
    path("items/bulk/", views.api_bulk_update_items, name="bulk_update_items"),

    # OpenAPI documentation
    path("docs/", schema_view(title="Easy Access API", version="2.0.0"), name="api_docs"),
]
```

**Access documentation at:** `/api/docs/`

### Step 5: Add API Tests

**File:** `src/apps/api/tests/test_validation.py` (NEW)

```python
import pytest
from django.test import TestCase
from django.urls import reverse
from apps.core.models import CopyrightItem, WorkflowStatus


class APIValidationTestCase(TestCase):
    """Test API input validation."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )
        self.client.login(username="testuser", password="testpass123")

        self.item = CopyrightItem.objects.create(
            material_id=1234567,
            workflow_status=WorkflowStatus.TODO
        )

    def test_parse_item_ids_valid(self):
        """Test parsing valid item IDs."""
        from apps.api.views import _parse_item_ids

        ids, error = _parse_item_ids(["123", "456", "789"])
        self.assertIsNone(error)
        self.assertEqual(ids, [123, 456, 789])

    def test_parse_item_ids_empty(self):
        """Test parsing empty item IDs."""
        from apps.api.views import _parse_item_ids

        ids, error = _parse_item_ids([])
        self.assertIsNotNone(error)
        self.assertIn("No item IDs", error)

    def test_parse_item_ids_invalid_format(self):
        """Test parsing invalid item IDs."""
        from apps.api.views import _parse_item_ids

        ids, error = _parse_item_ids(["123", "abc", "456"])
        self.assertIsNotNone(error)
        self.assertIn("position 2", error)  # abc is at position 2

    def test_parse_item_ids_negative(self):
        """Test parsing negative item IDs."""
        from apps.api.views import _parse_item_ids

        ids, error = _parse_item_ids(["123", "-456", "789"])
        self.assertIsNotNone(error)
        self.assertIn("must be positive", error)

    def test_parse_item_ids_duplicates(self):
        """Test that duplicates are removed."""
        from apps.api.views import _parse_item_ids

        ids, error = _parse_item_ids(["123", "456", "123", "789"])
        self.assertIsNone(error)
        self.assertEqual(ids, [123, 456, 789])  # Duplicate 123 removed

    def test_api_update_item_valid(self):
        """Test updating item with valid data."""
        url = reverse("api:update_item", kwargs={"material_id": 1234567})

        response = self.client.post(
            url,
            data={
                "workflow_status": "Done",
                "remarks": "Test update"
            },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verify update
        self.item.refresh_from_db()
        self.assertEqual(self.item.workflow_status, WorkflowStatus.DONE)
        self.assertEqual(self.item.remarks, "Test update")

    def test_api_update_item_invalid_status(self):
        """Test updating item with invalid status."""
        url = reverse("api:update_item", kwargs={"material_id": 1234567})

        response = self.client.post(
            url,
            data={
                "workflow_status": "InvalidStatus"
            },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    def test_api_bulk_update_valid(self):
        """Test bulk update with valid data."""
        # Create more items
        for i in range(2, 5):
            CopyrightItem.objects.create(
                material_id=1234567 + i,
                workflow_status=WorkflowStatus.TODO
            )

        url = reverse("api:bulk_update_items")

        response = self.client.post(
            url,
            data={
                "item_ids": [1234567, 1234568, 1234569],
                "workflow_status": "In Progress"
            },
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["updated_count"], 3)
```

### Step 6: Add Rate Limiting (Optional Enhancement)

**File:** `src/apps/api/middleware.py` (NEW)

```python
from django.core.cache import cache
from django.http import JsonResponse
from loguru import logger


class RateLimitMiddleware:
    """Simple rate limiting middleware for API endpoints."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/"):
            # Rate limit: 100 requests per minute per user
            user_id = request.user.id if request.user.is_authenticated else request.META.get("REMOTE_ADDR")
            key = f"rate_limit:{user_id}"

            count = cache.get(key, 0)
            if count >= 100:
                logger.warning(f"Rate limit exceeded for user {user_id}")
                return JsonResponse(
                    {"error": "Rate limit exceeded"},
                    status=429
                )

            # Increment counter
            cache.set(key, count + 1, timeout=60)

        return self.get_response(request)
```

**Add to settings:**

```python
MIDDLEWARE = [
    # ... other middleware ...
    "apps.api.middleware.RateLimitMiddleware",  # Add before CommonMiddleware
]
```

## Testing

### 1. Test Input Validation

```bash
# Test with curl
curl -X POST http://localhost:8000/api/items/bulk/ \
  -H "Content-Type: application/json" \
  -d '{
    "item_ids": [123, 456, "abc"],
    "workflow_status": "Done"
  }'

# Expected: 400 error with specific validation message
```

### 2. Test OpenAPI Documentation

```bash
# Visit in browser
open http://localhost:8000/api/docs/

# Should see interactive API documentation
```

### 3. Run API Tests

```bash
uv run pytest src/apps/api/tests/test_validation.py -v
```

## Success Criteria

- [ ] Input validation provides specific error messages
- [ ] Pydantic schemas created for all API endpoints
- [ ] Django Shinobi decorators applied
- [ ] OpenAPI documentation available at `/api/docs/`
- [ ] All API tests pass
- [ ] Rate limiting implemented (optional)
- [ ] Error responses follow standard format
- [ ] Request validation happens before business logic

## Files Created/Modified

- `src/apps/api/schemas.py` - NEW: Pydantic schemas
- `src/apps/api/views.py` - Enhanced validation, Shinobi decorators
- `src/apps/api/tests/test_validation.py` - NEW: Validation tests
- `src/apps/api/middleware.py` - NEW: Rate limiting (optional)
- `src/apps/api/urls.py` - Add OpenAPI docs route

## Benefits

1. **Type safety** - Pydantic validates request/response types
2. **Better errors** - Specific validation messages
3. **Documentation** - Auto-generated OpenAPI docs
4. **Testability** - Easier to test with schemas
5. **Security** - Input validation prevents injection
6. **Developer experience** - Interactive API docs

---

**Next Task:** [Task 13: Test Coverage Expansion](13-test-coverage-expansion.md)
