"""
Management command to parse PDFs and extract text.
"""

import traceback

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand

from apps.documents.services.parse import parse_pdfs


class Command(BaseCommand):
    help = "Parse PDFs and extract text using Kreuzberg"

    def add_arguments(self, parser):
        parser.add_argument(
            "--filter-ids",
            type=str,
            default="",
            help="Comma-separated list of copyright_item IDs to filter",
        )
        parser.add_argument(
            "--skip-text",
            action="store_true",
            help="Skip text extraction, only calculate file hashes",
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting PDF parsing...")

        # Parse filter IDs
        filter_ids = None
        if options["filter_ids"]:
            try:
                filter_ids = [int(x.strip()) for x in options["filter_ids"].split(",")]
            except ValueError:
                self.stderr.write(self.style.ERROR("Invalid filter-ids format"))
                return

        try:
            result = async_to_sync(parse_pdfs)(
                filter_ids=filter_ids,
                skip_text=options["skip_text"],
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"PDF parsing complete:\n"
                    f"  Processed: {result.get('processed', 0)}\n"
                    f"  Successful: {result.get('successful', 0)}\n"
                    f"  Failed: {result.get('failed', 0)}"
                )
            )

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
            traceback.print_exc()
