# Task 3: Settings System with YAML Persistence

## Overview

Create a comprehensive settings system with database models, YAML import/export, and admin UI.

**Current Status:** ✅ **COMPLETED**

**Current State:** Settings app with database models, admin interface, YAML import/export

## What Was Implemented

### Core Features ✅

- Database-backed settings (models)
- YAML import/export for backup/migration
- Admin interface with fieldsets
- Built-in caching (15 min TTL)
- Type validation (string, integer, float, boolean, JSON)
- Sensitive value masking (API keys)
- Category-based organization
- Audit trail (updated_by, timestamps)

### Simplified Approach (Per User Requirements)

Based on user feedback, we skipped:
- Faculty-specific overrides
- User-facing settings UI (non-admin)
- API credential testing
- Sheet export settings
- Complex validation rules

Focus was on core features that provide immediate value.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                YAML File                        │
│        (Backup/Migrate/Version Control)         │
└───────────────────┬─────────────────────────────┘
                    │ import/export
                    ↓
┌─────────────────────────────────────────────────┐
│              Setting Model                      │
│         (CRUD + Cache + Validation)             │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│            Django Admin                         │
│     (/admin/settings/setting/)                  │
└─────────────────────────────────────────────────┘
```

## Implementation Details

### Step 1: Created Settings App ✅

**Command:** `uv run python src/manage.py startapp settings src/apps`

**Files Created:**
- `src/apps/settings/apps.py` - AppConfig
- `src/apps/settings/models.py` - Setting model
- `src/apps/settings/admin.py` - Admin interface
- `src/apps/settings/migrations/0001_initial.py` - Initial migration

### Step 2: Setting Model ✅

**File:** `src/apps/settings/models.py`

```python
class Setting(models.Model):
    """Database-backed configuration with YAML import/export."""

    class ValueType(models.TextChoices):
        STRING = 'string', 'String'
        INTEGER = 'integer', 'Integer'
        FLOAT = 'float', 'Float'
        BOOLEAN = 'boolean', 'Boolean'
        JSON = 'json', 'JSON (Array/Object)'

    # Core fields
    key = models.CharField(max_length=200, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    value = models.JSONField()
    value_type = models.CharField(max_length=20, choices=ValueType.choices)
    default_value = models.JSONField()

    # Organization
    category = models.CharField(max_length=100, default='general', db_index=True)

    # Validation
    choices = models.JSONField(null=True, blank=True)  # ENUM-like behavior
    is_required = models.BooleanField(default=False)

    # Security
    is_sensitive = models.BooleanField(default=False)  # Mask API keys in UI

    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    # Class methods
    @classmethod
    def get(cls, key, default=None):
        """Get setting value with caching (15 min TTL)."""

    @classmethod
    def set(cls, key, value, user=None, **kwargs):
        """Set setting value and invalidate cache."""

    @classmethod
    def export_to_yaml(cls, include_sensitive=False):
        """Export all settings to YAML format."""

    @classmethod
    def import_from_yaml(cls, yaml_content, overwrite=False, user=None):
        """Import settings from YAML content."""
```

**Key Features:**
- Built-in caching via `cache.get(f"setting:{key}")` (15 min TTL)
- Automatic cache invalidation on save
- Validation for required settings and allowed choices
- Sensitive value masking in admin UI

### Step 3: Admin Interface ✅

**File:** `src/apps/settings/admin.py`

**Features:**
- Organized fieldsets (Basic Info, Value Config, Validation, Security, Audit)
- List filters by category, value_type, is_required, is_sensitive
- Search by key, name, description
- Sensitive value masking (`********` for is_sensitive=True)
- YAML export action for selected settings
- Read-only key after creation
- Automatic updated_by tracking

**Fieldsets:**
1. Basic Information: key, name, description, category
2. Value Configuration: value_type, value, default_value, choices
3. Validation: is_required
4. Security: is_sensitive
5. Audit Trail: created_at, updated_at, updated_by

### Step 4: YAML Import/Export ✅

**Export:**
```python
Setting.export_to_yaml(include_sensitive=False)
```

**Output format:**
```yaml
general:
  canvas.api_token:
    value: ********
    type: string
    name: Canvas API Token
    description: API token for Canvas LMS access

enrichment:
  osiris.base_url:
    value: https://utwente.osiris-student.nl
    type: string
    name: Osiris Base URL
    description: Base URL for Osiris API
```

**Import:**
```python
results = Setting.import_from_yaml(yaml_content, overwrite=False, user=request.user)
# Returns: {'created': 5, 'updated': 2, 'skipped': 3, 'errors': 0}
```

**Features:**
- Category-based organization
- Optional sensitive value masking on export
- Overwrite control (skip existing or update)
- Error handling with detailed statistics
- User attribution for changes

### Step 5: Testing ✅

Comprehensive testing completed:
- ✅ CRUD operations (create, read, update, delete)
- ✅ Type validation (string, integer, float, boolean, JSON)
- ✅ Choice validation
- ✅ Required field validation
- ✅ Sensitive value masking
- ✅ Caching (get/set with cache invalidation)
- ✅ YAML export/import
- ✅ Admin interface functionality

**Test Results:**
- All operations working correctly
- Cache invalidation confirmed
- YAML import/export tested with real data
- Admin UI renders and functions properly

## Usage Examples

### Setting Values

```python
from apps.settings.models import Setting

# Simple value
Setting.set('canvas.api_token', 'abc123...', user=request.user)

# With metadata
Setting.set(
    'export.batch_size',
    100,
    user=request.user,
    name='Export Batch Size',
    category='export',
    value_type='integer'
)

# Get value (with caching)
api_token = Setting.get('canvas.api_token')
batch_size = Setting.get('export.batch_size', default=50)  # with default
```

### YAML Export

```python
from apps.settings.models import Setting
from django.http import HttpResponse

yaml_content = Setting.export_to_yaml(include_sensitive=False)

response = HttpResponse(yaml_content, content_type='text/yaml')
response['Content-Disposition'] = 'attachment; filename="settings_export.yaml"'
return response
```

### YAML Import

```python
from apps.settings.models import Setting

with open('settings_backup.yaml') as f:
    yaml_content = f.read()

results = Setting.import_from_yaml(
    yaml_content,
    overwrite=True,  # Update existing settings
    user=request.user
)

print(f"Created: {results['created']}, Updated: {results['updated']}")
```

## Files Created/Modified

**Created:**
- `src/apps/settings/__init__.py`
- `src/apps/settings/apps.py`
- `src/apps/settings/models.py`
- `src/apps/settings/admin.py`
- `src/apps/settings/migrations/0001_initial.py`

**Modified:**
- `src/config/settings.py` - Added `apps.settings` to INSTALLED_APPS
- `pyproject.toml` - Added `pyyaml` dependency

## Success Criteria

- ✅ Settings app created and registered in INSTALLED_APPS
- ✅ Database models created and migrated
- ✅ Setting.get() and Setting.set() class methods working
- ✅ YAML export/import working
- ✅ Admin interface configured with fieldsets
- ✅ Built-in caching (15 min TTL)
- ✅ Comprehensive testing completed

## Next Steps (Future Enhancements)

Out of scope for current implementation but potential future work:
- User-facing settings UI (non-admin)
- Faculty-specific overrides
- API credential testing endpoint
- Settings validation against external APIs
- Settings versioning with rollback
- Settings change history/audit log

---

**Next Task:** [Task 4: Template Partials](04-template-partials.md) (Completed - kept include approach)
