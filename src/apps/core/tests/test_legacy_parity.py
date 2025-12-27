"""
Parity verification tests between legacy (ea-cli/) and new (src/apps/) code.

These tests verify that the new Django-based pipeline produces the same
outputs as the legacy CLI tool when processing the same input data.

IMPORTANT: These tests use REAL API calls (Osiris, Canvas, people pages).
No mocking. This ensures true end-to-end parity verification.
"""

import os
import tempfile
from pathlib import Path

import polars as pl
import pytest

from apps.ingest.tasks import process_batch, stage_batch
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db(transaction=True)
@pytest.mark.external_api
@pytest.mark.timeout(300)  # 5 minutes for real API calls
class TestLegacyParity:
    """
    Test parity between legacy and new code.

    Process: 1) Load pre-generated legacy baseline outputs
            2) Run new pipeline on same test data
            3) Compare outputs (faculty sheets)

    PREREQUISITE: Generate legacy baseline first
        python scripts/generate_legacy_baseline.py

    This test is SLOW and requires network access for external APIs.
    Marked with @pytest.mark.external_api so it can be skipped during development.
    """

    def test_base_case_5_parity_with_legacy(self, base_case_5_file):
        """
        RED PHASE: This test should fail initially.

        Verifies that processing base_case_5.xlsx through new code
        produces the same results as legacy code.

        IMPORTANT: This requires the legacy baseline to be generated first.
        Run: python scripts/generate_legacy_baseline.py

        Expected differences (acceptable):
        - Timestamps (created_at, updated_at)
        - Auto-generated IDs
        - Ordering of rows (if not sorted)
        - Column name differences (e.g., "Material id" vs "material_id")

        Expected to match:
        - Material IDs
        - Course codes
        - Classifications
        - File types
        - Faculty mappings
        - Enriched data (courses, persons)
        - Faculty sheet file structure
        """
        # Arrange: Check for baseline
        baseline_dir = Path(__file__).parent.parent.parent.parent.parent / "test_data" / "legacy_baseline"

        if not baseline_dir.exists():
            pytest.skip(
                f"Legacy baseline not found: {baseline_dir} does not exist. "
                "Generate it first: python scripts/generate_legacy_baseline.py"
            )

        baseline_info_file = baseline_dir / "baseline_info.json"
        if not baseline_info_file.exists():
            pytest.skip(
                f"Legacy baseline info not found: {baseline_info_file} does not exist. "
                "Regenerate baseline: python scripts/generate_legacy_baseline.py"
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Act: Run new pipeline
            new_output_dir = tmpdir / "new_output"
            os.makedirs(new_output_dir, exist_ok=True)

            new_result = self._run_new_pipeline(
                base_case_5_file, new_output_dir
            )

            # Assert: Compare outputs against baseline
            self._assert_faculty_sheets_match(
                baseline_dir / "faculty_sheets",
                new_output_dir,
            )

    def _run_new_pipeline(self, input_file: Path, output_dir: Path) -> dict:
        """
        Run the new Django-based pipeline.

        Returns: dict with batch_id and output_files
        """
        # Step 1: Ingest Qlik file
        batch = self._ingest_qlik_file(input_file)

        # Step 2: Process batch (merge to CopyrightItem)
        # This automatically triggers enrichment via trigger_batch_enrichment()
        process_batch.call(batch.id)

        # Step 3: Export faculty sheets
        self._export_faculty_sheets(output_dir)

        return {
            "batch_id": batch.id,
            "output_dir": output_dir,
        }

    def _ingest_qlik_file(self, file_path: Path):
        """Create ingestion batch and stage data."""
        from apps.ingest.models import IngestionBatch
        from django.core.files import File as DjangoFile
        first_user = User.objects.create(username="legacy_parity_user")
        print(f"Using user {first_user} for upload")
        with open(file_path, "rb") as f:
            django_file = DjangoFile(f, name=file_path.name)
            batch = IngestionBatch.objects.create(
                source_type=IngestionBatch.SourceType.QLIK,
                source_file=django_file,
                status=IngestionBatch.Status.PENDING,
                uploaded_by=first_user,

            )

        # Stage the data
        stage_batch.call(batch.id)

        return batch

    def _export_faculty_sheets(self, output_dir: Path):
        """Export faculty sheets to specified directory."""
        from apps.ingest.services.export import ExportService

        service = ExportService()
        service.export_workflow_tree(output_dir=str(output_dir))

    def _assert_faculty_sheets_match(
        self, legacy_dir: Path, new_dir: Path
    ):
        """
        Assert that faculty sheet outputs match.

        Compares Excel files row-by-row, ignoring:
        - Timestamp columns
        - Auto-generated IDs
        - Row order (if not explicitly sorted)
        """
        # Find all faculty sheets in both directories
        legacy_sheets = self._find_faculty_sheets(legacy_dir)
        new_sheets = self._find_faculty_sheets(new_dir)

        # Should have same faculties
        assert set(legacy_sheets.keys()) == set(new_sheets.keys()), (
            f"Faculties mismatch: legacy={set(legacy_sheets.keys())}, "
            f"new={set(new_sheets.keys())}"
        )

        # Compare each faculty's data
        for faculty in legacy_sheets.keys():
            legacy_df = pl.read_excel(legacy_sheets[faculty])
            new_df = pl.read_excel(new_sheets[faculty])

            # Normalize for comparison (sort, remove ignored columns)
            legacy_normalized = self._normalize_dataframe(legacy_df)
            new_normalized = self._normalize_dataframe(new_df)

            # Assert dataframes are equal
            try:
                assert_frame_equal(legacy_normalized, new_normalized)
            except AssertionError as e:
                raise AssertionError(
                    f"Faculty {faculty} data mismatch:\n{e}\n\n"
                    f"Legacy rows: {len(legacy_normalized)}, "
                    f"New rows: {len(new_normalized)}"
                )

    def _find_faculty_sheets(self, directory: Path) -> dict[str, Path]:
        """Find all faculty sheet files in directory."""
        sheets = {}

        for faculty_dir in directory.iterdir():
            if not faculty_dir.is_dir():
                continue

            # Look for ANY Excel file (inbox.xlsx, done.xlsx, overview.xlsx)
            excel_files = list(faculty_dir.glob("*.xlsx"))
            if excel_files:
                # Prefer inbox.xlsx for data entry, fallback to any Excel file
                inbox_file = faculty_dir / "inbox.xlsx"
                if inbox_file.exists():
                    sheets[faculty_dir.name] = inbox_file
                else:
                    # Use the first Excel file found
                    sheets[faculty_dir.name] = excel_files[0]

        return sheets

    def _normalize_dataframe(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Normalize DataFrame for comparison.

        - Sort by material_id
        - Remove timestamp columns
        - Remove auto-generated ID columns
        - Normalize strings (trim, case)
        """
        # Columns to ignore
        ignore_cols = [
            "id",
            "created_at",
            "updated_at",
            "row_number",
        ]

        # Drop ignored columns if they exist
        cols_to_drop = [c for c in ignore_cols if c in df.columns]
        df = df.drop(cols_to_drop)

        # Sort by material_id if it exists
        if "Material id" in df.columns:
            df = df.sort("Material id")
        elif "material_id" in df.columns:
            df = df.sort("material_id")

        # Normalize string columns
        for col in df.columns:
            if df[col].dtype == pl.Utf8:
                df = df.with_columns(
                    pl.col(col).str.strip_chars().str.to_lowercase()
                )

        return df


def assert_frame_equal(left: pl.DataFrame, right: pl.DataFrame):
    """
    Assert two Polars DataFrames are equal.

    Raises AssertionError with detailed diff if not equal.
    """
    if left.shape != right.shape:
        raise AssertionError(
            f"Shape mismatch: {left.shape} vs {right.shape}"
        )

    if set(left.columns) != set(right.columns):
        raise AssertionError(
            f"Column mismatch: {set(left.columns)} vs {set(right.columns)}"
        )

    # Compare row by row
    for i in range(len(left)):
        left_row = left.row(i)
        right_row = right.row(i)

        if left_row != right_row:
            raise AssertionError(
                f"Row {i} mismatch:\n  Left:  {left_row}\n  Right: {right_row}"
            )
