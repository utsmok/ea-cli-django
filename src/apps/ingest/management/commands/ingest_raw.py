import logging
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.ingest.utils import read_raw_copyright_file, sanitize_payload
from apps.core.models import StagedItem

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Ingest raw copyright Excel file into StagedItem table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            help="Path to the Excel file to ingest."
        )
        parser.add_argument(
            "--legacy-path",
            action="store_true",
            help="Look in the legacy ea-cli/raw_copyright_data folder for the newest file."
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            default=True,
            help="Clear existing StagedItem records of type 'CRC' before ingesting (default True)."
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

        # Process
        self.stdout.write(f"Processing {target_file}...")
        try:
            date_str, df = read_raw_copyright_file(target_file)
            count = len(df)
            self.stdout.write(f"Read {count} records. Date: {date_str}")

            # Convert to dicts
            records = df.to_dicts()

            # Sanitize payloads (NaN -> None)
            sanitized_records = [sanitize_payload(r) for r in records]

            # Clear old data?
            if options["clear"]:
                deleted, _ = StagedItem.objects.filter(source_type=StagedItem.SourceType.CRC_EXPORT).delete()
                self.stdout.write(f"Deleted {deleted} existing StagedItems (CRC).")

            # Create StagedItem objects
            batch_size = 1000
            objs = []

            for i, record in enumerate(sanitized_records):
                # We can try to extract target_material_id from record if available
                m_id = record.get("material_id")
                # Ensure it's an int if possible, safely
                try:
                    m_id = int(str(m_id).split(".")[0]) if m_id is not None else None
                except Exception:
                    m_id = None

                objs.append(StagedItem(
                    source_type=StagedItem.SourceType.CRC_EXPORT,
                    target_material_id=m_id,
                    payload=record,
                    status="PENDING"
                ))

                if len(objs) >= batch_size:
                    StagedItem.objects.bulk_create(objs)
                    self.stdout.write(f"Saved {i+1} records...")
                    objs = []

            if objs:
                StagedItem.objects.bulk_create(objs)
                self.stdout.write(f"Saved remaining {len(objs)} records.")

            self.stdout.write(self.style.SUCCESS("Ingestion complete."))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Ingestion failed: {e}"))
            raise e
