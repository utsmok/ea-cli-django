from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand

from apps.ingest.models import IngestionBatch
from apps.ingest.tasks import process_batch, stage_batch


class Command(BaseCommand):
    help = "Ingest raw copyright Excel file via the Phase A ingestion pipeline (IngestionBatch)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file", type=str, help="Path to the Excel file to ingest."
        )
        parser.add_argument(
            "--legacy-path",
            action="store_true",
            help="Look in the legacy ea-cli/raw_copyright_data folder for the newest file.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            default=True,
            help="Deprecated (kept for compatibility). No-op in Phase A pipeline.",
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        use_legacy = options["legacy_path"]

        target_file = None

        if file_path:
            target_file = Path(file_path)
        elif use_legacy:
            # Try to locate the legacy folder relative to the project root
            # Assuming BASE_DIR is src/..
            # settings.BASE_DIR is usually defined as the parent of config (so src/config/.. -> src)
            # wait, in settings.py: BASE_DIR = Path(__file__).resolve().parent.parent (which is 'src')
            # So project root is BASE_DIR.parent
            base_dir = Path(settings.BASE_DIR)
            legacy_dir = base_dir.parent / "ea-cli" / "raw_copyright_data"

            if not legacy_dir.exists():
                self.stderr.write(f"Legacy directory not found: {legacy_dir}")
                return

            # Find newest xlsx
            files = list(legacy_dir.glob("*.xlsx"))
            if not files:
                self.stderr.write("No .xlsx files found in legacy directory.")
                return

            # Use creation time to find newest
            target_file = max(files, key=lambda f: f.stat().st_ctime)
            self.stdout.write(f"Found newest file in legacy path: {target_file}")

        else:
            self.stderr.write("Please provide --file or --legacy-path")
            return

        if not target_file or not target_file.exists():
            self.stderr.write(f"File not found: {target_file}")
            return

        self.stdout.write(f"Ingesting raw export via batch pipeline: {target_file}")

        User = get_user_model()
        user, _ = User.objects.get_or_create(username="system")
        if not user.has_usable_password():
            user.set_unusable_password()
            user.save(update_fields=["password"])

        batch = IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            uploaded_by=user,
        )

        with open(target_file, "rb") as fh:
            batch.source_file = File(fh, name=Path(target_file).name)
            batch.save()

        stage_result = stage_batch(batch.id)
        if not stage_result.get("success"):
            raise RuntimeError(f"Staging failed: {stage_result}")

        process_result = process_batch(batch.id)
        if not process_result.get("success"):
            raise RuntimeError(f"Processing failed: {process_result}")

        self.stdout.write(
            self.style.SUCCESS(f"Batch {batch.id} complete: {process_result}")
        )
