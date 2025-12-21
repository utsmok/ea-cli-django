import logging
from datetime import date, datetime
from typing import Any

from apps.core.models import (
    Infringement,
    WorkflowStatus,
)

logger = logging.getLogger(__name__)

# --- Configuration ---

# Priorities lists (lower index = higher priority)
# Ported from legacy merge_rules.py

WORKFLOW_STATUS_PRIORITY = [
    WorkflowStatus.DONE,
    WorkflowStatus.IN_PROGRESS,
    WorkflowStatus.TODO,
]

INFRINGMENT_PRIORITY = [
    Infringement.YES,
    Infringement.NO,
    Infringement.UNDETERMINED,
]

FILE_EXISTS_PRIORITY = [
    False,
    0,
    True,
    1,
]  # False/0 overrides True/1 (pessimistic) -> wait, legacy said [False, 0, True, 1].
# Legacy FileExistsStrategy said "always update".
# But `added_fields` had priorities.
# Legacy Strategy for file_exists:
# "file_exists value received, always update"
# So priority list in legacy might have been unused for file_exists?
# I'll stick to "Always Update" for file_exists if new value is not None.

# Field groupings
ADDED_FIELDS = {
    "workflow_status": WORKFLOW_STATUS_PRIORITY,
    "retrieved_from_copyright_on": None,
    "possible_fine": None,
    "infringement": INFRINGMENT_PRIORITY,
    "file_exists": None,  # Special handling
}

CHANGEABLE_FIELDS = {
    "manual_classification": None,  # We might want to add priority if needed, legacy had None/List depending on settings
    "v2_manual_classification": None,
    "manual_identifier": None,
    "remarks": None,
    "scope": None,
    # Add others as needed
}


def get_mergeable_fields() -> dict:
    return {**ADDED_FIELDS, **CHANGEABLE_FIELDS}


# --- Strategies ---


class FieldComparisonStrategy:
    def should_update(
        self, new_value: Any, old_value: Any, ordering: list | None
    ) -> tuple[bool, str]:
        raise NotImplementedError


class RankedFieldStrategy(FieldComparisonStrategy):
    """Strategy for ranked fields (lower index = higher priority)."""

    def should_update(
        self, new_value: Any, old_value: Any, ordering: list | None
    ) -> tuple[bool, str]:
        if not ordering:
            return False, ""

        # Helper to find rank
        def get_rank(val, rules):
            # Try direct match
            if val in rules:
                return rules.index(val)
            # Try string match (for enums)
            val_str = str(val)
            str_rules = [str(r) for r in rules]
            if val_str in str_rules:
                return str_rules.index(val_str)
            return 999

        new_rank = get_rank(new_value, ordering)
        old_rank = get_rank(old_value, ordering)

        if new_rank < old_rank:
            return True, "new rank < old rank"
        return False, ""


class DateFieldStrategy(FieldComparisonStrategy):
    """Newer dates take precedence."""

    def should_update(
        self, new_value: Any, old_value: Any, ordering: Any
    ) -> tuple[bool, str]:
        if not (
            isinstance(new_value, date | datetime)
            and isinstance(old_value, date | datetime)
        ):
            return False, ""
        if new_value > old_value:
            return True, "new date > old date"
        return False, ""


class NumericFieldStrategy(FieldComparisonStrategy):
    """Larger numbers take precedence? Or just diff? Legacy said safe_compare_greater."""

    def should_update(
        self, new_value: Any, old_value: Any, ordering: Any
    ) -> tuple[bool, str]:
        try:
            val_new = float(new_value)
            val_old = float(old_value)
            if val_new > val_old:
                return True, "new > old"
        except (ValueError, TypeError):
            pass
        return False, ""


class StringFieldStrategy(FieldComparisonStrategy):
    """Longer strings take precedence."""

    def should_update(
        self, new_value: Any, old_value: Any, ordering: Any
    ) -> tuple[bool, str]:
        if not (isinstance(new_value, str) and isinstance(old_value, str)):
            return False, ""
        if len(new_value.strip()) > len(old_value.strip()):
            return True, "new len > old len"
        return False, ""


class AlwaysUpdateStrategy(FieldComparisonStrategy):
    def should_update(
        self, new_value: Any, old_value: Any, ordering: Any
    ) -> tuple[bool, str]:
        return True, "always update"


def get_strategy_for_field(
    field_name: str, ordering: list | None = None
) -> FieldComparisonStrategy:
    if field_name == "file_exists":
        return AlwaysUpdateStrategy()

    if ordering:
        return RankedFieldStrategy()

    # Default inferences
    if field_name in ["retrieved_from_copyright_on", "last_change"]:
        return DateFieldStrategy()

    return StringFieldStrategy()  # Default conservative? Or Numeric?
    # Legacy default was NumericFieldStrategy.
    # But usually text fields (remarks) use StringStrategy logic in legacy (checked explicitly for str).

    # I'll stick to legacy default Numeric behavior (greater > smaller) for numbers,
    # but I need to know the type.
    # Since we don't have the instance here, we might just default to AlwaysUpdate if not prioritized?
    # No, legacy default is conservative.

    # Let's use a Hybrid or just return Numeric for now, and handle String in Orchestrator?
    # Actually, legacy `get_comparison_strategy` checks the DB item type.
    # I'll implement `get_comparison_strategy` that accepts the old value to inspect type.
    return NumericFieldStrategy()


def determine_strategy_by_value(
    field_name: str, old_value: Any, ordering: list | None
) -> FieldComparisonStrategy:
    if field_name == "file_exists":
        return AlwaysUpdateStrategy()

    if ordering:
        return RankedFieldStrategy()

    if isinstance(old_value, date | datetime):
        return DateFieldStrategy()
    if isinstance(old_value, str):
        return StringFieldStrategy()
    if isinstance(old_value, int | float):
        return NumericFieldStrategy()

    return NumericFieldStrategy()  # Fallback
