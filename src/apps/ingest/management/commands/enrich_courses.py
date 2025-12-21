import traceback

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand

from apps.core.services.osiris import enrich_async
from apps.core.services.relations import link_courses


class Command(BaseCommand):
    help = "Enrich database with course data from OSIRIS"

    def handle(self, *args, **options):
        self.stdout.write("Starting course enrichment...")
        try:
            # 1. Fetch OSIRIS data
            async_to_sync(enrich_async)()

            # 2. Link Courses to CopyrightItems
            # (This is sync in relations.py)
            link_courses()

            self.stdout.write(self.style.SUCCESS("Enrichment complete."))
        except Exception:
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            raise
