from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from apps.ingest.services.export import ExportService


class Command(BaseCommand):
    help = (
        "Export workflow faculty sheets to disk (legacy-compatible folder structure). "
        "Creates one folder per faculty with inbox/in_progress/done/overview workbooks."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            type=str,
            default=None,
            help="Root directory to write faculty sheets to (default: exports/faculty_sheets)",
        )
        parser.add_argument(
            "--faculty",
            type=str,
            default=None,
            help="Optional faculty abbreviation to export (e.g. BMS)",
        )

    def handle(self, *args, **options):
        output_dir = options.get("output_dir")
        faculty = options.get("faculty")

        service = ExportService(faculty_abbr=faculty)
        result = service.export_workflow_tree(
            output_dir=Path(output_dir) if output_dir else None
        )

        self.stdout.write(self.style.SUCCESS(f"Exported to: {result['output_dir']}"))
        for p in result["files"]:
            self.stdout.write(f"- {p}")
