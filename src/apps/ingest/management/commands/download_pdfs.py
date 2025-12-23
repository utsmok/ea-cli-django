"""
Management command to download PDFs from Canvas LMS.
"""

import traceback

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand

from apps.documents.services.download import download_undownloaded_pdfs


class Command(BaseCommand):
    help = "Download PDFs from Canvas LMS for items with file_exists=True"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum number of PDFs to download (default: 0 = no limit)",
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting PDF download...")

        try:
            result = async_to_sync(download_undownloaded_pdfs)(
                limit=options["limit"],
            )

            if result is None:
                self.stderr.write(self.style.ERROR("Error: No result returned"))
                return

            if "error" in result:
                self.stderr.write(self.style.ERROR(f"Error: {result['error']}"))
                return

            self.stdout.write(
                self.style.SUCCESS(
                    f"PDF download complete:\n"
                    f"  Downloaded: {result.get('downloaded', 0)}\n"
                    f"  Failed: {result.get('failed', 0)}"
                )
            )

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
            traceback.print_exc()
