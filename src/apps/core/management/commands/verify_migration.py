"""
Management command to verify the legacy data migration.

Checks:
- Count of organizations, courses, persons, and relationships
- Data quality issues (missing required fields, broken relationships)
- Edge cases (orphaned records, duplicates)
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from apps.core.models import Course, CourseEmployee, Faculty, Organization, Person, CopyrightItem
from apps.ingest.models import ChangeLog


class Command(BaseCommand):
    help = "Verify the legacy data migration and report any issues"

    def add_arguments(self, parser):
        parser.add_argument(
            "--detailed",
            action="store_true",
            help="Show detailed information about issues",
        )

    def handle(self, *args, **options):
        detailed = options["detailed"]

        self.stdout.write(
            self.style.SUCCESS("\n=== Migration Verification Report ===\n")
        )

        # 1. Basic counts
        self._check_counts()

        # 2. Data quality checks
        self._check_data_quality(detailed)

        # 3. Relationship integrity
        self._check_relationships(detailed)

        # 4. Faculty distribution
        self._check_faculty_distribution()

        self.stdout.write(self.style.SUCCESS("\n=== Verification Complete ===\n"))

    def _check_counts(self):
        """Check basic record counts."""
        self.stdout.write("\n--- Record Counts ---")

        faculties = Faculty.objects.count()
        organizations = Organization.objects.exclude(hierarchy_level=1).count()
        courses = Course.objects.count()
        persons = Person.objects.count()
        relationships = CourseEmployee.objects.count()

        total_items = CopyrightItem.objects.count()
        migrated_logs = ChangeLog.objects.filter(
            change_source=ChangeLog.ChangeSource.MIGRATION
        ).count()

        self.stdout.write(f"  Faculties: {faculties}")
        self.stdout.write(f"  Organizations (non-faculty): {organizations}")
        self.stdout.write(f"  Courses: {courses}")
        self.stdout.write(f"  Persons: {persons}")
        self.stdout.write(f"  Course-Person relationships: {relationships}")
        self.stdout.write(f"  Copyright Items: {total_items}")
        self.stdout.write(f"  MIGRATION changelogs: {migrated_logs}")

        if total_items != migrated_logs:
            self.stdout.write(
                self.style.WARNING(
                    f"  ⚠ Mismatch: {total_items - migrated_logs} items without MIGRATION changelog"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("  ✓ All items accounted for by migration logs")
            )

        # Warnings
        if courses == 0:
            self.stdout.write(
                self.style.WARNING("  ⚠ No courses found - migration may not have run")
            )
        if persons == 0:
            self.stdout.write(
                self.style.WARNING("  ⚠ No persons found - migration may not have run")
            )

    def _check_data_quality(self, detailed):
        """Check for data quality issues."""
        self.stdout.write("\n--- Data Quality Checks ---")

        # Courses without names
        courses_no_name = Course.objects.filter(
            Q(name__isnull=True) | Q(name="")
        ).count()
        if courses_no_name > 0:
            self.stdout.write(
                self.style.WARNING(f"  ⚠ {courses_no_name} courses without names")
            )
            if detailed:
                for course in Course.objects.filter(Q(name__isnull=True) | Q(name=""))[
                    :5
                ]:
                    self.stdout.write(f"    - {course.cursuscode}")

        # Courses without cursuscode
        courses_no_code = Course.objects.filter(Q(cursuscode__isnull=True)).count()
        if courses_no_code > 0:
            self.stdout.write(
                self.style.ERROR(
                    f"  ✗ {courses_no_code} courses without cursuscode (required field)"
                )
            )

        # Persons without names
        persons_no_name = Person.objects.filter(
            Q(main_name__isnull=True) | Q(main_name="")
        ).count()
        if persons_no_name > 0:
            self.stdout.write(
                self.style.WARNING(f"  ⚠ {persons_no_name} persons without main_name")
            )
            if detailed:
                for person in Person.objects.filter(
                    Q(main_name__isnull=True) | Q(main_name="")
                )[:5]:
                    self.stdout.write(f"    - {person.input_name}")

        # Persons without input_name (required)
        persons_no_input = Person.objects.filter(
            Q(input_name__isnull=True) | Q(input_name="")
        ).count()
        if persons_no_input > 0:
            self.stdout.write(
                self.style.ERROR(
                    f"  ✗ {persons_no_input} persons without input_name (required field)"
                )
            )

        # Check for low match confidence
        low_confidence = Person.objects.filter(match_confidence__lt=0.5).count()
        if low_confidence > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"  ⚠ {low_confidence} persons with match confidence < 0.5"
                )
            )

        if (
            courses_no_name == 0
            and courses_no_code == 0
            and persons_no_name == 0
            and persons_no_input == 0
        ):
            self.stdout.write(
                self.style.SUCCESS("  ✓ All basic data quality checks passed")
            )

    def _check_relationships(self, detailed):
        """Check relationship integrity."""
        self.stdout.write("\n--- Relationship Integrity ---")

        # Orphaned course-person relationships
        invalid_relationships = CourseEmployee.objects.filter(
            Q(course__isnull=True) | Q(person__isnull=True)
        ).count()
        if invalid_relationships > 0:
            self.stdout.write(
                self.style.ERROR(
                    f"  ✗ {invalid_relationships} CourseEmployee records with null course or person"
                )
            )

        # Courses without any employees
        courses_no_employees = (
            Course.objects.annotate(employee_count=Count("courseemployee"))
            .filter(employee_count=0)
            .count()
        )
        if courses_no_employees > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"  ⚠ {courses_no_employees} courses without any associated employees"
                )
            )

        # Persons not linked to any courses
        persons_no_courses = (
            Person.objects.annotate(course_count=Count("courseemployee"))
            .filter(course_count=0)
            .count()
        )
        if persons_no_courses > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"  ⚠ {persons_no_courses} persons not linked to any courses"
                )
            )

        # Duplicate course-person relationships
        duplicates = (
            CourseEmployee.objects.values("course", "person")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )
        if duplicates.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"  ⚠ {duplicates.count()} duplicate course-person relationships"
                )
            )
            if detailed:
                for dup in duplicates[:5]:
                    self.stdout.write(
                        f"    - Course {dup['course']} + Person {dup['person']}: {dup['count']} times"
                    )

        if (
            invalid_relationships == 0
            and courses_no_employees < Course.objects.count() * 0.5
        ):
            self.stdout.write(
                self.style.SUCCESS("  ✓ Relationship integrity looks good")
            )

    def _check_faculty_distribution(self):
        """Check faculty distribution."""
        self.stdout.write("\n--- Faculty Distribution ---")

        # Courses per faculty
        course_dist = (
            Course.objects.values("faculty__abbreviation")
            .annotate(count=Count("cursuscode"))
            .order_by("-count")
        )

        if course_dist.exists():
            self.stdout.write("  Courses per faculty:")
            for item in course_dist:
                faculty = item["faculty__abbreviation"] or "None"
                self.stdout.write(f"    {faculty}: {item['count']}")
        else:
            self.stdout.write(self.style.WARNING("  ⚠ No faculty distribution data"))

        # Persons per faculty
        person_dist = (
            Person.objects.values("faculty__abbreviation")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        if person_dist.exists():
            self.stdout.write("\n  Persons per faculty:")
            for item in person_dist:
                faculty = item["faculty__abbreviation"] or "None"
                self.stdout.write(f"    {faculty}: {item['count']}")

        # Check for unmapped items
        courses_no_faculty = Course.objects.filter(faculty__isnull=True).count()
        persons_no_faculty = Person.objects.filter(faculty__isnull=True).count()

        if courses_no_faculty > 0 or persons_no_faculty > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"\n  ⚠ {courses_no_faculty} courses and {persons_no_faculty} persons without faculty mapping"
                )
            )
