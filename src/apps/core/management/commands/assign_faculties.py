"""
Management command to assign faculties to existing CopyrightItems.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from loguru import logger

from apps.core.models import CopyrightItem, Faculty
from config.university import DEPARTMENT_MAPPING_LOWER


class Command(BaseCommand):
    help = "Assign faculties to CopyrightItems based on department mapping"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Reassign all items, even if they already have a faculty",
        )

    def handle(self, *args, **options):
        if options["all"]:
            items = CopyrightItem.objects.all()
            self.stdout.write("Reassigning ALL items...")
        else:
            items = CopyrightItem.objects.filter(faculty__isnull=True)
            self.stdout.write("Assigning faculties to items without faculty...")

        updated = 0
        unmapped = 0
        errors = 0

        with transaction.atomic():
            for item in items:
                try:
                    dept = (item.department or "").strip().lower()
                    if not dept:
                        abbr = "UNM"
                    else:
                        abbr = DEPARTMENT_MAPPING_LOWER.get(dept)
                        if abbr is None:
                            if item.department:
                                abbr = DEPARTMENT_MAPPING_LOWER.get(
                                    item.department.strip()
                                )
                            if abbr is None:
                                logger.debug(f"Unmapped department: {item.department}")
                                abbr = "UNM"
                                unmapped += 1

                    faculty = Faculty.objects.get(abbreviation=abbr)
                    item.faculty = faculty
                    item.save(update_fields=["faculty"])
                    updated += 1

                except Faculty.DoesNotExist:
                    logger.error(f"Faculty {abbr} not found!")
                    errors += 1
                except Exception as e:
                    logger.error(f"Error assigning faculty to item {item.pk}: {e}")
                    errors += 1

        self.stdout.write(self.style.SUCCESS("\nSuccessfully assigned faculties:"))
        self.stdout.write(f"  - Updated: {updated}")
        self.stdout.write(f"  - Unmapped departments: {unmapped}")
        if errors:
            self.stdout.write(self.style.WARNING(f"  - Errors: {errors}"))

        # Show distribution
        self.stdout.write("\nFaculty distribution:")
        for faculty in Faculty.objects.all().order_by("abbreviation"):
            count = CopyrightItem.objects.filter(faculty=faculty).count()
            self.stdout.write(f"  - {faculty.abbreviation}: {count} items")
