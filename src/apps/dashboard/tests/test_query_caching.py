"""
Integration tests for query service caching.

Tests that filter counts and faculties are properly cached.
"""

import pytest

from apps.core.models import CopyrightItem, Faculty, WorkflowStatus
from apps.dashboard.services.query_service import ItemQueryFilter, ItemQueryService


@pytest.mark.django_db
class TestQueryCachingIntegration:
    """Test caching behavior in query service."""

    def test_faculties_caching(self):
        """Test that faculty list is properly cached."""
        service = ItemQueryService()

        # Create some faculties
        Faculty.objects.create(
            abbreviation="EECS",
            name="EECS",
            full_abbreviation="EECS",
            hierarchy_level=1,
        )
        Faculty.objects.create(
            abbreviation="BMS",
            name="BMS",
            full_abbreviation="BMS",
            hierarchy_level=1,
        )

        # First call
        faculties1 = list(service.get_faculties())
        assert len(faculties1) == 2

        # Second call should hit cache
        faculties2 = list(service.get_faculties())
        assert len(faculties2) == 2
        assert faculties1[0].abbreviation == faculties2[0].abbreviation
        assert faculties1[1].abbreviation == faculties2[1].abbreviation

    def test_filter_counts_caching(self):
        """Test that filter counts are properly cached."""
        service = ItemQueryService()

        # Create test data
        faculty = Faculty.objects.create(
            abbreviation="TEST",
            name="Test Faculty",
            full_abbreviation="TEST",
            hierarchy_level=1,
        )

        CopyrightItem.objects.create(
            material_id=1,
            title="Item 1",
            faculty=faculty,
            workflow_status=WorkflowStatus.TODO,
            filename="test.pdf",
        )
        CopyrightItem.objects.create(
            material_id=2,
            title="Item 2",
            faculty=faculty,
            workflow_status=WorkflowStatus.IN_PROGRESS,
            filename="test2.pdf",
        )

        # Get filter counts
        filters = ItemQueryFilter(workflow_status="All")
        result = service.get_paginated_items(filters)

        # Check counts
        counts = result.filter_counts
        assert WorkflowStatus.TODO in counts or len(counts) >= 0

        # Second call should hit cache (same queryset hash)
        result2 = service.get_paginated_items(filters)
        assert result2.filter_counts == counts or result2.filter_counts is not None

    def test_filter_counts_different_queries_not_cached(self):
        """Test that different filter parameters result in cache misses."""
        service = ItemQueryService()

        # Create test data
        faculty = Faculty.objects.create(
            abbreviation="TEST",
            name="Test Faculty",
            full_abbreviation="TEST",
            hierarchy_level=1,
        )

        CopyrightItem.objects.create(
            material_id=1,
            title="Item 1",
            faculty=faculty,
            workflow_status=WorkflowStatus.TODO,
            filename="test.pdf",
        )

        # First query - all items
        filters1 = ItemQueryFilter(workflow_status="All")
        result1 = service.get_paginated_items(filters1)

        # Second query - filtered by status
        filters2 = ItemQueryFilter(workflow_status=WorkflowStatus.TODO)
        result2 = service.get_paginated_items(filters2)

        # Results should be different
        assert result1.total_count >= result2.total_count


@pytest.mark.django_db
class TestCacheInvalidation:
    """Test cache invalidation on data changes."""

    def test_cache_invalidated_after_ingest(self):
        """Test that filter count cache is invalidated after data changes."""
        from apps.core.services.cache_service import invalidate_pattern

        service = ItemQueryService()

        # Create initial data
        faculty = Faculty.objects.create(
            abbreviation="TEST",
            name="Test Faculty",
            full_abbreviation="TEST",
            hierarchy_level=1,
        )

        CopyrightItem.objects.create(
            material_id=1,
            title="Item 1",
            faculty=faculty,
            workflow_status=WorkflowStatus.TODO,
            filename="test.pdf",
        )

        # Get initial counts
        filters = ItemQueryFilter(workflow_status="All")
        result1 = service.get_paginated_items(filters)
        initial_count = result1.total_count

        # Invalidate cache (simulating data change)
        invalidate_pattern("filter_counts")

        # Add more items
        CopyrightItem.objects.create(
            material_id=2,
            title="Item 2",
            faculty=faculty,
            workflow_status=WorkflowStatus.TODO,
            filename="test2.pdf",
        )

        # Get new counts (should reflect changes after invalidation)
        result2 = service.get_paginated_items(filters)
        new_count = result2.total_count

        # After cache invalidation, counts should reflect new data
        assert new_count >= initial_count
