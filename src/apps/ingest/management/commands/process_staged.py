from django.core.management.base import BaseCommand

from apps.ingest.models import IngestionBatch
from apps.ingest.tasks import process_batch


class Command(BaseCommand):
    help = "Process staged ingestion batches into CopyrightItems (Phase A pipeline)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Max number of batches to process in this run.",
        )
        parser.add_argument(
            "--batch-id",
            type=int,
            default=None,
            help="Optional batch id to process. If omitted, processes all STAGED batches.",
        )

    def handle(self, *args, **options):
        limit = options["batch_size"]
        batch_id = options.get("batch_id")

        if batch_id:
            result = process_batch(batch_id)
            self.stdout.write(
                self.style.SUCCESS(f"Processed batch {batch_id}: {result}")
            )
            return

        qs = IngestionBatch.objects.filter(
            status=IngestionBatch.Status.STAGED
        ).order_by("uploaded_at")
        batches = list(qs[:limit])
        if not batches:
            self.stdout.write("No STAGED batches found.")
            return

        ok = 0
        failed = 0
        for b in batches:
            try:
                result = process_batch(b.id)
                if not result.get("success"):
                    raise RuntimeError(result)
                ok += 1
            except Exception as e:
                failed += 1
                self.stderr.write(self.style.ERROR(f"Failed batch {b.id}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Done. OK={ok}, Failed={failed}"))
