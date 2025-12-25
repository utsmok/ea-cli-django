"""
Query Service: Builds, filters, and optimizes CopyrightItem queries.

Responsibilities:
- Base queryset with select_related/prefetch_related
- Dynamic filtering by workflow status, faculty, search
- Pagination logic
- Filter counts for tab badges

This service is completely testable without Django views.
"""

from __future__ import annotations

from typing import Literal

from django.core.paginator import Paginator
from django.db.models import Q, QuerySet, Count
from django.utils.functional import cached_property

from apps.core.models import (
    CopyrightItem,
    Faculty,
    WorkflowStatus,
    ClassificationV2,
    OvernameStatus,
    Lengte,
)


class ItemQueryFilter:
    """
    Encapsulates filter parameters for CopyrightItem queries.

    This provides a clean interface for views and makes testing easier.
    """

    def __init__(
        self,
        workflow_status: str | None = None,
        faculty_abbreviation: str | None = None,
        search_query: str | None = None,
        page: int = 1,
        per_page: Literal[25, 50, 100] = 50,
        sort_field: str | None = None,
        sort_direction: Literal["asc", "desc"] = "desc",
    ):
        self.workflow_status = workflow_status
        self.faculty_abbreviation = faculty_abbreviation
        self.search_query = search_query
        self.page = page
        self.per_page = per_page
        self.sort_field = sort_field
        self.sort_direction = sort_direction


class PaginatedResult:
    """
    Value object for paginated query results.

    This makes the service interface explicit and testable.
    """

    def __init__(
        self,
        items: list[CopyrightItem],
        page_obj,
        total_count: int,
        filter_counts: dict[str, int],
    ):
        self.items = items
        self.page_obj = page_obj
        self.total_count = total_count
        self.filter_counts = filter_counts


class ItemQueryService:
    """
    Service for querying and paginating CopyrightItems.

    Usage:
        service = ItemQueryService()
        result = service.get_paginated_items(filter_params)
        # Returns: PaginatedResult with items, page_obj, counts
    """

    def __init__(self):
        # Base optimization - always select related objects to avoid N+1
        self.base_qs = CopyrightItem.objects.select_related(
            "faculty",
            "document",
        )

    def get_filtered_queryset(self, filters: ItemQueryFilter) -> QuerySet[CopyrightItem]:
        """
        Apply filters to base queryset.

        This method can be tested independently by constructing
        ItemQueryFilter objects with different parameters.
        """
        qs = self.base_qs.all()

        # Workflow status filtering (default to Inbox if not specified)
        if filters.workflow_status and filters.workflow_status != "All":
            qs = qs.filter(workflow_status=filters.workflow_status)

        # Faculty filtering
        if filters.faculty_abbreviation:
            qs = qs.filter(faculty__abbreviation=filters.faculty_abbreviation)

        # Full-text search across multiple fields
        if filters.search_query:
            search_term = filters.search_query.strip()
            if search_term:
                qs = qs.filter(
                    Q(title__icontains=search_term)
                    | Q(filename__icontains=search_term)
                    | Q(course_code__icontains=search_term)
                    | Q(department__icontains=search_term)
                    | Q(remarks__icontains=search_term)
                )

        # Sorting (extensible for future column sorting)
        if filters.sort_field:
            sort_prefix = "-" if filters.sort_direction == "desc" else ""
            qs = qs.order_by(f"{sort_prefix}{filters.sort_field}")
        else:
            # Default ordering - most recently modified first
            qs = qs.order_by("-modified_at", "-material_id")

        return qs

    def get_paginated_items(self, filters: ItemQueryFilter) -> PaginatedResult:
        """
        Get paginated items with metadata.

        Returns a PaginatedResult object containing:
        - items: Current page items
        - page_obj: Django paginator page object
        - total_count: Total matching items
        - filter_counts: Breakdown by workflow status
        """
        qs = self.get_filtered_queryset(filters)

        paginator = Paginator(qs, filters.per_page)
        page_obj = paginator.get_page(filters.page)

        return PaginatedResult(
            items=page_obj,
            page_obj=page_obj,
            total_count=paginator.count,
            filter_counts=self._get_filter_counts(qs),
        )

    def get_faculties(self) -> QuerySet[Faculty]:
        """
        Get all faculties for filter dropdown.
        Ordered by abbreviation for consistent UI.
        """
        return Faculty.objects.all().order_by("abbreviation")

    def get_workflow_choices(self) -> list[tuple[str, str]]:
        """Get workflow status choices for tabs/dropdowns."""
        return WorkflowStatus.choices

    def get_classification_choices(self) -> list[tuple[str, str]]:
        """Get classification choices for dropdowns."""
        return ClassificationV2.choices

    def get_overnamestatus_choices(self) -> list[tuple[str, str]]:
        """Get overnamestatus choices for dropdowns."""
        return OvernameStatus.choices

    def get_lengte_choices(self) -> list[tuple[str, str]]:
        """Get lengte choices for dropdowns."""
        return Lengte.choices

    def _get_filter_counts(self, base_qs: QuerySet) -> dict[str, int]:
        """
        Get count of items per workflow status for tab badges.

        This is a single optimized query using aggregation,
        avoiding N+1 queries for tab counts.
        """
        counts = (
            base_qs.values("workflow_status")
            .annotate(count=Count("material_id"))
            .values_list("workflow_status", "count")
        )

        return {status: count for status, count in counts}
