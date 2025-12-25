"""
Admin interface for Settings model.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Q
from .models import Setting

@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    """Admin interface for Setting model."""

    list_display = [
        'key',
        'name',
        'category',
        'value_type',
        'display_value_safe',
        'is_required',
        'is_sensitive',
        'updated_at'
    ]
    list_filter = ['category', 'value_type', 'is_required', 'is_sensitive']
    search_fields = ['key', 'name', 'description']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('key', 'name', 'description', 'category')
        }),
        ('Value Configuration', {
            'fields': (
                'value_type',
                'value',
                'default_value',
                'choices'
            )
        }),
        ('Validation', {
            'fields': ('is_required',),
            'classes': ('collapse',)
        }),
        ('Security', {
            'fields': ('is_sensitive',),
            'description': 'Mark sensitive values like API keys to hide them in the UI'
        }),
        ('Audit Trail', {
            'fields': ('created_at', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

    def display_value_safe(self, obj):
        """
        Display value with HTML formatting.
        Masks sensitive values.
        """
        if obj.is_sensitive and obj.value:
            return format_html(
                '<span style="font-family: monospace; color: #666;">********</span>'
            )

        # Format JSON for better readability
        if obj.value_type == Setting.ValueType.JSON:
            if isinstance(obj.value, dict):
                return format_html(
                    '<pre style="font-size: 11px; margin: 0;">{}</pre>',
                    str(obj.value)[:200]  # Truncate long JSON
                )
            elif isinstance(obj.value, list):
                return format_html(
                    '<span style="font-family: monospace;">[{} items]</span>',
                    len(obj.value)
                )

        # Format regular values
        value = obj.value
        if value is None:
            return format_html('<span style="color: #999;">(empty)</span>')

        if isinstance(value, str):
            return format_html(
                '<span style="font-family: monospace;">{}</span>',
                str(value)[:100]  # Truncate long strings
            )
        elif isinstance(value, bool):
            color = 'green' if value else 'red'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{}</span>',
                color,
                str(value)
            )

        return format_html('<span>{}</span>', str(value)[:100])

    display_value_safe.short_description = 'Value'

    def get_readonly_fields(self, request, obj=None):
        """Make key readonly after creation."""
        if obj:  # Editing existing object
            return self.readonly_fields + ['key']
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        """Save the user who made the change."""
        if not change:  # Creating new object
            obj.updated_by = request.user
        else:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Add custom admin actions
@admin.action(description='Export selected settings to YAML')
def export_yaml(modeladmin, request, queryset):
    """
    Admin action to export selected settings as YAML.
    """
    import yaml
    from django.http import HttpResponse

    settings_dict = {}
    for setting in queryset:
        if setting.category not in settings_dict:
            settings_dict[setting.category] = {}
        settings_dict[setting.category][setting.key] = {
            'value': setting.value,
            'type': setting.value_type,
            'name': setting.name,
            'description': setting.description,
        }

    yaml_content = yaml.dump(
        settings_dict,
        default_flow_style=False,
        sort_keys=False
    )

    response = HttpResponse(yaml_content, content_type='text/yaml')
    response['Content-Disposition'] = 'attachment; filename="settings_export.yaml"'
    return response


SettingAdmin.actions = [export_yaml]
