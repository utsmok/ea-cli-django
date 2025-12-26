"""
Automatic cache invalidation using Django model signals.

When data changes, invalidate related cache keys automatically:
- CopyrightItem changes → invalidate filter_counts, faculty queries
- Course changes → invalidate osiris_course cache
- Person changes → invalidate osiris_person cache

This provides automatic cache invalidation without manual calls.
Cache failures are logged but don't break the application.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from loguru import logger

from apps.core.models import CopyrightItem, Course, Person
from apps.core.services.cache_service import invalidate_pattern


@receiver(post_save, sender=CopyrightItem)
@receiver(post_delete, sender=CopyrightItem)
def invalidate_copyright_item_cache(sender, **kwargs):
    """
    Invalidate query caches when CopyrightItem changes.

    This ensures filter counts and aggregations stay fresh.
    Triggered automatically on create, update, and delete.
    """
    try:
        # Invalidate all filter count caches
        invalidate_pattern("filter_counts")

        # Invalidate faculty queries
        invalidate_pattern("faculties")

        logger.debug(
            f"Invalidated copyright item caches after {sender.__name__} change"
        )
    except Exception as e:
        # Don't break the app if cache invalidation fails
        logger.error(f"Failed to invalidate cache: {e}")


@receiver(post_save, sender=Course)
@receiver(post_delete, sender=Course)
def invalidate_course_cache(sender, **kwargs):
    """
    Invalidate course cache when Course model changes.

    Forces refresh of Osiris course data on next fetch.
    """
    try:
        invalidate_pattern("osiris_course")
        logger.debug(f"Invalidated course caches after {sender.__name__} change")
    except Exception as e:
        logger.error(f"Failed to invalidate course cache: {e}")


@receiver(post_save, sender=Person)
@receiver(post_delete, sender=Person)
def invalidate_person_cache(sender, **kwargs):
    """
    Invalidate person cache when Person model changes.

    Forces refresh of people.utwente.nl data on next fetch.
    """
    try:
        invalidate_pattern("osiris_person")
        logger.debug(f"Invalidated person caches after {sender.__name__} change")
    except Exception as e:
        logger.error(f"Failed to invalidate person cache: {e}")
