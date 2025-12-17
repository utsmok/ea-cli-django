"""
Data standardization and processing services for ingestion pipeline.

Pure functions for transforming raw Excel data into standardized format.
No I/O, no Django dependencies - only DataFrame transformations.
"""

from .comparison import (
    ALWAYS_UPDATE,
    FILL_NULL,
    PREFER_GREATER,
    WORKFLOW_STATUS_PRIORITY,
)
from .excel_builder import ExcelBuilder
from .merge_rules import (
    FACULTY_MERGE_RULES,
    QLIK_MERGE_RULES,
    get_faculty_strategy,
    get_field_owner,
    get_qlik_strategy,
    is_human_field,
    is_system_field,
)
from .processor import BatchProcessor
from .standardizer import (
    normalize_column_names,
    safe_bool,
    safe_float,
    safe_int,
    standardize_dataframe,
)
from .validators import validate_faculty_data, validate_qlik_data

__all__ = [
    # Standardization
    "standardize_dataframe",
    "normalize_column_names",
    "validate_qlik_data",
    "validate_faculty_data",
    "safe_int",
    "safe_float",
    "safe_bool",
    "ExcelBuilder",
    # Comparison strategies
    "ALWAYS_UPDATE",
    "FILL_NULL",
    "PREFER_GREATER",
    "WORKFLOW_STATUS_PRIORITY",
    # Merge rules
    "QLIK_MERGE_RULES",
    "FACULTY_MERGE_RULES",
    "get_qlik_strategy",
    "get_faculty_strategy",
    "is_system_field",
    "is_human_field",
    "get_field_owner",
    # Processing
    "BatchProcessor",
]
