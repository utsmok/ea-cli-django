"""Load legacy data from a CSV export.

This is the Phase A Step 10 migration helper.

Usage:
    uv run python src/manage.py load_legacy path/to/migration_export.csv --dry-run
    uv run python src/manage.py load_legacy path/to/migration_export.csv

The importer is idempotent: existing material_id rows are skipped.
"""

from __future__ import annotations

import csv
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import ChangeLog, CopyrightItem, Faculty

User = get_user_model()


def _safe_int(value, default=None):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_str(value):
    if value is None:
        return None
    s = str(value).strip()
    return s if s != "" else None


class Command(BaseCommand):
    help = "Import legacy CopyrightItems from a CSV export (ea-cli Step 10)."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file", type=str, help="Path to legacy migration_export.csv"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview without writing to the database",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_file"])
        dry_run = bool(options["dry_run"])

        if not csv_path.exists():
            self.stdout.write(self.style.ERROR(f"File not found: {csv_path}"))
            return

        migration_user, _ = User.objects.get_or_create(username="system_migration")
        if not migration_user.has_usable_password():
            migration_user.set_unusable_password()
            migration_user.save(update_fields=["password"])

        faculty_map = {
            f.abbreviation: f for f in Faculty.objects.all() if f.abbreviation
        }

        to_create: list[CopyrightItem] = []

        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                material_id = _safe_int(row.get("material_id"), default=None)
                if material_id is None:
                    continue

                if CopyrightItem.objects.filter(material_id=material_id).exists():
                    continue

                faculty_code = _safe_str(row.get("faculty"))
                faculty = faculty_map.get(faculty_code) if faculty_code else None

                item = CopyrightItem(
                    material_id=material_id,
                    title=_safe_str(row.get("title")),
                    author=_safe_str(row.get("author")),
                    publisher=_safe_str(row.get("publisher")),
                    filename=_safe_str(row.get("filename")),
                    url=_safe_str(row.get("url")),
                    filehash=_safe_str(row.get("filehash")),
                    filetype=_safe_str(row.get("filetype"))
                    or CopyrightItem._meta.get_field("filetype").default,
                    status=_safe_str(row.get("status"))
                    or CopyrightItem._meta.get_field("status").default,
                    workflow_status=_safe_str(row.get("workflow_status"))
                    or CopyrightItem._meta.get_field("workflow_status").default,
                    department=_safe_str(row.get("department")),
                    period=_safe_str(row.get("period")),
                    course_code=_safe_str(row.get("course_code")),
                    course_name=_safe_str(row.get("course_name")),
                    canvas_course_id=_safe_int(
                        row.get("canvas_course_id"), default=None
                    ),
                    classification=_safe_str(row.get("classification"))
                    or CopyrightItem._meta.get_field("classification").default,
                    manual_classification=_safe_str(row.get("manual_classification")),
                    manual_identifier=_safe_str(row.get("manual_identifier")),
                    scope=_safe_str(row.get("scope")),
                    remarks=_safe_str(row.get("remarks")),
                    v2_manual_classification=_safe_str(
                        row.get("v2_manual_classification")
                    )
                    or CopyrightItem._meta.get_field(
                        "v2_manual_classification"
                    ).default,
                    v2_lengte=_safe_str(row.get("v2_lengte"))
                    or CopyrightItem._meta.get_field("v2_lengte").default,
                    v2_overnamestatus=_safe_str(row.get("v2_overnamestatus"))
                    or CopyrightItem._meta.get_field("v2_overnamestatus").default,
                    count_students_registered=_safe_int(
                        row.get("count_students_registered"), default=0
                    ),
                    pages_x_students=_safe_int(row.get("pages_x_students"), default=0),
                    pagecount=_safe_int(row.get("pagecount"), default=0),
                    wordcount=_safe_int(row.get("wordcount"), default=0),
                    picturecount=_safe_int(row.get("picturecount"), default=0),
                    reliability=_safe_int(row.get("reliability"), default=0),
                    infringement=_safe_str(row.get("infringement"))
                    or CopyrightItem._meta.get_field("infringement").default,
                    possible_fine=row.get("possible_fine") or None,
                    isbn=_safe_str(row.get("isbn")),
                    doi=_safe_str(row.get("doi")),
                    owner=_safe_str(row.get("owner")),
                    in_collection=(
                        str(row.get("in_collection")).lower() in {"true", "1", "yes"}
                        if row.get("in_collection") is not None
                        else None
                    ),
                    file_exists=(
                        str(row.get("file_exists")).lower() in {"true", "1", "yes"}
                        if row.get("file_exists") is not None
                        else None
                    ),
                    faculty=faculty,
                )
                to_create.append(item)

        self.stdout.write(f"Prepared {len(to_create)} items for import.")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: no data written."))
            return

        if not to_create:
            self.stdout.write("Nothing to import.")
            return

        with transaction.atomic():
            created = CopyrightItem.objects.bulk_create(to_create, batch_size=1000)

            logs = [
                ChangeLog(
                    item=item,
                    changes={
                        "migration": {"old": None, "new": "Imported from legacy ea-cli"}
                    },
                    changed_by=migration_user,
                    change_source=ChangeLog.ChangeSource.MIGRATION,
                    batch=None,
                )
                for item in created
            ]
            ChangeLog.objects.bulk_create(logs, batch_size=1000)

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(created)} items and logged {len(logs)} ChangeLogs."
            )
        )
