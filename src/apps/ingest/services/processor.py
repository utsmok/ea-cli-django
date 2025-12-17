"""
Batch processor service.

Processes staged entries (FacultyEntry or QlikEntry) and applies changes
to CopyrightItem records using merge rules.
"""

from django.db import transaction
from django.utils import timezone
from loguru import logger

from apps.core.models import ChangeLog, CopyrightItem, Faculty
from apps.ingest.models import (
    FacultyEntry,
    IngestionBatch,
    ProcessingFailure,
    QlikEntry,
)
from apps.ingest.services.merge_rules import (
    QLIK_CREATEABLE_FIELDS,
    get_faculty_strategy,
    get_qlik_strategy,
)
from config.university import DEPARTMENT_MAPPING_LOWER, FACULTY_NAME_BY_ABBR


class BatchProcessor:
    """
    Processes ingestion batches and updates CopyrightItems.

    Handles both Qlik (create/update) and Faculty (update-only) batches.
    """

    def __init__(self, batch: IngestionBatch):
        self.batch = batch
        self.stats = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
        }

    def process(self):
        """
        Main processing entry point.

        Dispatches to appropriate handler based on source type.
        """
        try:
            self.batch.status = IngestionBatch.Status.PROCESSING
            self.batch.started_at = timezone.now()
            self.batch.save(update_fields=["status", "started_at"])

            if self.batch.source_type == IngestionBatch.SourceType.QLIK:
                self._process_qlik_batch()
            elif self.batch.source_type == IngestionBatch.SourceType.FACULTY:
                self._process_faculty_batch()
            else:
                raise ValueError(f"Unknown source type: {self.batch.source_type}")

            # Update final statistics
            self.batch.items_created = self.stats["created"]
            self.batch.items_updated = self.stats["updated"]
            self.batch.items_skipped = self.stats["skipped"]
            self.batch.items_failed = self.stats["failed"]
            self.batch.completed_at = timezone.now()

            # Determine final status
            if self.stats["failed"] == 0:
                self.batch.status = IngestionBatch.Status.COMPLETED
            elif self.stats["failed"] < self.batch.rows_staged:
                self.batch.status = IngestionBatch.Status.PARTIAL
            else:
                self.batch.status = IngestionBatch.Status.FAILED

            self.batch.save(
                update_fields=[
                    "items_created",
                    "items_updated",
                    "items_skipped",
                    "items_failed",
                    "completed_at",
                    "status",
                ]
            )

            logger.info(
                f"Batch from file {self.batch.source_file} complete: "
                f"{self.stats['created']} created, "
                f"{self.stats['updated']} updated, "
                f"{self.stats['skipped']} skipped, "
                f"{self.stats['failed']} failed"
            )

        except Exception as e:
            logger.error(
                f"ingesting batch from file {self.batch.source_file} failed: {e}"
            )
            self.batch.status = IngestionBatch.Status.FAILED
            self.batch.error_message = str(e)
            self.batch.completed_at = timezone.now()
            self.batch.save(update_fields=["status", "error_message", "completed_at"])
            raise

    def _process_qlik_batch(self):
        """Process Qlik entries (can create + update)."""
        entries = self.batch.qlik_entries.filter(processed=False).order_by("row_number")

        for entry in entries:
            try:
                with transaction.atomic():
                    self._process_qlik_entry(entry)
                    entry.processed = True
                    entry.processed_at = timezone.now()
                    entry.save(update_fields=["processed", "processed_at"])
            except Exception as e:
                logger.error(
                    f"Failed to process Qlik entry {entry.material_id} "
                    f"(row {entry.row_number}): {e}"
                )
                self._record_failure(
                    entry.material_id,
                    entry.row_number,
                    type(e).__name__,
                    str(e),
                    self._entry_to_dict(entry),
                )
                self.stats["failed"] += 1

    def _process_faculty_batch(self):
        """Process Faculty entries (update-only)."""
        entries = self.batch.faculty_entries.filter(processed=False).order_by(
            "row_number"
        )

        for entry in entries:
            try:
                with transaction.atomic():
                    self._process_faculty_entry(entry)
                    entry.processed = True
                    entry.processed_at = timezone.now()
                    entry.save(update_fields=["processed", "processed_at"])
            except Exception as e:
                logger.error(
                    f"Failed to process Faculty entry {entry.material_id} "
                    f"(row {entry.row_number}): {e}"
                )
                self._record_failure(
                    entry.material_id,
                    entry.row_number,
                    type(e).__name__,
                    str(e),
                    self._entry_to_dict(entry),
                )
                self.stats["failed"] += 1

    def _process_qlik_entry(self, entry: QlikEntry):
        """
        Process a single Qlik entry.

        Can CREATE new items or UPDATE existing items (system fields only).
        """
        # Try to get existing item
        try:
            item = CopyrightItem.objects.get(material_id=entry.material_id)
            created = False
        except CopyrightItem.DoesNotExist:
            # Create new item
            item = CopyrightItem(material_id=entry.material_id)
            created = True

        # Collect changes
        changes = {}

        faculty_obj = self._resolve_faculty(entry.department)

        # Process all Qlik-managed fields
        for field_name in QLIK_CREATEABLE_FIELDS:
            # Get new value from entry
            new_value = getattr(entry, field_name, None)

            if created:
                # New item: set all non-null fields
                if new_value is not None:
                    setattr(item, field_name, new_value)
                    changes[field_name] = {"old": None, "new": new_value}
            else:
                # Existing item: use merge strategy
                old_value = getattr(item, field_name, None)
                strategy = get_qlik_strategy(field_name)

                if strategy and strategy.should_update(old_value, new_value):
                    setattr(item, field_name, new_value)
                    changes[field_name] = {"old": old_value, "new": new_value}

        # Save item
        if faculty_obj and (item.faculty_id != faculty_obj.id):
            old_faculty = item.faculty.abbreviation if item.faculty else None
            item.faculty = faculty_obj
            changes["faculty"] = {
                "old": old_faculty,
                "new": faculty_obj.abbreviation,
            }

        if changes:
            item.save()

            # Create ChangeLog entry
            ChangeLog.objects.create(
                item=item,
                changes=changes,
                changed_by=self.batch.uploaded_by,
                change_source=ChangeLog.ChangeSource.QLIK_INGESTION,
                batch=self.batch,
            )

            if created:
                self.stats["created"] += 1
                logger.debug(f"Created item {item.material_id}")
            else:
                self.stats["updated"] += 1
                logger.debug(
                    f"Updated item {item.material_id} ({len(changes)} changes)"
                )
        else:
            self.stats["skipped"] += 1
            logger.debug(f"Skipped item {entry.material_id} (no changes)")

    def _process_faculty_entry(self, entry: FacultyEntry):
        """
        Process a single Faculty entry.

        Can ONLY update existing items (human fields only).
        Faculty ingestion NEVER creates new items.
        """
        # Faculty entries must reference existing items
        try:
            item = CopyrightItem.objects.get(material_id=entry.material_id)
        except CopyrightItem.DoesNotExist:
            raise ValueError(
                f"Faculty entry references non-existent material_id: {entry.material_id}. "
                "Faculty sheets can only update existing items, not create new ones."
            )

        # Collect changes
        changes = {}

        # Process all Faculty-managed fields
        faculty_fields = [
            "workflow_status",
            "classification",
            "manual_classification",
            "v2_manual_classification",
            "v2_overnamestatus",
            "v2_lengte",
            "remarks",
            "scope",
            "manual_identifier",
        ]

        for field_name in faculty_fields:
            # Get new value from entry
            new_value = getattr(entry, field_name, None)

            if new_value is None:
                continue  # Skip null values (no update)

            # Get current value from item
            old_value = getattr(item, field_name, None)

            # Get merge strategy
            strategy = get_faculty_strategy(field_name)

            if strategy and strategy.should_update(old_value, new_value):
                setattr(item, field_name, new_value)
                changes[field_name] = {"old": old_value, "new": new_value}

        # Save item
        if changes:
            item.save()

            # Create ChangeLog entry
            ChangeLog.objects.create(
                item=item,
                changes=changes,
                changed_by=self.batch.uploaded_by,
                change_source=ChangeLog.ChangeSource.FACULTY_INGESTION,
                batch=self.batch,
            )

            self.stats["updated"] += 1
            logger.debug(f"Updated item {item.material_id} ({len(changes)} changes)")
        else:
            self.stats["skipped"] += 1
            logger.debug(f"Skipped item {entry.material_id} (no changes)")

    def _record_failure(
        self,
        material_id: int | None,
        row_number: int,
        error_type: str,
        error_message: str,
        row_data: dict,
    ):
        """Record a processing failure for debugging."""
        ProcessingFailure.objects.create(
            batch=self.batch,
            material_id=material_id,
            row_number=row_number,
            error_type=error_type,
            error_message=error_message,
            row_data=row_data,
        )

    def _entry_to_dict(self, entry) -> dict:
        """Convert entry to dict for failure logging."""
        if isinstance(entry, QlikEntry):
            return {
                "material_id": entry.material_id,
                "filename": entry.filename,
                "filetype": entry.filetype,
                "title": entry.title,
                "author": entry.author,
                "department": entry.department,
                # ... add more fields as needed for debugging
            }
        elif isinstance(entry, FacultyEntry):
            return {
                "material_id": entry.material_id,
                "workflow_status": entry.workflow_status,
                "classification": entry.classification,
                "remarks": entry.remarks,
                # ... add more fields as needed for debugging
            }
        return {}

    def _resolve_faculty(self, department: str | None) -> Faculty | None:
        """Map department/programme text to Faculty instance using config mapping."""

        if not department:
            return None

        mapped = DEPARTMENT_MAPPING_LOWER.get(department.strip().lower())
        if not mapped:
            return None

        defaults = {
            "name": FACULTY_NAME_BY_ABBR.get(mapped, mapped),
            "full_abbreviation": mapped,
            "hierarchy_level": 1,
        }
        faculty, _ = Faculty.objects.get_or_create(
            abbreviation=mapped,
            defaults=defaults,
        )
        return faculty
