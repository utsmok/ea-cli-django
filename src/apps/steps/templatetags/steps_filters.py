"""Custom template filters for the steps app."""

from django import template

register = template.Library()


@register.filter
def filename(value):
    """Extract the filename from a file path."""
    from pathlib import Path

    if not value:
        return ""
    return Path(value).name


@register.filter
def get(dictionary, key):
    """
    Get a value from a dictionary using a variable key.

    Usage: {{ mydict|get:key_variable }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)
