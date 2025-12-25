"""
Detail Service: Assembles rich detail view data.

Responsibilities:
- Fetch related objects (courses, teachers, entities)
- Get enrichment history
- Get change logs
- Determine file availability

This centralizes data fetching for all three detail views:
1. Split panel (partial)
2. Modal (full)
3. Dedicated page (complete)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import QuerySet, Prefetch
from django.db.models import Q

from apps.core.models import CopyrightItem, Course, Person, ChangeLog

if TYPE_CHECKING:
    from .query_service import ItemQueryFilter


@dataclass
class ItemDetailData:
    """
    Complete detail data for an item.

    This makes the service contract explicit - tests can verify
    exactly what data is returned.
    """

    item: CopyrightItem
    courses: list[Course]
    course_teachers: list[tuple[Course, list[Person]]]  # List of (course, teachers) for templates
    pdf_available: bool
    pdf_url: str | None
    enrichment_history: list[ChangeLog]
    recent_changes: list[ChangeLog]
    related_items: list[CopyrightItem]  # Same filehash (duplicates)


class ItemDetailService:
    """
    Service for fetching complete detail view data.

    This service optimizes queries to avoid N+1 problems
    when fetching related data.
    """

    def get_detail_data(self, material_id: int) -> ItemDetailData:
        """
        Fetch all data needed for detail views.

        Uses prefetch_related to efficiently load:
        - Courses for this item
        - Teachers for each course
        - Change logs
        - Related items (same filehash)
        """
        # Fetch item with related objects
        item = (
            CopyrightItem.objects.select_related("faculty", "document")
            .prefetch_related(
                Prefetch("courses", queryset=Course.objects.select_related("faculty")),
                "courses__teachers",
                "change_logs__changed_by",
            )
            .get(material_id=material_id)
        )

        # Extract courses and teachers
        courses = list(item.courses.all())
        course_teachers = [(course, list(course.teachers.all())) for course in courses]

        # Determine PDF availability
        pdf_available = bool(item.document and item.document.file)
        pdf_url = item.document.file.url if pdf_available else None

        # Get enrichment history (ENRICHMENT source changes)
        enrichment_history = list(
            item.change_logs.filter(change_source=ChangeLog.ChangeSource.ENRICHMENT)
            .order_by("-changed_at")[:10]
        )

        # Get recent manual changes (MANUAL_EDIT source changes)
        recent_changes = list(
            item.change_logs.filter(change_source=ChangeLog.ChangeSource.MANUAL_EDIT)
            .order_by("-changed_at")[:10]
        )

        # Find related items (same filehash = potential duplicates)
        related_items = []
        if item.filehash:
            related_items = list(
                CopyrightItem.objects.filter(filehash=item.filehash)
                .exclude(material_id=material_id)
                .select_related("faculty")[:5]
            )

        return ItemDetailData(
            item=item,
            courses=courses,
            course_teachers=course_teachers,
            pdf_available=pdf_available,
            pdf_url=pdf_url,
            enrichment_history=enrichment_history,
            recent_changes=recent_changes,
            related_items=related_items,
        )

    def get_minimal_detail(self, material_id: int) -> CopyrightItem:
        """
        Fetch minimal data for split panel (fast loading).

        Split panel only shows:
        - PDF preview
        - Basic info
        - Quick classification fields

        This is optimized for speed.
        """
        return (
            CopyrightItem.objects.select_related("faculty", "document")
            .prefetch_related("courses__teachers")
            .get(material_id=material_id)
        )

    def get_navigation_ids(
        self, material_id: int, filters: ItemQueryFilter | None = None
    ) -> tuple[int | None, int | None]:
        """
        Get previous and next item IDs for navigation.

        Respects current filters to navigate within filtered results.

        Returns: (prev_id, next_id) or (None, None)
        """
        # Import here to avoid circular dependency
        from .query_service import ItemQueryService

        query_service = ItemQueryService()

        if filters:
            # Get filtered queryset
            qs = query_service.get_filtered_queryset(filters)
        else:
            # Get all items
            qs = CopyrightItem.objects.all()

        # Get list of IDs (more efficient than fetching full objects)
        item_ids = list(qs.values_list("material_id", flat=True).order_by("-modified_at"))

        try:
            current_idx = item_ids.index(material_id)
            prev_id = item_ids[current_idx - 1] if current_idx > 0 else None
            next_id = (
                item_ids[current_idx + 1] if current_idx < len(item_ids) - 1 else None
            )
            return (prev_id, next_id)
        except ValueError:
            # Item not in filtered results
            return (None, None)
