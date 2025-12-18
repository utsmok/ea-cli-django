"""
Management command to load enrichment data from legacy ea-cli SQLite database.

Loads:
- Organizations (Faculties and Departments)
- Courses
- Persons
- Course-Person relationships
"""

import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from loguru import logger

from apps.core.models import Course, CourseEmployee, Faculty, Organization, Person


class Command(BaseCommand):
    help = "Load enrichment data from legacy ea-cli SQLite database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--db-path",
            type=str,
            default="ea-cli/db.sqlite3",
            help="Path to legacy SQLite database (default: ea-cli/db.sqlite3)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before loading",
        )
        parser.add_argument(
            "--skip-faculties",
            action="store_true",
            help="Skip faculty loading (use if already loaded via load_faculties)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be loaded without actually loading it",
        )

    def handle(self, *args, **options):
        db_path = Path(options["db_path"])
        dry_run = options["dry_run"]

        if not db_path.exists():
            self.stdout.write(self.style.ERROR(f"Database not found: {db_path}"))
            self.stdout.write(
                "Please provide the path to the legacy SQLite database using --db-path"
            )
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("\n=== DRY RUN MODE ==="))
            self.stdout.write("No data will be loaded. Inspecting legacy database...\n")

        self.stdout.write(f"Loading data from: {db_path}")

        # Connect to legacy database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get counts from legacy database
        cursor.execute("SELECT COUNT(*) FROM organization_data")
        org_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM course_data")
        course_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM person_data")
        person_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM course_employee")
        rel_count = cursor.fetchone()[0]

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\n=== Legacy Database Contents ==="))
            self.stdout.write(f"  Organizations: {org_count}")
            self.stdout.write(f"  Courses: {course_count}")
            self.stdout.write(f"  Persons: {person_count}")
            self.stdout.write(f"  Course-Person links: {rel_count}")

            self.stdout.write(self.style.SUCCESS("\n=== Current Django Database ==="))
            self.stdout.write(
                f"  Organizations (non-faculty): {Organization.objects.exclude(hierarchy_level=1).count()}"
            )
            self.stdout.write(f"  Courses: {Course.objects.count()}")
            self.stdout.write(f"  Persons: {Person.objects.count()}")
            self.stdout.write(
                f"  Course-Person links: {CourseEmployee.objects.count()}"
            )

            # Sample data
            self.stdout.write(self.style.SUCCESS("\n=== Sample Courses (first 5) ==="))
            cursor.execute("SELECT cursuscode, name, year FROM course_data LIMIT 5")
            for row in cursor.fetchall():
                self.stdout.write(
                    f"  {row['cursuscode']} - {row['name']} ({row['year']})"
                )

            self.stdout.write(self.style.SUCCESS("\n=== Sample Persons (first 5) ==="))
            cursor.execute(
                "SELECT input_name, main_name, match_confidence FROM person_data LIMIT 5"
            )
            for row in cursor.fetchall():
                conf = row["match_confidence"] if row["match_confidence"] else 0
                self.stdout.write(
                    f"  {row['input_name']} -> {row['main_name']} (confidence: {conf:.2f})"
                )

            conn.close()
            self.stdout.write(
                self.style.WARNING(
                    "\nDry run complete. Use without --dry-run to load data.\n"
                )
            )
            return

        if options["clear"]:
            self.clear_existing_data()

        stats = {
            "organizations": 0,
            "courses": 0,
            "persons": 0,
            "course_employees": 0,
        }

        with transaction.atomic():
            # Load organizations (departments)
            if not options["skip_faculties"]:
                stats["organizations"] = self.load_organizations(cursor)

            # Load courses
            stats["courses"] = self.load_courses(cursor)

            # Load persons
            stats["persons"] = self.load_persons(cursor)

            # Load course-person relationships
            stats["course_employees"] = self.load_course_employees(cursor)

        conn.close()

        self.stdout.write(self.style.SUCCESS("\nSuccessfully loaded legacy data:"))
        self.stdout.write(f"  - Organizations: {stats['organizations']}")
        self.stdout.write(f"  - Courses: {stats['courses']}")
        self.stdout.write(f"  - Persons: {stats['persons']}")
        self.stdout.write(f"  - Course-Person links: {stats['course_employees']}")

    def clear_existing_data(self):
        """Clear existing enrichment data."""
        counts = {
            "CourseEmployee": CourseEmployee.objects.count(),
            "Course": Course.objects.count(),
            "Person": Person.objects.count(),
            "Organization": Organization.objects.exclude(
                hierarchy_level=1
            ).count(),  # Don't delete faculties
        }

        CourseEmployee.objects.all().delete()
        Course.objects.all().delete()
        Person.objects.all().delete()
        Organization.objects.exclude(hierarchy_level=1).delete()

        self.stdout.write(
            self.style.WARNING(f"Cleared existing data: {sum(counts.values())} records")
        )

    def load_organizations(self, cursor):
        """Load organization hierarchy (faculties and departments)."""
        cursor.execute("SELECT * FROM organization_data")
        rows = cursor.fetchall()

        created = 0
        for row in rows:
            row = dict(row)  # Convert sqlite3.Row to dict
            try:
                # Get or create parent organization
                parent = None
                if row.get("parent_organization_id"):
                    try:
                        parent = Organization.objects.get(
                            pk=row["parent_organization_id"]
                        )
                    except Organization.DoesNotExist:
                        logger.warning(
                            f"Parent organization {row['parent_organization_id']} not found for {row['name']}"
                        )

                # Create organization
                org, was_created = Organization.objects.update_or_create(
                    id=row["id"],
                    defaults={
                        "hierarchy_level": row["hierarchy_level"],
                        "name": row["name"],
                        "abbreviation": row["abbreviation"],
                        "full_abbreviation": row["full_abbreviation"],
                        "parent": parent,
                    },
                )

                if was_created:
                    created += 1
                    logger.debug(f"Created organization: {org.name}")

            except Exception as e:
                logger.error(f"Error loading organization {row['name']}: {e}")

        return created

    def load_courses(self, cursor):
        """Load courses from legacy database."""
        cursor.execute("SELECT * FROM course_data")
        rows = cursor.fetchall()

        created = 0
        for row in rows:
            row = dict(row)  # Convert sqlite3.Row to dict
            try:
                # Map faculty if exists
                faculty = None
                if row.get("faculty_id"):
                    try:
                        # faculty_id is an abbreviation string
                        faculty = Faculty.objects.get(abbreviation=row["faculty_id"])
                    except Faculty.DoesNotExist:
                        logger.warning(
                            f"Faculty {row['faculty_id']} not found for course {row['name']}"
                        )

                course, was_created = Course.objects.update_or_create(
                    cursuscode=row["cursuscode"],
                    defaults={
                        "internal_id": row["internal_id"],
                        "year": row["year"],
                        "name": row["name"],
                        "short_name": row["short_name"],
                        "faculty": faculty,
                        "programme_text": row["programme"],
                    },
                )

                if was_created:
                    created += 1

            except Exception as e:
                try:
                    logger.error(f"Error loading course {row['name']}: {e}")
                except:
                    logger.error(f"Error loading course: {e}")

        return created

    def load_persons(self, cursor):
        """Load persons from legacy database."""
        cursor.execute("SELECT * FROM person_data")
        rows = cursor.fetchall()

        created = 0
        for row in rows:
            row = dict(row)  # Convert sqlite3.Row to dict
            try:
                # Map faculty if exists
                faculty = None
                if row.get("faculty_id"):
                    try:
                        faculty = Faculty.objects.get(abbreviation=row["faculty_id"])
                    except Faculty.DoesNotExist:
                        pass

                person, was_created = Person.objects.update_or_create(
                    id=row["id"],
                    defaults={
                        "input_name": row["input_name"],
                        "main_name": row["main_name"],
                        "match_confidence": row["match_confidence"],
                        "email": row["email"],
                        "people_page_url": row["people_page_url"],
                        "faculty": faculty,
                    },
                )

                if was_created:
                    created += 1

            except Exception as e:
                try:
                    logger.error(f"Error loading person {row['input_name']}: {e}")
                except:
                    logger.error(f"Error loading person: {e}")

        return created

    def load_course_employees(self, cursor):
        """Load course-person relationships."""
        cursor.execute("SELECT * FROM course_employee")
        rows = cursor.fetchall()

        created = 0
        for row in rows:
            row = dict(row)  # Convert sqlite3.Row to dict
            try:
                course = Course.objects.get(cursuscode=row["course_id"])
                person = Person.objects.get(pk=row["person_id"])

                _, was_created = CourseEmployee.objects.get_or_create(
                    course=course,
                    person=person,
                    role=row["role"],
                )

                if was_created:
                    created += 1

            except Course.DoesNotExist:
                logger.warning(f"Course {row['course_id']} not found")
            except Person.DoesNotExist:
                logger.warning(f"Person {row['person_id']} not found")
            except Exception as e:
                logger.error(f"Error loading course employee: {e}")

        return created
