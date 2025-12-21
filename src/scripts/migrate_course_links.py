import os
import sqlite3
from pathlib import Path

import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.core.models import CopyrightItem, Course


def migrate_links():
    legacy_db = Path("ea-cli/db.sqlite3")
    if not legacy_db.exists():
        return

    conn = sqlite3.connect(legacy_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM copyright_data_course_data")
    rows = cursor.fetchall()

    # Optional: clear existing links if we want a fresh start
    # CopyrightItem.courses.through.objects.all().delete()

    count = 0
    missing_items = 0
    missing_courses = 0

    for row in rows:
        mat_id = row["copyright_data_id"]
        course_id = row["course_id"]

        try:
            item = CopyrightItem.objects.get(material_id=mat_id)
            course = Course.objects.get(cursuscode=course_id)
            item.courses.add(course)
            count += 1
            if count % 500 == 0:
                pass
        except CopyrightItem.DoesNotExist:
            missing_items += 1
        except Course.DoesNotExist:
            missing_courses += 1

    conn.close()


if __name__ == "__main__":
    migrate_links()
