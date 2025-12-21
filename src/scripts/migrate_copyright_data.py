import os
import sqlite3
from pathlib import Path

import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.core.models import CopyrightItem, Faculty


def migrate():
    db_path = Path("ea-cli/db.sqlite3")
    if not db_path.exists():
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM copyright_data")
    rows = cursor.fetchall()

    count = 0
    for row in rows:
        row = dict(row)
        try:
            # Resolve faculty
            faculty_abbr = None
            dept = row.get("department")
            if dept:
                # Use mapping as in legacy
                from config.university import DEPARTMENT_MAPPING

                faculty_abbr = DEPARTMENT_MAPPING.get(dept)

            # Fallback to legacy faculty_id column if mapping failed but abbreviation exists
            if not faculty_abbr:
                faculty_abbr = row.get("faculty_id")
                # Handle EWI -> EEMCS mapping specifically if it appears
                if faculty_abbr == "EWI":
                    faculty_abbr = "EEMCS"

            faculty = None
            if faculty_abbr:
                faculty = Faculty.objects.filter(abbreviation=faculty_abbr).first()

            item, created = CopyrightItem.objects.update_or_create(
                material_id=row["material_id"],
                defaults={
                    "period": row.get("period", ""),
                    "department": row.get("department", ""),
                    "course_code": row.get("course_code", ""),
                    "course_name": row.get("course_name", ""),
                    "url": row.get("url"),
                    "filename": row.get("filename"),
                    "title": row.get("title"),
                    "owner": row.get("owner"),
                    "filetype": row.get("filetype", "unknown"),
                    "classification": row.get("classification", "lange overname"),
                    "ml_classification": row.get("ml_prediction"),
                    "manual_classification": row.get("manual_classification")
                    or "onbekend",
                    "manual_identifier": row.get("manual_identifier"),
                    "v2_manual_classification": row.get("v2_manual_classification")
                    or "Onbekend",
                    "v2_overnamestatus": row.get("v2_overnamestatus") or "Onbekend",
                    "v2_lengte": row.get("v2_lengte") or "Onbekend",
                    "scope": row.get("scope"),
                    "remarks": row.get("remarks"),
                    "auditor": row.get("auditor"),
                    "last_change": row.get("last_change"),
                    "status": row.get("status", "Published"),
                    "isbn": row.get("isbn"),
                    "doi": row.get("doi"),
                    "in_collection": bool(row.get("in_collection")),
                    "pagecount": row.get("pagecount") or 0,
                    "wordcount": row.get("wordcount") or 0,
                    "picturecount": row.get("picturecount") or 0,
                    "author": row.get("author"),
                    "publisher": row.get("publisher"),
                    "reliability": row.get("reliability") or 0,
                    "pages_x_students": row.get("pages_x_students") or 0,
                    "count_students_registered": row.get("count_students_registered")
                    or 0,
                    "filehash": row.get("filehash"),
                    "last_scan_date_university": row.get("last_scan_date_university"),
                    "last_scan_date_course": row.get("last_scan_date_course"),
                    "retrieved_from_copyright_on": row.get(
                        "retrieved_from_copyright_on"
                    ),
                    "workflow_status": row.get("workflow_status", "ToDo"),
                    "file_exists": bool(row.get("file_exists")),
                    "last_canvas_check": row.get("last_canvas_check"),
                    "canvas_course_id": row.get("canvas_course_id"),
                    "faculty": faculty,
                },
            )
            count += 1
            if count % 100 == 0:
                pass
        except Exception:
            pass

    conn.close()


if __name__ == "__main__":
    migrate()
