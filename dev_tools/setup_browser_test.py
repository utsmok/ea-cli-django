import os

import django
from django.contrib.auth import get_user_model

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.core.models import CopyrightItem, EnrichmentStatus, Faculty


def setup():
    User = get_user_model()
    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser("admin", "admin@example.com", "password123")
    else:
        pass

    # Create dummy faculty
    faculty, _ = Faculty.objects.get_or_create(
        abbreviation="TEST",
        defaults={
            "name": "Test Faculty",
            "hierarchy_level": 1,
            "full_abbreviation": "TEST",
        },
    )

    # Create a pending item
    item, created = CopyrightItem.objects.get_or_create(
        material_id=88888,
        defaults={
            "filename": "browser_test.pdf",
            "faculty": faculty,
            "enrichment_status": EnrichmentStatus.PENDING,
            "title": "Browser Test Item",
        },
    )
    if created:
        pass
    else:
        # Reset if exists
        item.enrichment_status = EnrichmentStatus.PENDING
        item.save()


if __name__ == "__main__":
    setup()
