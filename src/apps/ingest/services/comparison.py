"""
Field comparison strategies for merge operations.

Defines how to compare old and new values to decide which to keep.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol


class ComparisonStrategy(Protocol):
    """Protocol for field comparison strategies."""

    def should_update(self, old_value: Any, new_value: Any) -> bool:
        """
        Determine if field should be updated.

        Args:
            old_value: Current value in database
            new_value: New value from source

        Returns:
            True if should update to new_value, False to keep old_value
        """
        ...


class AlwaysUpdateStrategy:
    """Always take the new value (unconditional overwrite)."""

    def should_update(self, old_value: Any, new_value: Any) -> bool:
        # Always update if new value is not None
        if new_value is None:
            return False  # Don't overwrite with None
        return True


class NeverUpdateStrategy:
    """Never overwrite (preserve existing value)."""

    def should_update(self, old_value: Any, new_value: Any) -> bool:
        # Never update (keep old value)
        return False


class FillNullStrategy:
    """Only update if current value is None/empty."""

    def should_update(self, old_value: Any, new_value: Any) -> bool:
        # Only fill if old is None or empty string
        if new_value is None:
            return False  # Don't fill with None
        if old_value is None:
            return True
        if isinstance(old_value, str) and old_value.strip() == "":
            return True
        return False


class PreferNonNullStrategy:
    """Update only if new value is non-null and old is null."""

    def should_update(self, old_value: Any, new_value: Any) -> bool:
        # Same as FillNullStrategy
        return FillNullStrategy().should_update(old_value, new_value)


class PreferGreaterStrategy:
    """Take whichever value is numerically greater."""

    def should_update(self, old_value: Any, new_value: Any) -> bool:
        # Update if new value is greater
        if new_value is None:
            return False
        if old_value is None:
            return True

        try:
            # Try numeric comparison
            old_num = (
                float(old_value)
                if not isinstance(old_value, (int, float, Decimal))
                else float(old_value)
            )
            new_num = (
                float(new_value)
                if not isinstance(new_value, (int, float, Decimal))
                else float(new_value)
            )
            return new_num > old_num
        except (ValueError, TypeError):
            # If not numeric, fallback to always update
            return True


class PreferNewerDateStrategy:
    """Take whichever date is more recent."""

    def should_update(self, old_value: Any, new_value: Any) -> bool:
        if new_value is None:
            return False
        if old_value is None:
            return True

        try:
            # Normalize to date objects
            if isinstance(old_value, str):
                old_date = datetime.fromisoformat(old_value).date()
            elif isinstance(old_value, datetime):
                old_date = old_value.date()
            elif isinstance(old_value, date):
                old_date = old_value
            else:
                return True  # Can't parse old, take new

            if isinstance(new_value, str):
                new_date = datetime.fromisoformat(new_value).date()
            elif isinstance(new_value, datetime):
                new_date = new_value.date()
            elif isinstance(new_value, date):
                new_date = new_value
            else:
                return False  # Can't parse new, keep old

            return new_date > old_date
        except (ValueError, TypeError):
            # If comparison fails, prefer new value
            return True


class PriorityListStrategy:
    """
    Choose value based on ranked priority list.

    Used for workflow_status where we have explicit ranking:
    Done > InProgress > ToDo
    """

    def __init__(self, priority_list: list[str]):
        """
        Args:
            priority_list: List of values in order of priority (highest first)
        """
        self.priority_list = priority_list

    def should_update(self, old_value: Any, new_value: Any) -> bool:
        if new_value is None:
            return False
        if old_value is None:
            return True

        # Normalize to strings
        old_str = str(old_value).strip()
        new_str = str(new_value).strip()

        # Get priority ranks (lower index = higher priority)
        try:
            old_rank = self.priority_list.index(old_str)
        except ValueError:
            old_rank = len(self.priority_list)  # Unknown = lowest priority

        try:
            new_rank = self.priority_list.index(new_str)
        except ValueError:
            new_rank = len(self.priority_list)  # Unknown = lowest priority

        # Update if new has higher priority (lower rank)
        return new_rank < old_rank


# Predefined strategies
ALWAYS_UPDATE = AlwaysUpdateStrategy()
NEVER_UPDATE = NeverUpdateStrategy()
FILL_NULL = FillNullStrategy()
PREFER_GREATER = PreferGreaterStrategy()
PREFER_NEWER_DATE = PreferNewerDateStrategy()

# Workflow status priority (Done > InProgress > ToDo)
WORKFLOW_STATUS_PRIORITY = PriorityListStrategy(["Done", "InProgress", "ToDo"])
