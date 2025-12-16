import logging
from typing import Any, Dict, List
from datetime import datetime, date

from django.db import transaction
from django.db.models import Q

from apps.core.models import (
    StagedItem,
    CopyrightItem,
    Faculty,
    Course,
    Status,
    Classification,
    WorkflowStatus,
    ItemUpdate
)
from apps.core.utils.safecast import safe_int, safe_float, safe_enum, safe_int
from apps.core.utils.course_parser import determine_course_code
from apps.core.services import merging

logger = logging.getLogger(__name__)

class PipelineService:
    def __init__(self):
        self.faculty_cache = {}
        self._load_faculties()

    def _load_faculties(self):
        for f in Faculty.objects.all():
            self.faculty_cache[f.abbreviation] = f
            # Also map full_abbreviation if different?
            if f.full_abbreviation and f.full_abbreviation != f.abbreviation:
                self.faculty_cache[f.full_abbreviation] = f

    def get_faculty(self, abbr: str | None) -> Faculty:
        if not abbr:
            return self.faculty_cache.get("UNM")

        # Try direct match
        if f := self.faculty_cache.get(abbr):
            return f

        # Try finding simplified UNM or default
        return self.faculty_cache.get("UNM")

    def process_staged_items(self, batch_size: int = 500):
        """Processes all pending StagedItems."""

        # We process in chunks to avoid memory issues
        while True:
            # Fetch a batch of pending items
            # lock rows? StagedItem.objects.select_for_update().filter(status="PENDING")[:batch_size]
            # simplified:
            batch = list(StagedItem.objects.filter(status="PENDING")[:batch_size])
            if not batch:
                break

            logger.info(f"Processing batch of {len(batch)} staged items...")

            with transaction.atomic():
                processed_ids = []
                for item in batch:
                    try:
                        self._process_single_item(item)
                        processed_ids.append(item.id)
                    except Exception as e:
                        logger.exception(f"Failed to process StagedItem {item.id}: {e}")
                        item.status = "FAILED"
                        item.error_message = str(e)[:500]
                        item.save()

                # Delete processed items or mark done?
                # Legacy deleted them.
                if processed_ids:
                    StagedItem.objects.filter(id__in=processed_ids).delete()
                    logger.info(f"Deleted {len(processed_ids)} processed StagedItems.")

    def _process_single_item(self, staged: StagedItem):
        data = staged.payload
        mid = staged.target_material_id

        # If target_material_id is missing from staged model field, try payload
        if not mid:
            mid = safe_int(data.get("material_id"))

        if not mid:
            raise ValueError("Missing material_id")

        # Check source type
        if staged.source_type == StagedItem.SourceType.CRC_EXPORT:
            self._process_raw_export(mid, data)
        elif staged.source_type == StagedItem.SourceType.FACULTY_SHEET:
            self._process_faculty_update(mid, data)
        else:
            logger.warning(f"Unknown source type {staged.source_type}")

    def _process_raw_export(self, mid: int, data: Dict[str, Any]):
        item = CopyrightItem.objects.filter(material_id=mid).first()

        if not item:
            # CREATE NEW
            self._create_copyright_item(mid, data)
        else:
            # UPDATE EXISTING
            self._update_copyright_item(item, data)

    def _create_copyright_item(self, mid: int, data: Dict[str, Any]):
        # Map fields
        # Using safely cast setters

        faculty_abbr = data.get("faculty")
        if not faculty_abbr or faculty_abbr == "Unmapped":
            faculty_abbr = "UNM"

        faculty = self.get_faculty(faculty_abbr)

        # Defaults
        classification = data.get("classification", Classification.LANGE_OVERNAME)
        status = data.get("status", Status.PUBLISHED)

        # Casting
        pagecount = safe_int(data.get("pagecount"), 0)
        wordcount = safe_int(data.get("wordcount"), 0)
        # etc.

        # Create
        new_item = CopyrightItem(
            material_id=mid,
            faculty=faculty,
            period=data.get("period", ""),
            department=data.get("department", ""),
            course_code=data.get("course_code", ""),
            course_name=data.get("course_name", ""),
            url=data.get("url", ""),
            filename=data.get("filename", ""),
            title=data.get("title", ""),
            owner=data.get("owner", ""),
            filetype=data.get("filetype", "unknown"),
            classification=classification,
            manual_classification=data.get("manual_classification"),
            manual_identifier=data.get("manual_identifier"),
            scope=data.get("scope"),
            remarks=data.get("remarks"),
            isbn=data.get("isbn"),
            doi=data.get("doi"),
            author=data.get("author"),
            publisher=data.get("publisher"),
            status=status,
            workflow_status=data.get("workflow_status", WorkflowStatus.TODO),
            pagecount=pagecount,
            wordcount=wordcount,
            picturecount=safe_int(data.get("picturecount"), 0),
            reliability=safe_int(data.get("reliability"), 0),
            pages_x_students=safe_int(data.get("pages_x_students"), 0),
            count_students_registered=safe_int(data.get("count_students_registered"), 0),
            file_exists=self._normalize_file_exists(data.get("file_exists")),
        )

        # Date fields safety
        if lc := data.get("last_change"):
            try:
                if isinstance(lc, str):
                    new_item.last_change = datetime.strptime(lc[:10], "%Y-%m-%d").date()
            except ValueError:
                pass

        if rc := data.get("retrieved_from_copyright_on"):
             try:
                if isinstance(rc, str):
                    new_item.retrieved_from_copyright_on = datetime.strptime(rc[:10], "%Y-%m-%d").date()
             except ValueError:
                pass

        new_item.save()
        # logger.debug(f"Created new CopyrightItem {mid}")

        # Link Courses (heuristic)
        self._link_courses(new_item)


    def _update_copyright_item(self, item: CopyrightItem, data: Dict[str, Any]):
        # Check merges
        mergeable = merging.get_mergeable_fields()
        changes = {}

        for field, ordering in mergeable.items():
            new_val = data.get(field)
            if new_val is None:
                continue

            old_val = getattr(item, field)

            # Normalize file_exists
            if field == "file_exists":
                new_val = self._normalize_file_exists(new_val)
                # Strategy expects actual values

            strategy = merging.determine_strategy_by_value(field, old_val, ordering)
            should_update, reason = strategy.should_update(new_val, old_val, ordering)

            if should_update:
                setattr(item, field, new_val)
                changes[field] = {"old": str(old_val), "new": str(new_val), "reason": reason}

        # Check trivial fields (status, last_change)
        # Using loose equivalence
        new_status_str = data.get("status")
        if new_status_str:
            # Cast to Status Enum
             # Assuming safe_enum...
             pass

        if changes:
             item.save()
             # Record history
             ItemUpdate.objects.create(
                 material_id=item.material_id,
                 change_details=changes
             )

    def _process_faculty_update(self, mid: int, data: Dict[str, Any]):
        item = CopyrightItem.objects.filter(material_id=mid).first()
        if not item:
            return # Skip if not found

        changes = {}
        # fields to check: manual_classification, remarks, workflow_status

        if mc := data.get("manual_classification"):
            if item.manual_classification != mc:
                old = item.manual_classification
                item.manual_classification = mc
                changes["manual_classification"] = {"old": str(old), "new": mc}

        if rem := data.get("remarks"):
            if item.remarks != rem:
                old = item.remarks
                item.remarks = rem
                changes["remarks"] = {"old": str(old), "new": rem}

        if wf := data.get("workflow_status"):
            # Normalize logic from legacy (inbox/in_progress -> InProgress)
            norm_wf = self._normalize_workflow_status(wf)
            if norm_wf and item.workflow_status != norm_wf:
                old = item.workflow_status
                item.workflow_status = norm_wf
                changes["workflow_status"] = {"old": str(old), "new": norm_wf}

        if changes:
            item.save()
            # Record update? Optional for faculty sheets, but good practice.
            # ItemUpdate.objects.create(...)

    def _link_courses(self, item: CopyrightItem):
        # Heuristic to find courses
        codes = determine_course_code(item.course_code, item.course_name)
        if not codes:
            return

        courses = Course.objects.filter(cursuscode__in=list(codes))
        if courses.exists():
            item.courses.add(*courses)

    def _normalize_file_exists(self, value: Any) -> bool | None:
        if value is None or value == "":
            return None
        if str(value).lower() in ["true", "1", "yes"]:
            return True
        return False

    def _normalize_workflow_status(self, val: str) -> str | None:
        if not val:
            return None
        s = str(val).strip().lower()
        map = {
            "todo": WorkflowStatus.TODO,
            "to do": WorkflowStatus.TODO,
            "inbox": WorkflowStatus.TODO,
            "in_progress": WorkflowStatus.IN_PROGRESS,
            "in progress": WorkflowStatus.IN_PROGRESS,
            "inprogress": WorkflowStatus.IN_PROGRESS,
            "done": WorkflowStatus.DONE,
        }
        return map.get(s)
