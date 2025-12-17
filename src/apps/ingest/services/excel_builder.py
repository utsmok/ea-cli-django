"""
Excel export service for backward compatibility.

Generates faculty-oriented Excel workbooks that mirror the legacy data-entry
layout closely enough for Phase A parity:
- Per-faculty sheets with locked system columns and editable human columns
- Basic data validation for enums (workflow_status, classification v2, lengte, overnamestatus)
- Overview sheet with totals per faculty
- In-memory BytesIO result suitable for HTTP responses
"""

from __future__ import annotations

from io import BytesIO
from typing import Iterable, Optional

import polars as pl
from loguru import logger
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from apps.core.models import (
    ClassificationV2,
    CopyrightItem,
    Lengte,
    OvernameStatus,
    WorkflowStatus,
)


class ExcelBuilder:
    """
    Build Excel workbooks for faculty data-entry/export.

    This is a lightweight, Django-friendly port of the legacy export routines.
    It intentionally focuses on matching column order and editability while
    keeping formatting minimal but functional.
    """

    # Legacy sheet names (match what our ingestion expects, and the ea-cli tool uses)
    COMPLETE_SHEET_NAME = "Complete data"
    DATA_ENTRY_SHEET_NAME = "Data entry"

    FACULTY_SHEET_COLUMNS: list[str] = [
        "material_id",
        "title",
        "author",
        "publisher",
        "filename",
        "url",
        "department",
        "faculty",
        "workflow_status",
        "v2_manual_classification",
        "v2_lengte",
        "v2_overnamestatus",
        "remarks",
        "scope",
        "manual_identifier",
        "manual_classification",
        "count_students_registered",
        "pagecount",
        "wordcount",
        "pages_x_students",
        "infringement",
        "possible_fine",
        "status",
    ]

    EDITABLE_COLUMNS = {
        "workflow_status",
        "v2_manual_classification",
        "v2_lengte",
        "v2_overnamestatus",
        "remarks",
        "scope",
        "manual_identifier",
        "manual_classification",
    }

    # Columns shown on the Data entry sheet (subset, with dropdowns etc.)
    # Include a couple of read-only reference fields for usability.
    DATA_ENTRY_COLUMNS: list[str] = [
        "material_id",
        "title",
        "workflow_status",
        "v2_manual_classification",
        "v2_lengte",
        "v2_overnamestatus",
        "remarks",
        "scope",
        "manual_identifier",
        "manual_classification",
    ]

    def __init__(self, faculty_code: Optional[str] = None):
        self.faculty_code = faculty_code

    def build(self) -> BytesIO:
        logger.info(f"Building Excel export for faculty: {self.faculty_code or 'ALL'}")
        df = self._fetch_data()

        if df.is_empty():
            logger.warning("No data available for export")
            return self._create_empty_workbook()

        wb = Workbook()
        wb.remove(wb.active)

        faculties = sorted(df.get_column("faculty").unique().drop_nulls().to_list())
        if self.faculty_code and self.faculty_code not in faculties:
            faculties.append(self.faculty_code)

        for faculty in faculties:
            faculty_df = df.filter(pl.col("faculty") == faculty)
            if faculty_df.is_empty():
                continue
            # For the dashboard "download all" endpoint we create one sheet per faculty
            # (this is not the workflow exporter; that's handled by the filesystem exporter).
            self._create_faculty_overview_sheet(wb, faculty, faculty_df)

        self._create_overview_sheet(wb, df)

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    # ------------------------------------------------------------------
    # Data Fetching & Preparation
    # ------------------------------------------------------------------

    def _fetch_data(self) -> pl.DataFrame:
        qs = CopyrightItem.objects.all()
        if self.faculty_code:
            qs = qs.filter(faculty__abbreviation=self.faculty_code)

        values = list(
            qs.values(
                *[col for col in self.FACULTY_SHEET_COLUMNS if col != "faculty"],
                "faculty__abbreviation",
            )
        )
        if not values:
            return pl.DataFrame()

        df = pl.DataFrame(values)
        if "faculty__abbreviation" in df.columns:
            df = df.rename({"faculty__abbreviation": "faculty"})

        # Ensure all required columns exist
        for col in self.FACULTY_SHEET_COLUMNS:
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).alias(col))

        # Normalize enums to display values
        df = df.with_columns(
            pl.col("workflow_status").fill_null(WorkflowStatus.TODO).cast(str),
            pl.col("v2_manual_classification")
            .fill_null(ClassificationV2.ONBEKEND)
            .cast(str),
            pl.col("v2_lengte").fill_null(Lengte.ONBEKEND).cast(str),
            pl.col("v2_overnamestatus").fill_null(OvernameStatus.ONBEKEND).cast(str),
        )

        return df.select(self.FACULTY_SHEET_COLUMNS)

    # ------------------------------------------------------------------
    # Sheet creation
    # ------------------------------------------------------------------

    def build_workbook_for_dataframe(self, df: pl.DataFrame) -> Workbook:
        """Build a legacy-like workbook for a single exported dataset.

        Creates two sheets:
        - "Complete data" (all columns, read-only)
        - "Data entry" (subset of columns, editable with dropdown validations)

        This is the core primitive used by the filesystem workflow exporter.
        """
        wb = Workbook()

        # Complete data
        ws_complete = wb.active
        ws_complete.title = self.COMPLETE_SHEET_NAME
        self._write_dataframe(ws_complete, df, self.FACULTY_SHEET_COLUMNS)
        self._protect_sheet_all_locked(ws_complete)

        # Data entry
        ws_entry = wb.create_sheet(title=self.DATA_ENTRY_SHEET_NAME)
        self._write_dataframe(ws_entry, df, self.DATA_ENTRY_COLUMNS)
        self._add_validations(
            ws_entry, columns=self.DATA_ENTRY_COLUMNS, max_row=df.height + 1
        )
        self._protect_sheet_with_editable_columns(ws_entry, self.DATA_ENTRY_COLUMNS)

        # Make the Data entry sheet the active sheet.
        wb.active = wb.sheetnames.index(self.DATA_ENTRY_SHEET_NAME)

        return wb

    def _create_faculty_overview_sheet(
        self, wb: Workbook, faculty: str, df: pl.DataFrame
    ) -> None:
        """Create a single worksheet with the full faculty dataset.

        This is used for the dashboard download endpoints (single workbook with many sheets).
        For workflow exports on disk we use `build_workbook_for_dataframe`.
        """
        ws = wb.create_sheet(title=faculty)
        self._write_dataframe(ws, df, self.FACULTY_SHEET_COLUMNS)
        # Keep it read-only in this aggregated export
        self._protect_sheet_all_locked(ws)

    def _create_overview_sheet(self, wb: Workbook, df: pl.DataFrame) -> None:
        ws = wb.create_sheet(title="Overview", index=0)
        ws.append(["Faculty", "Total Items", "Total Students"])
        header_font = Font(bold=True)
        for cell in ws[1]:
            cell.font = header_font

        summary = df.group_by("faculty").agg(
            pl.count("material_id").alias("total_items"),
            pl.sum("count_students_registered").alias("total_students"),
        )

        for row in summary.iter_rows(named=True):
            ws.append(
                [row.get("faculty"), row.get("total_items"), row.get("total_students")]
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _write_headers(self, ws, columns: Iterable[str]) -> None:
        header_font = Font(bold=True)
        header_fill = PatternFill("solid", fgColor="DDDDDD")
        for idx, name in enumerate(columns, start=1):
            cell = ws.cell(row=1, column=idx, value=name)
            cell.font = header_font
            cell.fill = header_fill

    def _add_validations(self, ws, columns: list[str], max_row: int) -> None:
        def _add_list_validation(column_name: str, options: list[str]):
            if column_name not in columns:
                return
            letter = get_column_letter(columns.index(column_name) + 1)
            validation = DataValidation(
                type="list",
                formula1=f'"{",".join(options)}"',
                allow_blank=True,
            )
            ws.add_data_validation(validation)
            validation.add(f"{letter}2:{letter}{max_row}")

        _add_list_validation(
            "workflow_status",
            [
                WorkflowStatus.TODO.value,
                WorkflowStatus.IN_PROGRESS.value,
                WorkflowStatus.DONE.value,
            ],
        )
        _add_list_validation(
            "v2_manual_classification",
            [choice.value for choice in ClassificationV2],
        )
        _add_list_validation(
            "v2_lengte",
            [choice.value for choice in Lengte],
        )
        _add_list_validation(
            "v2_overnamestatus",
            [choice.value for choice in OvernameStatus],
        )

    def _write_dataframe(self, ws, df: pl.DataFrame, columns: list[str]) -> None:
        self._write_headers(ws, columns)

        # Ensure all columns exist
        for col in columns:
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).alias(col))

        # Write rows
        for row_idx, row in enumerate(
            df.select(columns).iter_rows(named=True), start=2
        ):
            for col_idx, col_name in enumerate(columns, start=1):
                ws.cell(row=row_idx, column=col_idx, value=row.get(col_name))

        # Autosize-ish (simple: set a reasonable width based on header length)
        for col_idx, col_name in enumerate(columns, start=1):
            letter = get_column_letter(col_idx)
            ws.column_dimensions[letter].width = max(
                12, min(40, len(str(col_name)) + 2)
            )

    def _protect_sheet_all_locked(self, ws) -> None:
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=ws.max_column):
            for cell in row:
                if hasattr(cell.protection, "copy"):
                    cell.protection = cell.protection.copy(locked=True)
                else:
                    cell.protection = cell.protection.__class__(locked=True)
        ws.protection.sheet = True
        ws.protection.enable()

    def _protect_sheet_with_editable_columns(self, ws, columns: list[str]) -> None:
        editable_letters = {
            get_column_letter(columns.index(col) + 1)
            for col in self.EDITABLE_COLUMNS
            if col in columns
        }

        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=len(columns)):
            for cell in row:
                col_letter = get_column_letter(cell.column)
                locked = col_letter not in editable_letters
                if hasattr(cell.protection, "copy"):
                    cell.protection = cell.protection.copy(locked=locked)
                else:
                    cell.protection = cell.protection.__class__(locked=locked)

        ws.protection.sheet = True
        ws.protection.enable()

    def _create_empty_workbook(self) -> BytesIO:
        wb = Workbook()
        ws = wb.active
        ws.title = "No Data"
        ws["A1"] = "No data available for export"

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output
