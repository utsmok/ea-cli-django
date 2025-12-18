"""
Data standardization service for ingestion pipeline.

Pure functions for transforming raw Excel data into standardized format.
No I/O, no Django dependencies - only Polars DataFrame transformations.
"""

from typing import Any

import polars as pl

from config.university import DEPARTMENT_MAPPING_LOWER

FACULTY_ABBREVIATIONS_LOWER = {
    abbr.lower(): abbr for abbr in set(DEPARTMENT_MAPPING_LOWER.values())
}

# Column name normalization mapping
# Maps raw column names from Qlik/Faculty sheets to standardized names
QLIK_COLUMN_MAPPING = {
    "Material ID": "material_id",
    "Filename": "filename",
    "Filehash": "filehash",
    "Filetype": "filetype",
    "URL": "url",
    "Status": "status",
    "Title": "title",
    "Author": "author",
    "Publisher": "publisher",
    "Period": "period",
    "Department": "department",
    "Course code": "course_code",
    "Course name": "course_name",
    "ISBN": "isbn",
    "DOI": "doi",
    "Owner": "owner",
    "In collection": "in_collection",
    "Picturecount": "picturecount",
    "Reliability": "reliability",
    "Pages x students": "pages_x_students",
    "# Students registered": "count_students_registered",
    "Pagecount": "pagecount",
    "Wordcount": "wordcount",
    "Canvas course ID": "canvas_course_id",
    "Infringement": "infringement",
    "Possible fine": "possible_fine",
    # Added from user request
    "ML Prediction": "ml_classification",
    "Last canvas check": "last_canvas_check",
    "Manual classification": "manual_classification",
    "Remarks": "remarks",
    "Scope": "scope",
    "Auditor": "auditor",
    "Last change": "last_change",
}

FACULTY_COLUMN_MAPPING = {
    "Material ID": "material_id",
    "Workflow status": "workflow_status",
    "Classification": "classification",
    "Manual classification v2": "v2_manual_classification",
    "Overname status": "v2_overnamestatus",
    "Lengte": "v2_lengte",
    "Remarks": "remarks",
    "Scope": "scope",
    "Manual identifier": "manual_identifier",
    "Manual classification": "manual_classification",
}


def normalize_column_names(df: pl.DataFrame, source_type: str) -> pl.DataFrame:
    """
    Normalize column names to standard format.

    Args:
        df: Raw DataFrame from Excel
        source_type: "QLIK" or "FACULTY"

    Returns:
        DataFrame with normalized column names
    """
    mapping = QLIK_COLUMN_MAPPING if source_type == "QLIK" else FACULTY_COLUMN_MAPPING

    # First pass: use explicit mapping
    renames = {}
    for old_name in df.columns:
        if old_name in mapping:
            renames[old_name] = mapping[old_name]
        else:
            # Fallback: normalize by rules (lowercase, replace spaces/special chars)
            new_name = (
                old_name.replace(" ", "_")
                .replace("#", "count_")
                .replace("*", "x")
                .replace("%", "pct")
                .lower()
            )
            renames[old_name] = new_name

    return df.rename(renames)


def replace_null_markers(df: pl.DataFrame) -> pl.DataFrame:
    """
    Replace null markers with actual nulls.

    Common null markers: "-", "", whitespace
    """
    return df.with_columns(
        pl.when(
            (pl.col(pl.String) == "-") | (pl.col(pl.String).str.strip_chars() == "")
        )
        .then(None)
        .otherwise(pl.col(pl.String))
        .name.keep()
    )


def ensure_workflow_status(df: pl.DataFrame) -> pl.DataFrame:
    """
    Ensure workflow_status exists and has a default of "ToDo" when missing/blank.

    Mirrors legacy behavior where missing workflow_status was initialized to ToDo
    to keep downstream exports and dashboard buckets consistent.
    """

    if "workflow_status" not in df.columns:
        return df.with_columns(pl.lit("ToDo").alias("workflow_status"))

    workflow_col = pl.col("workflow_status")
    needs_default_expr = workflow_col.is_null().all() | (
        workflow_col.str.strip_chars().eq("").all()
    )

    needs_default = bool(df.select(needs_default_expr).to_series(0).item())

    if needs_default:
        return df.with_columns(pl.lit("ToDo").alias("workflow_status"))

    return df


def map_faculty(df: pl.DataFrame) -> pl.DataFrame:
    """
    Map department/programme values to faculty abbreviations.

    Uses DEPARTMENT_MAPPING from config/university (case-insensitive) and falls back
    to "UNM" when no mapping is found. Adds/overwrites a `faculty` column.
    """

    def _lookup_faculty(value: str | None) -> str:
        if value is None:
            return "UNM"
        normalized = value.strip().lower()
        if normalized == "":
            return "UNM"
        return DEPARTMENT_MAPPING_LOWER.get(
            normalized, FACULTY_ABBREVIATIONS_LOWER.get(normalized, "UNM")
        )

    if "department" not in df.columns:
        return df.with_columns(pl.lit("UNM").alias("faculty"))

    return df.with_columns(
        pl.col("department")
        .map_elements(_lookup_faculty, return_dtype=pl.String)
        .alias("faculty")
    )


def cast_to_string(df: pl.DataFrame) -> pl.DataFrame:
    """
    Cast all non-string columns to string for initial staging.

    Actual type conversions happen during processing, not standardization.
    """
    return df.with_columns(pl.exclude(pl.String).cast(str))


def filter_required_rows(df: pl.DataFrame, source_type: str) -> pl.DataFrame:
    """
    Filter out rows that should not be processed.

    Rules:
    - Always: Drop rows with null material_id
    - Qlik only: Keep only pdf, ppt, doc filetypes (or null/empty)
    """
    # Filter null material_ids
    df = df.filter(pl.col("material_id").is_not_null())

    # Qlik-specific filtering
    if source_type == "QLIK" and "filetype" in df.columns:
        df = df.filter(
            (pl.col("filetype").is_in(["pdf", "ppt", "doc", "-"]))
            | (pl.col("filetype").is_null())
        )

    return df


def add_row_numbers(df: pl.DataFrame) -> pl.DataFrame:
    """
    Add row_number column for error reporting.

    Row numbers are 1-indexed to match Excel.
    """
    return df.with_row_index(
        name="row_number", offset=2
    )  # +1 for 1-indexing, +1 for header row


def standardize_dataframe(df: pl.DataFrame, source_type: str) -> pl.DataFrame:
    """
    Complete standardization pipeline.

    Steps:
    1. Normalize column names
    2. Cast all to string
    3. Replace null markers
    4. Filter invalid rows
    5. Add row numbers

    Args:
        df: Raw DataFrame from Excel
        source_type: "QLIK" or "FACULTY"

    Returns:
        Standardized DataFrame ready for staging

    Example:
        >>> raw_df = pl.read_excel("qlik_export.xlsx")
        >>> standardized = standardize_dataframe(raw_df, "QLIK")
    """
    df = normalize_column_names(df, source_type)
    df = cast_to_string(df)
    df = replace_null_markers(df)
    df = ensure_workflow_status(df)
    df = filter_required_rows(df, source_type)
    df = map_faculty(df)
    df = add_row_numbers(df)

    return df


# Safe type conversion utilities (for use in processor service)


def safe_int(value: Any) -> int | None:
    """Safely convert value to int, return None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None


def safe_float(value: Any) -> float | None:
    """Safely convert value to float, return None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_bool(value: Any) -> bool | None:
    """Safely convert value to bool, return None on failure."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        value_lower = value.lower().strip()
        if value_lower in ("true", "yes", "1", "y"):
            return True
        if value_lower in ("false", "no", "0", "n"):
            return False
    try:
        return bool(int(value))
    except (ValueError, TypeError):
        return None


def safe_datetime(value: Any) -> Any | None:
    """
    Safely convert string value to datetime, trying multiple formats.
    Returns None on failure.
    """
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value

    from dateutil import parser

    try:
        # Use dateutil.parser for robust parsing of various formats
        return parser.parse(value)
    except (ValueError, TypeError):
        return None
