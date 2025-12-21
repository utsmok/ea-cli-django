import os

from django.core.files import File as DjangoFile
from django.core.management.base import BaseCommand

from apps.ingest.models import IngestionBatch
from apps.ingest.tasks import process_batch, stage_batch
from apps.users.models import User


class Command(BaseCommand):
    help = "Ingests a Qlik Excel file from a specified path."

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            type=str,
            help="The absolute or relative path to the Qlik Excel file.",
        )

    def handle(self, *args, **options):
        file_path = options["file_path"]
        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f"File not found at: {file_path}"))
            return

        # Ensure a superuser exists to own the batch
        user, created = User.objects.get_or_create(
            username="admin", defaults={"is_staff": True, "is_superuser": True}
        )
        if created:
            user.set_password("admin")
            user.save()
            self.stdout.write(
                self.style.SUCCESS("Created admin user with password 'admin'")
            )

        self.stdout.write(f"Ingesting file: {file_path}")

        with Path.open(file_path, "rb") as f:
            django_file = DjangoFile(f, name=os.path.basename(file_path))

            # Create the IngestionBatch
            batch = IngestionBatch.objects.create(
                source_type=IngestionBatch.SourceType.QLIK,
                source_file=django_file,
                uploaded_by=user,
            )
            self.stdout.write(self.style.SUCCESS(f"Created IngestionBatch #{batch.id}"))

        self.stdout.write("Staging batch...")
        stage_result = stage_batch(batch.id)
        if not stage_result["success"]:
            self.stderr.write(
                self.style.ERROR(f"Staging failed: {batch.error_message}")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"Staging complete. {batch.rows_staged} rows staged.")
        )

        self.stdout.write("Processing batch...")
        process_result = process_batch(batch.id)
        if not process_result["success"]:
            self.stderr.write(
                self.style.ERROR(f"Processing failed: {batch.error_message}")
            )
            return

        self.stdout.write(self.style.SUCCESS("Processing complete!"))
        self.stdout.write(f"  Items created: {batch.items_created}")
        self.stdout.write(f"  Items updated: {batch.items_updated}")
        self.stdout.write(f"  Items skipped: {batch.items_skipped}")
        self.stdout.write(f"  Items failed: {batch.items_failed}")
