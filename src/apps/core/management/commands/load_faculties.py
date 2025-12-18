"""
Management command to populate Faculty records from university configuration.
"""

from django.core.management.base import BaseCommand
from loguru import logger

from apps.core.models import Faculty
from config.university import FACULTIES


class Command(BaseCommand):
    help = "Populate Faculty records from university configuration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing faculties before loading",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            count = Faculty.objects.count()
            Faculty.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"Cleared {count} existing faculties")
            )

        created_count = 0
        updated_count = 0

        for faculty_data in FACULTIES:
            abbreviation = faculty_data["abbreviation"]
            name = faculty_data["name"]

            # Create or update faculty
            faculty, created = Faculty.objects.update_or_create(
                abbreviation=abbreviation,
                defaults={
                    "hierarchy_level": 1,  # Faculties are level 1
                    "name": name,
                    "full_abbreviation": abbreviation,
                },
            )

            if created:
                created_count += 1
                logger.info(f"Created faculty: {abbreviation} - {name}")
            else:
                updated_count += 1
                logger.info(f"Updated faculty: {abbreviation} - {name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully loaded {len(FACULTIES)} faculties:"
            )
        )
        self.stdout.write(f"  - Created: {created_count}")
        self.stdout.write(f"  - Updated: {updated_count}")

        # Display loaded faculties
        self.stdout.write("\nLoaded faculties:")
        for faculty in Faculty.objects.all().order_by("abbreviation"):
            self.stdout.write(f"  • {faculty.abbreviation}: {faculty.name}")
