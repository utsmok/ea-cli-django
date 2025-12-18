"""
Merge rules for Qlik and Faculty data sources.

Defines which fields each source can update and how conflicts are resolved.
"""

from .comparison import (
    ALWAYS_UPDATE,
    FILL_NULL,
    PREFER_GREATER,
    WORKFLOW_STATUS_PRIORITY,
    ComparisonStrategy,
)

# -----------------------------------------------------------------------------
# Qlik Merge Rules (System-managed fields)
# -----------------------------------------------------------------------------

QLIK_MERGE_RULES: dict[str, ComparisonStrategy] = {
    # File metadata (always update from Qlik)
    "filename": ALWAYS_UPDATE,
    "filehash": ALWAYS_UPDATE,
    "filetype": ALWAYS_UPDATE,
    "url": ALWAYS_UPDATE,
    "status": ALWAYS_UPDATE,
    # Content metadata (always update from Qlik)
    "title": ALWAYS_UPDATE,
    "author": ALWAYS_UPDATE,
    "publisher": ALWAYS_UPDATE,
    "isbn": FILL_NULL,  # Only fill if missing
    "doi": FILL_NULL,  # Only fill if missing
    # Course information (always update from Qlik)
    "period": ALWAYS_UPDATE,
    "department": ALWAYS_UPDATE,
    "course_code": ALWAYS_UPDATE,
    "course_name": ALWAYS_UPDATE,
    "canvas_course_id": ALWAYS_UPDATE,
    # Collection metadata (always update from Qlik)
    "owner": ALWAYS_UPDATE,
    "in_collection": ALWAYS_UPDATE,
    # Metrics (always take latest from Qlik)
    "count_students_registered": ALWAYS_UPDATE,
    "pagecount": PREFER_GREATER,  # Take higher count
    "wordcount": PREFER_GREATER,  # Take higher count
    "picturecount": PREFER_GREATER,  # Take higher count
    "pages_x_students": ALWAYS_UPDATE,
    "reliability": ALWAYS_UPDATE,
    # Added from user request
    "ml_classification": ALWAYS_UPDATE,
    "last_canvas_check": ALWAYS_UPDATE,
    "auditor": ALWAYS_UPDATE,
    "last_change": ALWAYS_UPDATE,
}

# Fields that Qlik can create on new items
QLIK_CREATEABLE_FIELDS = set(QLIK_MERGE_RULES.keys())


# -----------------------------------------------------------------------------
# Faculty Merge Rules (Human-managed fields)
# -----------------------------------------------------------------------------

FACULTY_MERGE_RULES: dict[str, ComparisonStrategy] = {
    # Workflow management (use priority: Done > InProgress > ToDo)
    "workflow_status": WORKFLOW_STATUS_PRIORITY,
    # Classification fields (always update from Faculty)
    "classification": ALWAYS_UPDATE,
    "manual_classification": ALWAYS_UPDATE,
    "v2_manual_classification": ALWAYS_UPDATE,
    "v2_overnamestatus": ALWAYS_UPDATE,
    "v2_lengte": ALWAYS_UPDATE,
    # Human annotations (always update from Faculty)
    "remarks": ALWAYS_UPDATE,
    "scope": ALWAYS_UPDATE,
    "manual_identifier": ALWAYS_UPDATE,
}

# Fields that Faculty can update on existing items
FACULTY_UPDATEABLE_FIELDS = set(FACULTY_MERGE_RULES.keys())


# -----------------------------------------------------------------------------
# Field Ownership Validation
# -----------------------------------------------------------------------------


def validate_qlik_update(field_name: str) -> bool:
    """
    Check if Qlik source can update this field.

    Args:
        field_name: Field to check

    Returns:
        True if Qlik can update this field, False otherwise
    """
    return field_name in QLIK_MERGE_RULES


def validate_faculty_update(field_name: str) -> bool:
    """
    Check if Faculty source can update this field.

    Args:
        field_name: Field to check

    Returns:
        True if Faculty can update this field, False otherwise
    """
    return field_name in FACULTY_MERGE_RULES


def get_qlik_strategy(field_name: str) -> ComparisonStrategy | None:
    """Get comparison strategy for Qlik field."""
    return QLIK_MERGE_RULES.get(field_name)


def get_faculty_strategy(field_name: str) -> ComparisonStrategy | None:
    """Get comparison strategy for Faculty field."""
    return FACULTY_MERGE_RULES.get(field_name)


# -----------------------------------------------------------------------------
# Cross-contamination Prevention
# -----------------------------------------------------------------------------

# Ensure no field is in both Qlik and Faculty rules (preventing conflicts)
_qlik_fields = set(QLIK_MERGE_RULES.keys())
_faculty_fields = set(FACULTY_MERGE_RULES.keys())
_overlap = _qlik_fields & _faculty_fields

if _overlap:
    raise ValueError(
        f"Field ownership conflict! These fields appear in both Qlik and Faculty rules: {_overlap}. "
        "Each field must have exactly ONE authoritative source."
    )


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def get_all_managed_fields() -> set[str]:
    """Get set of all fields managed by ingestion (Qlik + Faculty)."""
    return _qlik_fields | _faculty_fields


def is_system_field(field_name: str) -> bool:
    """Check if field is system-managed (Qlik)."""
    return field_name in _qlik_fields


def is_human_field(field_name: str) -> bool:
    """Check if field is human-managed (Faculty)."""
    return field_name in _faculty_fields


def get_field_owner(field_name: str) -> str | None:
    """
    Get the authoritative source for a field.

    Returns:
        "QLIK" if Qlik manages this field
        "FACULTY" if Faculty manages this field
        None if field is not managed by ingestion
    """
    if is_system_field(field_name):
        return "QLIK"
    if is_human_field(field_name):
        return "FACULTY"
    return None
