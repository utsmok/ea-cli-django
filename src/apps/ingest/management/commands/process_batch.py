"""
Management command to manually trigger batch processing.

Usage:
    python manage.py process_batch <batch_id>
    python manage.py process_batch <batch_id> --stage-only
    python manage.py process_batch <batch_id> --process-only
"""

from django.core.management.base import BaseCommand, CommandError

from apps.ingest.models import IngestionBatch
from apps.ingest.tasks import process_batch, stage_batch


class Command(BaseCommand):
    help = "Process an ingestion batch (staging + processing)"

    def add_arguments(self, parser):
        parser.add_argument(
            "batch_id", type=int, help="ID of the IngestionBatch to process"
        )
        parser.add_argument(
            "--stage-only",
            action="store_true",
            help="Only run staging phase (don't process)",
        )
        parser.add_argument(
            "--process-only",
            action="store_true",
            help="Only run processing phase (skip staging)",
        )

    def handle(self, *args, **options):
        batch_id = options["batch_id"]
        stage_only = options["stage_only"]
        process_only = options["process_only"]

        # Validate batch exists
        try:
            batch = IngestionBatch.objects.get(id=batch_id)
        except IngestionBatch.DoesNotExist:
            raise CommandError(f"IngestionBatch with ID {batch_id} does not exist")

        self.stdout.write(
            self.style.SUCCESS(
                f"Processing batch {batch_id} ({batch.get_source_type_display()})"
            )
        )

        # Run staging
        if not process_only:
            self.stdout.write("Running staging phase...")
            try:
                result = stage_batch(batch_id)
                if result["success"]:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Staging complete: {result['rows_staged']} rows staged"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"✗ Staging failed: {result.get('errors', 'Unknown error')}"
                        )
                    )
                    return
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Staging failed: {e}"))
                raise

        if stage_only:
            self.stdout.write("Stopping after staging (--stage-only flag set)")
            return

        # Run processing
        self.stdout.write("Running processing phase...")
        try:
            result = process_batch(batch_id)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Processing complete:\n"
                    f"  - Created: {result['created']}\n"
                    f"  - Updated: {result['updated']}\n"
                    f"  - Skipped: {result['skipped']}\n"
                    f"  - Failed: {result['failed']}"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Processing failed: {e}"))
            raise

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Batch {batch_id} complete! Check admin for details."
            )
        )
