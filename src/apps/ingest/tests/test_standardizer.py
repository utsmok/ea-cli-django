"""
Tests for standardization service.

Pure function tests - no Django dependencies needed.
"""

import polars as pl

from apps.ingest.services.standardizer import (
    add_row_numbers,
    filter_required_rows,
    normalize_column_names,
    replace_null_markers,
    safe_bool,
    safe_float,
    safe_int,
    standardize_dataframe,
)


class TestColumnNormalization:
    """Test column name normalization."""

    def test_qlik_column_mapping(self):
        """Test explicit Qlik column mapping."""
        df = pl.DataFrame(
            {
                "Material ID": [1, 2, 3],
                "Filename": ["a.pdf", "b.pdf", "c.pdf"],
                "# Students registered": [10, 20, 30],
            }
        )

        result = normalize_column_names(df, "QLIK")

        assert "material_id" in result.columns
        assert "filename" in result.columns
        assert "count_students_registered" in result.columns
        assert "Material ID" not in result.columns

    def test_faculty_column_mapping(self):
        """Test explicit Faculty column mapping."""
        df = pl.DataFrame(
            {
                "Material ID": [1, 2, 3],
                "Workflow status": ["ToDo", "Done", "InProgress"],
                "Remarks": ["note 1", "note 2", "note 3"],
            }
        )

        result = normalize_column_names(df, "FACULTY")

        assert "material_id" in result.columns
        assert "workflow_status" in result.columns
        assert "remarks" in result.columns

    def test_fallback_normalization(self):
        """Test fallback normalization for unmapped columns."""
        df = pl.DataFrame(
            {
                "Some Column Name": [1, 2, 3],
                "Another Column": ["a", "b", "c"],
            }
        )

        result = normalize_column_names(df, "QLIK")

        assert "some_column_name" in result.columns
        assert "another_column" in result.columns


class TestNullMarkerReplacement:
    """Test null marker replacement."""

    def test_dash_replacement(self):
        """Test that dashes are replaced with null."""
        df = pl.DataFrame(
            {
                "col1": ["value", "-", "another"],
                "col2": ["-", "value", "-"],
            }
        )

        result = replace_null_markers(df)

        assert result["col1"][1] is None
        assert result["col2"][0] is None
        assert result["col2"][2] is None
        assert result["col1"][0] == "value"

    def test_empty_string_replacement(self):
        """Test that empty strings are replaced with null."""
        df = pl.DataFrame(
            {
                "col1": ["value", "", "  "],  # empty and whitespace
            }
        )

        result = replace_null_markers(df)

        assert result["col1"][1] is None
        assert result["col1"][2] is None


class TestRowFiltering:
    """Test row filtering logic."""

    def test_filter_null_material_ids(self):
        """Test that rows with null material_id are filtered."""
        df = pl.DataFrame(
            {
                "material_id": ["1", "2", None, "4"],
                "filename": ["a", "b", "c", "d"],
            }
        )

        result = filter_required_rows(df, "QLIK")

        assert result.height == 3
        assert result["material_id"].to_list() == ["1", "2", "4"]

    def test_qlik_filetype_filtering(self):
        """Test that Qlik data filters non-document filetypes."""
        df = pl.DataFrame(
            {
                "material_id": ["1", "2", "3", "4", "5"],
                "filetype": ["pdf", "ppt", "doc", "mp4", "xlsx"],
            }
        )

        result = filter_required_rows(df, "QLIK")

        assert result.height == 3
        filetypes = result["filetype"].to_list()
        assert "pdf" in filetypes
        assert "ppt" in filetypes
        assert "doc" in filetypes
        assert "mp4" not in filetypes

    def test_faculty_no_filetype_filtering(self):
        """Test that Faculty data doesn't filter by filetype."""
        df = pl.DataFrame(
            {
                "material_id": ["1", "2", "3"],
                "workflow_status": ["ToDo", "Done", "InProgress"],
            }
        )

        result = filter_required_rows(df, "FACULTY")

        # All rows should be kept (no filetype filtering for Faculty)
        assert result.height == 3


class TestRowNumbering:
    """Test row number addition."""

    def test_row_numbers_start_at_2(self):
        """Test that row numbers start at 2 (Excel row 2, accounting for header)."""
        df = pl.DataFrame(
            {
                "material_id": ["1", "2", "3"],
            }
        )

        result = add_row_numbers(df)

        assert "row_number" in result.columns
        assert result["row_number"].to_list() == [2, 3, 4]


class TestCompleteStandardization:
    """Test complete standardization pipeline."""

    def test_qlik_standardization(self):
        """Test complete Qlik data standardization."""
        df = pl.DataFrame(
            {
                "Material ID": ["1", "2", None, "4"],  # One null to filter
                "Filename": ["a.pdf", "b.pdf", "-", "d.pdf"],  # One null marker
                "Filetype": ["pdf", "ppt", "doc", "mp4"],  # One invalid type
                "# Students registered": [10, 20, 30, 40],
            }
        )

        result = standardize_dataframe(df, "QLIK")

        # Should have normalized columns
        assert "material_id" in result.columns
        assert "filename" in result.columns
        assert "count_students_registered" in result.columns
        assert "faculty" in result.columns

        # Should have filtered null material_id and invalid filetype
        assert result.height == 2  # Only pdf and ppt remain (not null, not mp4)

        # Should have replaced "-" with None
        assert result["filename"][0] == "a.pdf"
        assert result["filename"][1] == "b.pdf"

        # Should have mapped faculties (default UNM for unknown)
        assert result["faculty"].to_list() == ["UNM", "UNM"]

        # Should have row numbers
        assert "row_number" in result.columns

    def test_faculty_standardization(self):
        """Test complete Faculty data standardization."""
        df = pl.DataFrame(
            {
                "Material ID": ["1", "2", "3"],
                "Workflow status": ["ToDo", "-", "Done"],
                "Remarks": ["note", "", "another note"],
            }
        )

        result = standardize_dataframe(df, "FACULTY")

        # Should have normalized columns
        assert "material_id" in result.columns
        assert "workflow_status" in result.columns
        assert "remarks" in result.columns

        # Should have replaced null markers
        assert result["workflow_status"][1] is None
        assert result["remarks"][1] is None

        # Should keep all rows (no filetype filtering for Faculty)
        assert result.height == 3


class TestWorkflowAndFacultyMapping:
    """Test workflow defaulting and faculty mapping."""

    def test_workflow_status_defaulted_when_missing(self):
        df = pl.DataFrame(
            {
                "Material ID": [1, 2],
                "Department": ["Master Public Management", "Unknown"],
            }
        )

        result = standardize_dataframe(df, "QLIK")

        assert "workflow_status" in result.columns
        assert result["workflow_status"].to_list() == ["ToDo", "ToDo"]

    def test_faculty_mapping_is_case_insensitive(self):
        df = pl.DataFrame(
            {
                "Material ID": [1, 2],
                "Department": ["eemcs", "Master Public Management"],
            }
        )

        result = standardize_dataframe(df, "QLIK")

        assert result["faculty"].to_list() == ["EEMCS", "BMS"]


class TestSafeConversions:
    """Test safe type conversion utilities."""

    def test_safe_int(self):
        assert safe_int("123") == 123
        assert safe_int("123.7") == 123
        assert safe_int(456) == 456
        assert safe_int("invalid") is None
        assert safe_int(None) is None

    def test_safe_float(self):
        assert safe_float("123.45") == 123.45
        assert safe_float("123") == 123.0
        assert safe_float(456.78) == 456.78
        assert safe_float("invalid") is None
        assert safe_float(None) is None

    def test_safe_bool(self):
        assert safe_bool("true") is True
        assert safe_bool("yes") is True
        assert safe_bool("1") is True
        assert safe_bool("false") is False
        assert safe_bool("no") is False
        assert safe_bool("0") is False
        assert safe_bool(True) is True
        assert safe_bool(False) is False
        assert safe_bool("invalid") is None
        assert safe_bool(None) is None
