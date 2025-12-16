import logging
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.ingest.utils import read_faculty_sheets, sanitize_payload
from apps.core.models import StagedItem

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Ingest Faculty Sheets (updates) into StagedItem table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            type=str,
            help="Path to the faculty sheets directory."
        )
        parser.add_argument(
            "--legacy-path",
            action="store_true",
            help="Look in the legacy ea-cli/faculty_sheets folder."
        )
        parser.add_argument(
            "--sheet-name",
            type=str,
            default="Data entry",
            help="Name of the worksheet to read (default 'Data entry')."
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            default=True,
            help="Clear existing StagedItem records of type 'SHEET' before ingesting (default True)."
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

        # Process
        self.stdout.write(f"Reading faculty sheets from {target_dir}...")
        try:
            df = read_faculty_sheets(target_dir, data_entry_name=options["sheet_name"])

            if df.is_empty():
                self.stdout.write("No data found or directory empty.")
                return

            count = len(df)
            self.stdout.write(f"Read {count} records.")

            # Convert to dicts
            records = df.to_dicts()

            # Sanitize payloads
            sanitized_records = [sanitize_payload(r) for r in records]

            # Clear old data
            if options["clear"]:
                deleted, _ = StagedItem.objects.filter(source_type=StagedItem.SourceType.FACULTY_SHEET).delete()
                self.stdout.write(f"Deleted {deleted} existing StagedItems (SHEET).")

            # Create StagedItem objects
            batch_size = 1000
            objs = []

            for i, record in enumerate(sanitized_records):
                m_id = record.get("material_id")
                try:
                    m_id = int(str(m_id).split(".")[0]) if m_id is not None and str(m_id) != "None" else None
                except Exception:
                    m_id = None

                objs.append(StagedItem(
                    source_type=StagedItem.SourceType.FACULTY_SHEET,
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

            self.stdout.write(self.style.SUCCESS("Faculty ingestion complete."))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Ingestion failed: {e}"))
            raise e
