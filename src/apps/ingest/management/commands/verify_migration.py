"""Verify legacy migration results (Phase A Step 10)."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.core.models import ChangeLog, CopyrightItem


class Command(BaseCommand):
    help = "Verify legacy data migration (counts, basic coverage)."

    def handle(self, *args, **options):
        total_items = CopyrightItem.objects.count()
        migrated_logs = ChangeLog.objects.filter(
            change_source=ChangeLog.ChangeSource.MIGRATION
        ).count()

        items_with_faculty = CopyrightItem.objects.exclude(faculty=None).count()
        items_with_nondefault_classification = CopyrightItem.objects.exclude(
            v2_manual_classification="Onbekend"
        ).count()

        self.stdout.write("Migration verification:")
        self.stdout.write(f"  Total items: {total_items}")
        self.stdout.write(f"  MIGRATION changelogs: {migrated_logs}")
        self.stdout.write(f"  Items with faculty: {items_with_faculty}")
        self.stdout.write(
            f"  Items with v2_manual_classification != 'Onbekend': {items_with_nondefault_classification}"
        )

        if total_items == migrated_logs:
            self.stdout.write(
                self.style.SUCCESS("✓ All items accounted for by migration logs")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ Mismatch: {total_items - migrated_logs} items without MIGRATION changelog"
                )
            )
