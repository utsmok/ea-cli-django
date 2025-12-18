"""
Export column configuration.

Defines which columns appear in exports and how they're formatted.
Based on legacy settings.yaml data_settings.
"""
from dataclasses import dataclass

from . import export_config

@dataclass
class ColumnConfig:
    """Configuration for a single column in the export."""

    name: str  # Column name in database/DataFrame
    new_name: str | None = None  # Display name in export (if different)
    is_editable: bool = False  # Whether faculty can edit this field
    is_url: bool = False  # Whether to format as hyperlink
    is_new: bool = False # Whether the column is new
    dropdown_options: str | None = None  # Dropdown validation options
    default_val: str | None = None  # Default value for new rows


# Data entry columns (editable subset shown to faculty)
DATA_ENTRY_COLUMNS = [
    ColumnConfig(name="material_id"),
    ColumnConfig(name="period"),
    ColumnConfig(name="url", is_url=True),
    ColumnConfig(name="file_exists"),
    ColumnConfig(name="last_canvas_check", new_name="latest_filecheck_date"),
    ColumnConfig(
        name="workflow_status",
        is_new=True,
        is_editable=True,
        dropdown_options='"ToDo,Done,InProgress"',
        default_val="ToDo",
    ),
    ColumnConfig(
        name="manual_classification",
        new_name="v1_manual_classification",
        is_editable=True,
        dropdown_options='"open access,eigen materiaal - powerpoint,eigen materiaal - overig,lange overname,eigen materiaal - titelindicatie,anders,korte overname,middellange overname,onbekend"',
    ),
    ColumnConfig(
        name="v2_manual_classification",
        is_editable=True,
        dropdown_options='"OA,EM,Cit,OV,Unk"',  # ClassificationV2 enum values
    ),
    ColumnConfig(
        name="v2_overnamestatus",
        is_editable=True,
        dropdown_options='"Yes,No,Unclear"',  # OvernameStatus enum values
    ),
    ColumnConfig(
        name="v2_lengte",
        is_editable=True,
        dropdown_options='"Kort,Midden,Lang"',  # Lengte enum values
    ),
    ColumnConfig(name="remarks", is_editable=True),
    ColumnConfig(name="ml_prediction"),
    ColumnConfig(name="filename", new_name="pdf_filename"),
    ColumnConfig(name="title", new_name="pdf_title"),
    ColumnConfig(name="owner", new_name="uploaded_by"),
    ColumnConfig(name="author", new_name="detected_pdf_author"),
    ColumnConfig(name="course_link", new_name="view_in_canvas", is_url=True),
    ColumnConfig(name="course_name", new_name="course_name_canvas"),
    ColumnConfig(name="department", new_name="programme_canvas"),
]


# Complete data columns (all fields, read-only)
# This includes everything from the raw data plus enrichment
COMPLETE_DATA_COLUMN_ORDER = [
    "material_id",
    "period",
    "department",
    "course_code",
    "course_name",
    "url",
    "course_link",
    "file_exists",
    "last_canvas_check",
    "filename",
    "title",
    "owner",
    "filetype",
    "classification",
    "type",
    "ml_prediction",
    "manual_classification",
    "manual_identifier",
    "scope",
    "remarks",
    "v2_manual_classification",
    "v2_overnamestatus",
    "v2_lengte",
    "auditor",
    "last_change",
    "status",
    "google_search_file",
    "isbn",
    "doi",
    "in_collection",
    "pagecount",
    "wordcount",
    "picturecount",
    "author",
    "publisher",
    "reliability",
    "pages_x_students",
    "count_students_registered",
    "retrieved_from_copyright_on",
    "workflow_status",
    "faculty",
    "course_contacts_faculties",
    "course_contacts_names",
    "course_contacts_emails",
    "course_contacts_organizations",
    "course_names",
    "cursuscodes",
    "osiris_catalogue_url",
    "programmes",
    "filehash",
    "last_scan_date_university",
    "last_scan_date_course",
]


def get_display_name(col: ColumnConfig) -> str:
    """Get the display name for a column (uses new_name if available)."""
    return col.new_name if col.new_name else col.name


def get_editable_columns() -> list[str]:
    """Get list of editable column names."""
    return [col.name for col in DATA_ENTRY_COLUMNS if col.is_editable]


def get_column_by_name(name: str) -> ColumnConfig | None:
    """Find column config by name."""
    for col in DATA_ENTRY_COLUMNS:
        if col.name == name:
            return col
    return None
