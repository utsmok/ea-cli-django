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
from apps.ingest.services.standardizer import safe_datetime
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
        """Process Qlik entries (can create + update).

        Each entry is processed in its own transaction - if one fails,
        it rolls back independently without affecting other entries.
        """
        entries = self.batch.qlik_entries.filter(processed=False).order_by("row_number")

        for entry in entries:
            try:
                # Each item is processed in its own transaction
                with transaction.atomic(savepoint=True):
                    self._process_qlik_entry(entry)
                    entry.processed = True
                    entry.processed_at = timezone.now()
                    entry.save(update_fields=["processed", "processed_at"])
            except Exception as e:
                logger.exception(
                    f"Failed to process Qlik entry {entry.material_id} "
                    f"(row {entry.row_number})"
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
        """Process Faculty entries (update-only).

        Each entry is processed in its own transaction - if one fails,
        it rolls back independently without affecting other entries.
        """
        entries = self.batch.faculty_entries.filter(processed=False).order_by(
            "row_number"
        )

        for entry in entries:
            try:
                # Each item is processed in its own transaction
                with transaction.atomic(savepoint=True):
                    self._process_faculty_entry(entry)
                    entry.processed = True
                    entry.processed_at = timezone.now()
                    entry.save(update_fields=["processed", "processed_at"])
            except Exception as e:
                logger.exception(
                    f"Failed to process Faculty entry {entry.material_id} "
                    f"(row {entry.row_number})"
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

        Two-step process:
        1. Create/update QlikItem (exact mirror of Qlik data)
        2. Merge to CopyrightItem (preserving existing data when Qlik has nulls)
        """
        from apps.core.models import QlikItem

        # Fields that exist on both QlikItem and CopyrightItem
        QLIK_MIRROR_FIELDS = [
            "filename",
            "filehash",
            "filetype",
            "url",
            "title",
            "author",
            "publisher",
            "period",
            "department",
            "course_code",
            "course_name",
            "status",
            "classification",
            "ml_classification",
            "isbn",
            "doi",
            "owner",
            "in_collection",
            "picturecount",
            "reliability",
            "pages_x_students",
            "count_students_registered",
            "pagecount",
            "wordcount",
            "canvas_course_id",
            "retrieved_from_copyright_on",
        ]

        # Step 1: Create/update QlikItem (exact mirror of Qlik data)
        try:
            qlik_item = QlikItem.objects.get(material_id=entry.material_id)
        except QlikItem.DoesNotExist:
            qlik_item = QlikItem(material_id=entry.material_id)

        # Update QlikItem with all values from entry (even nulls - this is the mirror)
        for field_name in QLIK_MIRROR_FIELDS:
            value = getattr(entry, field_name, None)
            if field_name == "retrieved_from_copyright_on":
                value = safe_datetime(value)
            setattr(qlik_item, field_name, value)

        qlik_item.qlik_source_file = self.batch.source_file
        qlik_item.save()

        # Step 2: Get or create CopyrightItem (working copy that preserves data)
        try:
            item = CopyrightItem.objects.get(material_id=entry.material_id)
            created = False
        except CopyrightItem.DoesNotExist:
            item = CopyrightItem(material_id=entry.material_id)
            created = True

        changes = {}
        faculty_obj = self._resolve_faculty(entry.department)

        # Merge Qlik data to CopyrightItem
        # Key rule: only update if new value is not null/empty
        # This preserves existing data when Qlik loses values
        for field_name in QLIK_MIRROR_FIELDS:
            new_value = getattr(entry, field_name, None)

            # Special handling for date fields
            if field_name == "retrieved_from_copyright_on":
                new_value = safe_datetime(new_value)

            # Skip null/empty values - preserve existing data in CopyrightItem
            if new_value is None or new_value == "":
                continue

            old_value = getattr(item, field_name, None)

            # For new items: set all non-null values
            # For existing items: only update if value actually changed
            if created or old_value != new_value:
                # Use merge strategy if available, otherwise just update
                if not created:
                    strategy = get_qlik_strategy(field_name)
                    if strategy and not strategy.should_update(old_value, new_value):
                        continue

                setattr(item, field_name, new_value)
                changes[field_name] = {"old": old_value, "new": new_value}

        # Handle faculty assignment
        if faculty_obj and (item.faculty_id != faculty_obj.id):
            old_faculty = item.faculty.abbreviation if item.faculty else None
            item.faculty = faculty_obj
            changes["faculty"] = {
                "old": old_faculty,
                "new": faculty_obj.abbreviation,
            }

        if changes or created:
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
