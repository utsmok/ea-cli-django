"""
Validation functions for staged data.

Validates that required fields exist and meet basic constraints.
"""

import polars as pl


def validate_qlik_data(df: pl.DataFrame) -> tuple[bool, list[str]]:
    """
    Validate Qlik data has required fields.

    Args:
        df: Standardized DataFrame from Qlik export

    Returns:
        (is_valid, error_messages)

    Required fields:
    - material_id (must be unique, non-null integer)
    - filename (recommended but not required)
    """
    errors = []

    # Check required columns exist
    if "material_id" not in df.columns:
        errors.append("Missing required column: material_id")
        return False, errors

    # Check material_id is not null
    null_count = df.filter(pl.col("material_id").is_null()).height
    if null_count > 0:
        errors.append(f"Found {null_count} rows with null material_id")

    # Check material_id uniqueness
    total_rows = df.height
    unique_ids = df.select(pl.col("material_id")).unique().height
    if unique_ids < total_rows:
        duplicates = total_rows - unique_ids
        errors.append(
            f"Found {duplicates} duplicate material_ids. "
            "Each row must have a unique material_id."
        )

    # Check material_id can be converted to integer
    try:
        df.select(pl.col("material_id").cast(pl.Int64, strict=False))
    except Exception as e:
        errors.append(f"material_id contains non-integer values: {e}")

    is_valid = len(errors) == 0
    return is_valid, errors


def validate_faculty_data(df: pl.DataFrame) -> tuple[bool, list[str]]:
    """
    Validate Faculty data has required fields.

    Args:
        df: Standardized DataFrame from Faculty sheet

    Returns:
        (is_valid, error_messages)

    Required fields:
    - material_id (must exist in CopyrightItem table - checked later)

    Faculty sheets ONLY update existing items, never create new ones.
    """
    errors = []

    # Check required columns exist
    if "material_id" not in df.columns:
        errors.append("Missing required column: material_id")
        return False, errors

    # Check material_id is not null
    null_count = df.filter(pl.col("material_id").is_null()).height
    if null_count > 0:
        errors.append(f"Found {null_count} rows with null material_id")

    # Check material_id can be converted to integer
    try:
        df.select(pl.col("material_id").cast(pl.Int64, strict=False))
    except Exception as e:
        errors.append(f"material_id contains non-integer values: {e}")

    # Check that at least ONE human-managed field is present
    human_fields = [
        "workflow_status",
        "classification",
        "v2_manual_classification",
        "v2_overnamestatus",
        "v2_lengte",
        "remarks",
        "scope",
        "manual_identifier",
        "manual_classification",
    ]

    present_fields = [f for f in human_fields if f in df.columns]
    if not present_fields:
        errors.append(
            f"Faculty sheet must contain at least one human-managed field: "
            f"{', '.join(human_fields)}"
        )

    is_valid = len(errors) == 0
    return is_valid, errors
