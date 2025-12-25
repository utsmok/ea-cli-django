"""
Settings System - Database-backed configuration with YAML import/export.

Simple key-value store for platform settings that can be edited via admin
and backed up/restored via YAML files.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.cache import cache
import json
import yaml

User = get_user_model()


class Setting(models.Model):
    """
    A single platform setting with typed value.

    Examples:
        - 'canvas.api_token': 'abc123...'
        - 'osiris.base_url': 'https://utwente.osiris-student.nl'
        - 'export.batch_size': 100
        - 'cache.enabled': true
    """

    class ValueType(models.TextChoices):
        STRING = 'string', 'String'
        INTEGER = 'integer', 'Integer'
        FLOAT = 'float', 'Float'
        BOOLEAN = 'boolean', 'Boolean'
        JSON = 'json', 'JSON (Array/Object)'

    # Setting identifier (e.g., 'canvas.api_token')
    key = models.CharField(max_length=200, unique=True, db_index=True)

    # Human-readable name
    name = models.CharField(max_length=200)

    # Description for admins
    description = models.TextField(blank=True)

    # Value type
    value_type = models.CharField(
        max_length=20,
        choices=ValueType.choices,
        default=ValueType.STRING
    )

    # The actual value (stored as JSON for flexibility)
    value = models.JSONField()

    # Default value (used when resetting)
    default_value = models.JSONField()

    # Category/grouping for organization
    category = models.CharField(
        max_length=100,
        default='general',
        db_index=True,
        help_text='Category for grouping related settings'
    )

    # Is this value sensitive (API keys, secrets)?
    is_sensitive = models.BooleanField(
        default=False,
        help_text='Sensitive values are masked in the admin UI'
    )

    # Is this setting required?
    is_required = models.BooleanField(
        default=False,
        help_text='Required settings must have a non-empty value'
    )

    # Validation: allowed choices for ENUM-like behavior
    choices = models.JSONField(
        null=True,
        blank=True,
        help_text='List of allowed values (null = any value allowed)'
    )

    # Audit trail
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_settings'
    )

    class Meta:
        verbose_name = "Setting"
        verbose_name_plural = "Settings"
        ordering = ['category', 'key']

    def __str__(self):
        return f"{self.category}/{self.key}"

    def save(self, *args, **kwargs):
        """Validate and cache setting on save."""
        self.full_clean()
        super().save(*args, **kwargs)

        # Invalidate cache
        cache.delete(f"setting:{self.key}")

    def clean(self):
        """Validate setting value."""
        # Check required settings have values
        if self.is_required and not self.value:
            raise ValidationError({"value": "This setting is required and cannot be empty."})

        # Validate against choices if provided
        if self.choices and self.value not in self.choices:
            raise ValidationError({
                "value": f"Value must be one of: {self.choices}"
            })

        # Type-specific validation
        try:
            if self.value_type == self.ValueType.INTEGER:
                int(self.value)
            elif self.value_type == self.ValueType.FLOAT:
                float(self.value)
            elif self.value_type == self.ValueType.BOOLEAN:
                bool(self.value)
            elif self.value_type == self.ValueType.JSON:
                if not isinstance(self.value, (dict, list)):
                    raise ValidationError("JSON type requires a dict or list value")
        except (ValueError, TypeError) as e:
            raise ValidationError({"value": f"Invalid {self.value_type} value: {e}"})

    @property
    def display_value(self):
        """
        Get human-readable value for admin display.

        Masks sensitive values and converts types appropriately.
        """
        if self.is_sensitive and self.value:
            return "********"  # Mask API keys and secrets

        # Return value as-is for most types
        return self.value

    @classmethod
    def get(cls, key, default=None):
        """
        Get a setting value with caching.

        Usage:
            api_token = Setting.get('canvas.api_token')
            batch_size = Setting.get('export.batch_size', 50)
        """
        # Try cache first
        cache_key = f"setting:{key}"
        cached_value = cache.get(cache_key)
        if cached_value is not None:
            return cached_value

        # Fetch from database
        try:
            setting = cls.objects.get(key=key)
            value = setting.value
            # Cache for 15 minutes
            cache.set(cache_key, value, 900)
            return value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value, user=None, **kwargs):
        """
        Set a setting value.

        Usage:
            Setting.set('canvas.api_token', 'abc123', user=request.user)
            Setting.set('cache.enabled', True)
        """
        setting, created = cls.objects.get_or_create(
            key=key,
            defaults={
                'name': kwargs.get('name', key),
                'value': value,
                'category': kwargs.get('category', 'general'),
                'value_type': kwargs.get('value_type', cls.ValueType.STRING),
                'default_value': value,
            }
        )

        if not created:
            setting.value = value
            if user:
                setting.updated_by = user
            setting.save()

        return setting

    @classmethod
    def export_to_yaml(cls, include_sensitive=False):
        """
        Export all settings to YAML format.

        Args:
            include_sensitive: If False, sensitive values are exported as '********'

        Returns:
            YAML string
        """
        settings_dict = {}
        for setting in cls.objects.all():
            if setting.is_sensitive and not include_sensitive:
                value = "********"  # Mask sensitive values
            else:
                value = setting.value

            # Organize by category
            if setting.category not in settings_dict:
                settings_dict[setting.category] = {}
            settings_dict[setting.category][setting.key] = {
                'value': value,
                'type': setting.value_type,
                'name': setting.name,
                'description': setting.description,
            }

        return yaml.dump(
            settings_dict,
            default_flow_style=False,
            sort_keys=False
        )

    @classmethod
    def import_from_yaml(cls, yaml_content, overwrite=False, user=None):
        """
        Import settings from YAML content.

        Args:
            yaml_content: YAML string to import
            overwrite: If False, skip existing settings. If True, overwrite.
            user: User to attribute changes to

        Returns:
            dict with 'created', 'updated', 'skipped', 'errors' counts
        """
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML: {e}")

        if not isinstance(data, dict):
            raise ValidationError("YAML must contain a dictionary of settings")

        results = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }

        for category, settings in data.items():
            if not isinstance(settings, dict):
                results['errors'] += 1
                continue

            for key, setting_data in settings.items():
                try:
                    if not isinstance(setting_data, dict):
                        results['errors'] += 1
                        continue

                    value = setting_data.get('value')
                    if value is None:
                        results['errors'] += 1
                        continue

                    # Check if setting exists
                    existing = cls.objects.filter(key=key).first()

                    if existing:
                        if overwrite:
                            existing.value = value
                            if user:
                                existing.updated_by = user
                            existing.save()
                            results['updated'] += 1
                        else:
                            results['skipped'] += 1
                    else:
                        # Create new setting
                        cls.objects.create(
                            key=key,
                            value=value,
                            category=category,
                            name=setting_data.get('name', key),
                            description=setting_data.get('description', ''),
                            value_type=setting_data.get('type', 'string'),
                            default_value=value,
                            updated_by=user
                        )
                        results['created'] += 1

                except Exception as e:
                    results['errors'] += 1
                    # Log error but continue processing other settings
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error importing setting {key}: {e}")

        return results
