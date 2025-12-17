from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand

from apps.ingest.models import IngestionBatch
from apps.ingest.tasks import process_batch, stage_batch


class Command(BaseCommand):
    help = "Ingest Faculty Sheets (workflow workbooks) via the Phase A ingestion pipeline (IngestionBatch)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir", type=str, help="Path to the faculty sheets directory."
        )
        parser.add_argument(
            "--legacy-path",
            action="store_true",
            help="Look in the legacy ea-cli/faculty_sheets folder.",
        )
        parser.add_argument(
            "--sheet-name",
            type=str,
            default="Data entry",
            help="Deprecated (kept for compatibility). Phase A pipeline always reads the first sheet.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            default=True,
            help="Deprecated (kept for compatibility). No-op in Phase A pipeline.",
        )

    def handle(self, *args, **options):
        dir_path = options["dir"]
        use_legacy = options["legacy_path"]
        target_dir = None

        if dir_path:
            target_dir = Path(dir_path)
        elif use_legacy:
            base_dir = Path(settings.BASE_DIR)
            target_dir = base_dir.parent / "ea-cli" / "faculty_sheets"
        else:
            self.stderr.write("Please provide --dir or --legacy-path")
            return

        if not target_dir or not target_dir.exists():
            self.stderr.write(f"Directory not found: {target_dir}")
            return

        self.stdout.write(f"Ingesting faculty sheets from {target_dir}...")

        User = get_user_model()
        user, _ = User.objects.get_or_create(username="system")
        if not user.has_usable_password():
            user.set_unusable_password()
            user.save(update_fields=["password"])

        # Expect a tree like: <root>/<FACULTY>/(inbox|in_progress|done).xlsx
        workbooks = []
        for faculty_dir in sorted([p for p in target_dir.iterdir() if p.is_dir()]):
            faculty_code = faculty_dir.name
            for bucket in ["inbox", "in_progress", "done"]:
                path = faculty_dir / f"{bucket}.xlsx"
                if path.exists():
                    workbooks.append((faculty_code, bucket, path))

        if not workbooks:
            self.stdout.write("No faculty workbook files found.")
            return

        ok = 0
        failed = 0
        for faculty_code, bucket, path in workbooks:
            self.stdout.write(f"- Processing {faculty_code}/{path.name}...")
            batch = IngestionBatch.objects.create(
                source_type=IngestionBatch.SourceType.FACULTY,
                uploaded_by=user,
                faculty_code=faculty_code,
            )

            with open(path, "rb") as fh:
                batch.source_file = File(fh, name=f"{faculty_code}_{bucket}.xlsx")
                batch.save()

            try:
                stage_result = stage_batch(batch.id)
                if not stage_result.get("success"):
                    raise RuntimeError(f"Staging failed: {stage_result}")

                process_result = process_batch(batch.id)
                if not process_result.get("success"):
                    raise RuntimeError(f"Processing failed: {process_result}")

                ok += 1
            except Exception as e:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(f"  Failed {faculty_code}/{path.name}: {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(f"Faculty ingestion complete. OK={ok}, Failed={failed}")
        )
