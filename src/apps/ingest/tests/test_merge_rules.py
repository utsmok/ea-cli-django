"""
Tests for field comparison and merge rules.
"""

from apps.ingest.services.comparison import (
    AlwaysUpdateStrategy,
    FillNullStrategy,
    PreferGreaterStrategy,
    PriorityListStrategy,
)
from apps.ingest.services.merge_rules import (
    FACULTY_MERGE_RULES,
    QLIK_MERGE_RULES,
    get_field_owner,
    is_human_field,
    is_system_field,
)


class TestComparisonStrategies:
    """Test individual comparison strategies."""

    def test_always_update_strategy(self):
        """AlwaysUpdateStrategy should always prefer new value."""
        strategy = AlwaysUpdateStrategy()

        assert strategy.should_update("old", "new") is True
        assert strategy.should_update(10, 20) is True
        assert (
            strategy.should_update("something", None) is False
        )  # Don't update to None
        assert strategy.should_update(None, "new") is True

    def test_fill_null_strategy(self):
        """FillNullStrategy should only update if old is None/empty."""
        strategy = FillNullStrategy()

        assert strategy.should_update(None, "new") is True
        assert strategy.should_update("", "new") is True
        assert strategy.should_update("  ", "new") is True
        assert strategy.should_update("existing", "new") is False
        assert strategy.should_update("existing", None) is False

    def test_prefer_greater_strategy(self):
        """PreferGreaterStrategy should take numerically greater value."""
        strategy = PreferGreaterStrategy()

        assert strategy.should_update(10, 20) is True
        assert strategy.should_update(20, 10) is False
        assert strategy.should_update(None, 5) is True
        assert strategy.should_update(5, None) is False
        assert strategy.should_update("10", "20") is True  # String to number conversion

    def test_priority_list_strategy(self):
        """PriorityListStrategy should respect priority ordering."""
        strategy = PriorityListStrategy(["Done", "InProgress", "ToDo"])

        # Done > InProgress
        assert strategy.should_update("InProgress", "Done") is True
        assert strategy.should_update("Done", "InProgress") is False

        # InProgress > ToDo
        assert strategy.should_update("ToDo", "InProgress") is True
        assert strategy.should_update("InProgress", "ToDo") is False

        # Done > ToDo
        assert strategy.should_update("ToDo", "Done") is True
        assert strategy.should_update("Done", "ToDo") is False


class TestMergeRules:
    """Test merge rule definitions."""

    def test_no_field_overlap(self):
        """Qlik and Faculty rules should not overlap."""
        qlik_fields = set(QLIK_MERGE_RULES.keys())
        faculty_fields = set(FACULTY_MERGE_RULES.keys())

        overlap = qlik_fields & faculty_fields
        assert len(overlap) == 0, f"Field ownership conflict: {overlap}"

    def test_qlik_owns_system_fields(self):
        """Qlik should own all system-managed fields."""
        system_fields = [
            "filename",
            "filehash",
            "filetype",
            "url",
            "status",
            "title",
            "author",
            "count_students_registered",
        ]

        for field in system_fields:
            assert field in QLIK_MERGE_RULES
            assert get_field_owner(field) == "QLIK"
            assert is_system_field(field) is True
            assert is_human_field(field) is False

    def test_faculty_owns_human_fields(self):
        """Faculty should own all human-managed fields."""
        human_fields = [
            "workflow_status",
            "classification",
            "v2_manual_classification",
            "remarks",
            "scope",
        ]

        for field in human_fields:
            assert field in FACULTY_MERGE_RULES
            assert get_field_owner(field) == "FACULTY"
            assert is_human_field(field) is True
            assert is_system_field(field) is False

    def test_unmanaged_field(self):
        """Fields not in either ruleset should return None."""
        assert get_field_owner("nonexistent_field") is None
        assert is_system_field("nonexistent_field") is False
        assert is_human_field("nonexistent_field") is False
