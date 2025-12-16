import logging
from django.core.management.base import BaseCommand
from apps.core.services.pipeline import PipelineService

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Process StagedItems into CopyrightItems."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of items to process per batch."
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]

        self.stdout.write("Starting processing pipeline...")
        try:
            service = PipelineService()
            service.process_staged_items(batch_size=batch_size)
            self.stdout.write(self.style.SUCCESS("Processing complete."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Processing failed: {e}"))
            raise e
