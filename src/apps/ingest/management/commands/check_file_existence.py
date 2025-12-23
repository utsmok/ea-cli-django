"""
Management command to check file existence on Canvas LMS.
"""

import traceback

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand

from apps.core.services.canvas import refresh_file_existence_async


class Command(BaseCommand):
    help = "Check file existence for copyright items on Canvas LMS"

    def add_arguments(self, parser):
        parser.add_argument(
            "--ttl-days",
            type=int,
            default=7,
            help="TTL in days for file existence checks (default: 7)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Maximum items to process per batch (default: 1000)",
        )
        parser.add_argument(
            "--max-concurrent",
            type=int,
            default=50,
            help="Maximum concurrent API requests (default: 50)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-check all items regardless of TTL",
        )
        parser.add_argument(
            "--rate-limit-delay",
            type=float,
            default=0.05,
            help="Delay between requests in seconds (default: 0.05)",
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting file existence check...")

        try:
            result = async_to_sync(refresh_file_existence_async)(
                ttl_days=options["ttl_days"],
                batch_size=options["batch_size"],
                max_concurrent=options["max_concurrent"],
                force=options["force"],
                rate_limit_delay=options["rate_limit_delay"],
            )

            if result is None:
                self.stderr.write(self.style.ERROR("Error: No result returned"))
                return

            if "error" in result:
                self.stderr.write(self.style.ERROR(f"Error: {result['error']}"))
                return

            self.stdout.write(
                self.style.SUCCESS(
                    f"File existence check complete:\n"
                    f"  Checked: {result.get('checked', 0)}\n"
                    f"  Exists: {result.get('exists', 0)}\n"
                    f"  Not Found: {result.get('not_exists', 0)}\n"
                    f"  Duration: {result.get('duration_seconds', 0)}s"
                )
            )

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
            traceback.print_exc()
