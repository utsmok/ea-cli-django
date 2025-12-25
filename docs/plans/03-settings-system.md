# Task 3: Settings System with YAML Persistence

## Overview

Create a comprehensive settings system with database models, YAML import/export, user/admin UIs, and Canvas API key validation. Migrate useful settings from legacy `settings.yaml`.

**Current Status:** ❌ **NOT STARTED**

**Current State:** Hardcoded settings in `config/university.py`, `export_config.py`, `models.py`

**Goal:** Dynamic, user-editable settings with YAML backup/restore

## Features

- Database-backed settings (models)
- YAML import/export for backup/migration
- User-facing settings UI (non-admin)
- Admin-only settings UI
- Faculty-specific overrides
- API credential management with testing
- Integration with existing export/config systems

## Architecture

```
┌─────────────────────────────────────────────────┐
│                YAML File                        │
│        (Backup/Migrate/Version Control)         │
└───────────────────┬─────────────────────────────┘
                    │ import/export
                    ↓
┌─────────────────────────────────────────────────┐
│           SettingsManager Service               │
│         (CRUD + Cache + Validation)             │
└──────┬────────────────────────────────────┬─────┘
       │                                    │
       ↓                                    ↓
┌──────────────────┐              ┌──────────────────┐
│  Setting Model   │              │ FacultyOverride  │
│  (Global/Category│              │  (Per-Faculty)   │
└──────────────────┘              └──────────────────┘
       │                                    │
       ↓                                    ↓
┌─────────────────────────────────────────────────┐
│            UI Layer (HTMX/Alpine)               │
│  - User Settings (/settings/user)               │
│  - Admin Settings (/admin/settings/)            │
└─────────────────────────────────────────────────┘
```

## Implementation Steps

### Step 1: Create Settings App

```bash
# Create new Django app
uv run python src/manage.py startapp settings src/apps
```

**File:** `src/apps/settings/__init__.py` (auto-created)

### Step 2: Create Settings Models

**File:** `src/apps/settings/models.py`

```python
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import json

User = get_user_model()


class SettingCategory(models.Model):
    """Group related settings together."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']
        verbose_name_plural = "Setting Categories"

    def __str__(self):
        return self.name


class Setting(models.Model):
    """Individual setting with value and metadata."""

    class ValueType(models.TextChoices):
        STRING = 'string', 'String'
        INTEGER = 'integer', 'Integer'
        FLOAT = 'float', 'Float'
        BOOLEAN = 'boolean', 'Boolean'
        JSON = 'json', 'JSON'
        ENUM = 'enum', 'Enumeration'

    category = models.ForeignKey(
        SettingCategory,
        on_delete=models.CASCADE,
        related_name='settings'
    )
    key = models.CharField(max_length=200)
    value = models.JSONField()
    value_type = models.CharField(max_length=20, choices=ValueType.choices)
    default_value = models.JSONField()

    # For ENUM types
    enum_choices = models.JSONField(null=True, blank=True)

    # Metadata
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_required = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False)  # Hide in UI (API keys)

    # Faculty overrides
    allow_faculty_override = models.BooleanField(default=False)

    # Validation
    validation_regex = models.CharField(max_length=500, blank=True)
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        unique_together = ('category', 'key')
        ordering = ['category', 'key']

    def __str__(self):
        return f"{self.category.name}/{self.key}"

    def clean(self):
        """Validate setting value."""
        import re
        # Validate regex
        if self.validation_regex and isinstance(self.value, str):
            if not re.match(self.validation_regex, self.value):
                raise ValidationError(f"Value does not match pattern: {self.validation_regex}")

        # Validate min/max for numeric
        if self.value_type in [self.ValueType.INTEGER, self.ValueType.FLOAT]:
            if self.min_value is not None and self.value < self.min_value:
                raise ValidationError(f"Value must be >= {self.min_value}")
            if self.max_value is not None and self.value > self.max_value:
                raise ValidationError(f"Value must be <= {self.max_value}")


class FacultyOverride(models.Model):
    """Faculty-specific override for a setting."""
    setting = models.ForeignKey(
        Setting,
        on_delete=models.CASCADE,
        related_name='overrides'
    )
    faculty = models.ForeignKey(
        'core.Faculty',
        on_delete=models.CASCADE
    )
    override_value = models.JSONField()

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    class Meta:
        unique_together = ('setting', 'faculty')
        verbose_name = "Faculty Override"

    def __str__(self):
        return f"{self.faculty.abbreviation} -> {self.setting.key}"


class APICredential(models.Model):
    """Store API credentials securely."""

    class Provider(models.TextChoices):
        CANVAS = 'canvas', 'Canvas LMS'
        OSIRIS = 'osiris', 'Osiris API'

    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        unique=True
    )
    api_key = models.CharField(max_length=500)
    api_url = models.URLField(max_length=500)
    is_active = models.BooleanField(default=True)
    last_tested = models.DateTimeField(null=True, blank=True)
    test_result = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "API Credential"

    def __str__(self):
        return f"{self.get_provider_display()} credentials"
```

### Step 3: Create Settings Manager Service

**File:** `src/apps/settings/services/settings_manager.py`

```python
from typing import Any, Optional
from django.core.cache import cache
from .models import Setting, FacultyOverride


class SettingsManager:
    """Centralized settings access with caching and overrides."""

    @staticmethod
    def get(
        key: str,
        faculty: Optional['core.Faculty'] = None,
        default: Any = None
    ) -> Any:
        """
        Get setting value with optional faculty override.
        """
        cache_key = f"setting:{key}:{faculty.abbreviation if faculty else 'default'}"
        value = cache.get(cache_key)

        if value is not None:
            return value

        try:
            setting = Setting.objects.select_related('category').get(key=key)

            # Check for faculty override
            if faculty and setting.allow_faculty_override:
                override = FacultyOverride.objects.filter(
                    setting=setting,
                    faculty=faculty
                ).first()
                if override:
                    value = override.override_value
                else:
                    value = setting.value
            else:
                value = setting.value

            cache.set(cache_key, value, timeout=300)
            return value

        except Setting.DoesNotExist:
            return default

    @staticmethod
    def set(key: str, value: Any, user=None) -> None:
        """Update setting value and invalidate cache."""
        try:
            setting = Setting.objects.get(key=key)
            setting.value = value
            setting.updated_by = user
            setting.save()
            SettingsManager.invalidate(key)
        except Setting.DoesNotExist:
            raise ValueError(f"Setting not found: {key}")

    @staticmethod
    def invalidate(key: str) -> None:
        """Invalidate cache for a setting."""
        cache.delete_pattern(f"setting:{key}:*")

    @staticmethod
    def export_to_yaml() -> str:
        """Export all settings to YAML format."""
        import yaml
        from collections import defaultdict

        settings = Setting.objects.select_related('category').all()
        output = defaultdict(lambda: {'description': '', 'settings': {}})

        for setting in settings:
            cat_data = output[setting.category.slug]
            cat_data['description'] = setting.category.description
            cat_data['settings'][setting.key] = {
                'value': setting.value,
                'type': setting.value_type,
                'name': setting.name,
            }

        return yaml.dump(dict(output), default_flow_style=False)

    @staticmethod
    def import_from_yaml(yaml_content: str, create_categories=True) -> dict:
        """Import settings from YAML content."""
        import yaml

        data = yaml.safe_load(yaml_content)
        stats = {'created': 0, 'updated': 0, 'errors': []}

        for cat_slug, cat_data in data.items():
            # Create or get category
            if create_categories:
                category, _ = SettingCategory.objects.get_or_create(
                    slug=cat_slug,
                    defaults={
                        'name': cat_slug.replace('_', ' ').title(),
                        'description': cat_data.get('description', ''),
                    }
                )
            else:
                category = SettingCategory.objects.get(slug=cat_slug)

            # Import settings
            for key, setting_data in cat_data.get('settings', {}).items():
                try:
                    setting, created = Setting.objects.get_or_create(
                        category=category,
                        key=key,
                        defaults={
                            'value': setting_data['value'],
                            'value_type': setting_data.get('type', 'string'),
                            'name': setting_data.get('name', key),
                        }
                    )
                    if created:
                        stats['created'] += 1
                    else:
                        setting.value = setting_data['value']
                        setting.save()
                        stats['updated'] += 1
                except Exception as e:
                    stats['errors'].append(f"{key}: {str(e)}")

        return stats


# Global settings instance
settings = SettingsManager()
```

### Step 4: Create API Validator

**File:** `src/apps/settings/services/api_validator.py`

```python
import httpx
from django.utils import timezone
from ..models import APICredential


async def test_canvas_api(credentials: APICredential) -> dict:
    """Test Canvas API credentials."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{credentials.api_url}/courses",
                headers={"Authorization": f"Bearer {credentials.api_key}"},
                timeout=10.0
            )

            result = {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'message': 'Valid credentials' if response.status_code == 200 else 'Authentication failed',
                'timestamp': timezone.now().isoformat(),
            }

            if response.status_code == 200:
                courses = response.json()
                result['courses_accessible'] = len(courses)

            credentials.test_result = result
            credentials.last_tested = timezone.now()
            credentials.save()

            return result

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'timestamp': timezone.now().isoformat(),
        }
```

### Step 5: Migrate Legacy Settings

**File:** `src/apps/settings/management/commands/migrate_legacy_settings.py` (NEW)

```python
from django.core.management.base import BaseCommand
from pathlib import Path
import yaml

class Command(BaseCommand):
    help = 'Migrate settings from legacy settings.yaml'

    def add_arguments(self, parser):
        parser.add_argument('yaml_path', type=str, help='Path to legacy settings.yaml')

    def handle(self, *args, **options):
        from apps.settings.services.settings_manager import SettingsManager

        yaml_path = Path(options['yaml_path'])

        with open(yaml_path) as f:
            legacy_settings = yaml.safe_load(f)

        # Migrate university settings
        if 'university' in legacy_settings:
            self.migrate_university_settings(legacy_settings['university'])

        # Migrate enrichment settings
        if 'enrichment' in legacy_settings:
            self.migrate_enrichment_settings(legacy_settings['enrichment'])

        self.stdout.write(self.style.SUCCESS('Settings migrated successfully'))

    def migrate_university_settings(self, data):
        """Migrate university section."""
        from apps.settings.models import Setting, SettingCategory

        category, _ = SettingCategory.objects.get_or_create(
            slug='university',
            defaults={'name': 'University', 'order': 1}
        )

        # Create individual settings
        for key, value in data.items():
            Setting.objects.get_or_create(
                category=category,
                key=key,
                defaults={
                    'value': value,
                    'value_type': self.determine_type(value),
                    'name': key.replace('_', ' ').title(),
                }
            )
```

Run migration:
```bash
uv run python src/manage.py migrate_legacy_settings ea-cli/settings.yaml
```

### Step 6: Create Admin Interface

**File:** `src/apps/settings/admin.py`

```python
from django.contrib import admin
from .models import Setting, SettingCategory, FacultyOverride, APICredential


@admin.register(SettingCategory)
class SettingCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'order']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'name', 'category', 'value_type', 'is_required']
    list_filter = ['category', 'value_type']
    search_fields = ['key', 'name', 'description']


@admin.register(APICredential)
class APICredentialAdmin(admin.ModelAdmin):
    list_display = ['provider', 'is_active', 'last_tested']
    actions = ['test_credentials']

    def test_credentials(self, request, queryset):
        """Admin action to test API credentials."""
        from asgiref.sync import async_to_sync
        from .services.api_validator import test_canvas_api

        for cred in queryset:
            if cred.provider == 'canvas':
                result = async_to_sync(test_canvas_api)(cred)
                self.message_user(request, f"Tested {cred.provider}: {result.get('message', 'Failed')}")
```

### Step 7: Create User Settings UI

**File:** `src/apps/settings/templates/settings/base.html` (NEW)

```html
{% extends "base.html" %}

{% block title %}Settings{% endblock %}

{% block content %}
<div class="container mx-auto p-6" x-data="settingsApp()">
  <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
    <!-- Sidebar: Categories -->
    <nav class="space-y-2">
      <template x-for="category in categories" :key="category.id">
        <button @click="activeCategory = category.id"
                :class="activeCategory === category.id ? 'btn btn-active' : 'btn btn-ghost'"
                class="btn btn-justify w-full"
                x-text="category.name">
        </button>
      </template>
    </nav>

    <!-- Main: Settings -->
    <div class="md:col-span-3">
      <div class="flex justify-between items-center mb-4">
        <h1 class="text-2xl font-bold" x-text="activeCategoryName"></h1>
        <div class="space-x-2">
          <button @click="exportSettings" class="btn btn-outline btn-sm">Export YAML</button>
          <button @click="showImportModal = true" class="btn btn-primary btn-sm">Import YAML</button>
        </div>
      </div>

      <div class="space-y-4">
        <template x-for="setting in activeSettings" :key="setting.id">
          <div class="card bg-base-100 shadow-sm">
            <div class="card-body p-4">
              <label class="label">
                <span class="label-text font-medium" x-text="setting.name"></span>
              </label>

              <input x-if="setting.value_type === 'string'"
                     type="text" :x-model="setting.value"
                     @change="updateSetting(setting)"
                     class="input input-bordered w-full">

              <input x-if="setting.value_type === 'boolean'"
                     type="checkbox" :x-model="setting.value"
                     @change="updateSetting(setting)"
                     class="toggle toggle-primary">

              <span x-show="setting.description"
                    class="text-xs text-base-content/60 mt-2"
                    x-text="setting.description"></span>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</div>

<script>
function settingsApp() {
  return {
    categories: [],
    activeCategory: null,
    showImportModal: false,
    importYaml: '',

    init() {
      fetch('/settings/api/categories')
        .then(r => r.json())
        .then(data => {
          this.categories = data;
          this.activeCategory = data[0]?.id;
        });
    },

    get activeSettings() {
      if (!this.activeCategory) return [];
      return this.categories.find(c => c.id === this.activeCategory)?.settings || [];
    },

    get activeCategoryName() {
      return this.categories.find(c => c.id === this.activeCategory)?.name || '';
    },

    updateSetting(setting) {
      htmx.ajax('POST', `/settings/api/update/${setting.id}`, {
        values: { value: setting.value }
      });
    },

    exportSettings() {
      window.location.href = '/settings/api/export';
    },

    importSettings() {
      fetch('/settings/api/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ yaml: this.importYaml })
      })
      .then(r => r.json())
      .then(data => {
        alert(`Imported: ${data.created} created, ${data.updated} updated`);
        window.location.reload();
      });
    }
  };
}
</script>
{% endblock %}
```

### Step 8: Create Settings Views/URLs

**File:** `src/apps/settings/views.py`

```python
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Setting
import json

@login_required
def user_settings(request):
    """User settings page."""
    categories = SettingCategory.objects.prefetch_related('settings').all()
    context = {'categories': categories}
    return render(request, 'settings/base.html', context)


def api_categories(request):
    """API endpoint for categories."""
    categories = list(SettingCategory.objects.prefetch_related('settings').all().values(
        'id', 'name', 'slug', 'description',
        settings__id, settings__key, settings__name, settings__value,
        settings__value_type, settings__description
    ))
    # Group settings under categories
    # ... implementation ...
    return JsonResponse(categories, safe=False)
```

**File:** `src/apps/settings/urls.py`

```python
from django.urls import path
from . import views

app_name = 'settings'

urlpatterns = [
    path('', views.user_settings, name='user'),
    path('api/categories', views.api_categories, name='api_categories'),
]
```

Include in main URLs:
**File:** `src/config/urls.py`

```python
urlpatterns = [
    # ...
    path('settings/', include('apps.settings.urls')),
]
```

## Success Criteria

- [ ] Settings app created and registered
- [ ] Database models created
- [ ] SettingsManager service implemented
- [ ] YAML import/export working
- [ ] Legacy settings migration command created
- [ ] Admin interface configured
- [ ] User-facing UI created (HTMX/Alpine.js)
- [ ] Canvas API key testing working

## Estimated Time

- **App creation + models:** 6 hours
- **SettingsManager service:** 6 hours
- **API validator:** 4 hours
- **Legacy migration:** 4 hours
- **Admin interface:** 3 hours
- **User UI:** 10 hours
- **Testing:** 6 hours

**Total: 4-5 days**

---

**Next Task:** [Task 5: Error Handling](05-error-handling.md)
