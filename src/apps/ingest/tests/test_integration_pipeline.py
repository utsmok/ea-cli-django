"""
Integration tests for the complete ingestion pipeline.

Tests the full workflow:
1. Ingest Qlik export → Create CopyrightItems
2. Ingest Faculty sheets → Update items with human annotations
3. Export faculty sheets → Verify structure matches legacy format
"""

import shutil
from pathlib import Path

import pytest
from django.core.files import File

from apps.core.models import CopyrightItem, Faculty
from apps.ingest.models import IngestionBatch
from apps.ingest.services.export import ExportService
from apps.ingest.tasks import process_batch, stage_batch
from apps.users.models import User


@pytest.fixture
def test_user(db):
    """Create a test user for ingestion."""
    return User.objects.create_user(username="testuser", email="test@example.com")


@pytest.fixture
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent.parent.parent.parent.parent / "test_data"


@pytest.fixture
def qlik_file(test_data_dir):
    """Path to Qlik export test file."""
    file_path = test_data_dir / "qlik_data.xlsx"
    assert file_path.exists(), f"Qlik test file not found: {file_path}"
    return file_path


@pytest.fixture
def faculty_sheets_dir(test_data_dir):
    """Path to faculty sheets directory."""
    sheets_dir = test_data_dir / "faculty_sheets"
    assert sheets_dir.exists(), f"Faculty sheets not found: {sheets_dir}"
    return sheets_dir


@pytest.mark.django_db
class TestQlikIngestion:
    """Test Qlik export ingestion."""

    def test_ingest_qlik_export(self, test_user, qlik_file):
        """Test complete Qlik ingestion workflow."""
        # Create ingestion batch
        with open(qlik_file, "rb") as f:
            batch = IngestionBatch.objects.create(
                source_type=IngestionBatch.SourceType.QLIK,
                uploaded_by=test_user,
                source_file=File(f, name="qlik_data.xlsx"),
            )

        # Stage the data
        stage_result = stage_batch(batch.id)
        assert stage_result["success"], f"Staging failed: {stage_result}"

        # Verify batch was staged
        batch.refresh_from_db()
        assert batch.status == IngestionBatch.Status.STAGED

        # Process the data
        process_result = process_batch(batch.id)
        assert process_result["success"], f"Processing failed: {process_result}"

        # Verify batch statistics
        batch.refresh_from_db()
        assert batch.status in [
            IngestionBatch.Status.COMPLETED,
            IngestionBatch.Status.PARTIAL,
        ]
        assert batch.items_created > 0, "No items were created"
        assert batch.rows_staged > 0, "No rows were staged"

        # Verify items were created
        item_count = CopyrightItem.objects.count()
        assert item_count > 0, "No CopyrightItems created"
        assert (
            item_count == batch.items_created
        ), f"Item count mismatch: {item_count} != {batch.items_created}"

        # Verify sample item has expected fields
        sample_item = CopyrightItem.objects.first()
        assert sample_item.material_id is not None
        assert sample_item.title is not None or sample_item.filename is not None

        return batch


@pytest.mark.django_db
class TestFacultyIngestion:
    """Test Faculty sheet ingestion."""

    def test_ingest_faculty_sheets(
        self, test_user, qlik_file, faculty_sheets_dir, test_data_dir
    ):
        """Test Faculty sheet ingestion after Qlik import."""
        # First, ingest Qlik data to create items
        with open(qlik_file, "rb") as f:
            qlik_batch = IngestionBatch.objects.create(
                source_type=IngestionBatch.SourceType.QLIK,
                uploaded_by=test_user,
                source_file=File(f, name="qlik_data.xlsx"),
            )

        stage_batch(qlik_batch.id)
        process_batch(qlik_batch.id)

        initial_count = CopyrightItem.objects.count()
        assert initial_count > 0, "No items created from Qlik import"

        # Now ingest a faculty sheet
        eemcs_inbox = faculty_sheets_dir / "EEMCS" / "inbox.xlsx"
        if not eemcs_inbox.exists():
            pytest.skip("EEMCS inbox.xlsx not found in test data")

        with open(eemcs_inbox, "rb") as f:
            faculty_batch = IngestionBatch.objects.create(
                source_type=IngestionBatch.SourceType.FACULTY,
                uploaded_by=test_user,
                source_file=File(f, name="EEMCS_inbox.xlsx"),
                faculty_code="EEMCS",
            )

        # Stage and process
        stage_result = stage_batch(faculty_batch.id)
        assert stage_result["success"], f"Faculty staging failed: {stage_result}"

        process_result = process_batch(faculty_batch.id)
        assert process_result["success"], f"Faculty processing failed: {process_result}"

        # Verify updates were applied
        faculty_batch.refresh_from_db()
        assert faculty_batch.items_updated > 0 or faculty_batch.items_skipped > 0

        # Verify no new items created (Faculty sheets only update)
        final_count = CopyrightItem.objects.count()
        assert (
            final_count == initial_count
        ), "Faculty sheets should not create new items"


@pytest.mark.django_db
class TestExportFunctionality:
    """Test export functionality."""

    def test_export_structure(self, test_user, qlik_file, tmp_path):
        """Test export creates correct directory structure."""
        # Setup: Ingest some data first
        with open(qlik_file, "rb") as f:
            batch = IngestionBatch.objects.create(
                source_type=IngestionBatch.SourceType.QLIK,
                uploaded_by=test_user,
                source_file=File(f, name="qlik_data.xlsx"),
            )

        stage_batch(batch.id)
        process_batch(batch.id)

        # Ensure we have faculties in the database
        # Create test faculties if they don't exist
        for abbr in ["EEMCS", "BMS", "ET", "ITC", "TNW"]:
            Faculty.objects.get_or_create(
                abbreviation=abbr,
                defaults={
                    "hierarchy_level": 1,
                    "name": f"Faculty of {abbr}",
                    "full_abbreviation": abbr,
                },
            )

        # Export
        export_dir = tmp_path / "exports"
        exporter = ExportService()
        result = exporter.export_workflow_tree(output_dir=export_dir)

        # Verify directory structure
        assert export_dir.exists(), "Export directory not created"

        # Check for faculty directories
        faculties_with_data = result.get("faculties", [])
        for faculty in faculties_with_data:
            faculty_dir = export_dir / faculty
            assert faculty_dir.exists(), f"Faculty directory not created: {faculty}"

            # Check for workflow files (may be empty if no items in that workflow state)
            # The export service only creates files if there's data
            if (faculty_dir / "inbox.xlsx").exists():
                assert (faculty_dir / "inbox.xlsx").stat().st_size > 0

        # Check for overview CSV
        overview_csv = export_dir / "update_overview.csv"
        assert overview_csv.exists(), "update_overview.csv not created"


@pytest.mark.django_db
class TestRoundTripIngestion:
    """Test that exported sheets can be re-ingested."""

    def test_export_reimport_cycle(self, test_user, qlik_file, tmp_path):
        """Test exporting and re-importing data maintains integrity."""
        # Initial import
        with open(qlik_file, "rb") as f:
            batch1 = IngestionBatch.objects.create(
                source_type=IngestionBatch.SourceType.QLIK,
                uploaded_by=test_user,
                source_file=File(f, name="qlik_data.xlsx"),
            )

        stage_batch(batch1.id)
        process_batch(batch1.id)

        initial_count = CopyrightItem.objects.count()
        sample_item_initial = CopyrightItem.objects.first()
        initial_workflow = sample_item_initial.workflow_status

        # Export
        export_dir = tmp_path / "exports"
        exporter = ExportService()
        result = exporter.export_workflow_tree(output_dir=export_dir)

        # Find an exported file to re-import
        exported_files = list(export_dir.rglob("*.xlsx"))
        if not exported_files:
            pytest.skip("No files were exported (may be empty dataset)")

        # Take the first exported file that looks like a faculty sheet
        reimport_file = None
        for f in exported_files:
            if "overview" not in f.name.lower():
                reimport_file = f
                break

        if not reimport_file:
            pytest.skip("No suitable file found for re-import")

        # Re-import as faculty sheet
        with open(reimport_file, "rb") as f:
            batch2 = IngestionBatch.objects.create(
                source_type=IngestionBatch.SourceType.FACULTY,
                uploaded_by=test_user,
                source_file=File(f, name=reimport_file.name),
            )

        stage_batch(batch2.id)
        process_batch(batch2.id)

        # Verify no new items created
        final_count = CopyrightItem.objects.count()
        assert final_count == initial_count, "Re-import should not create new items"


@pytest.mark.django_db
def test_complete_pipeline(test_user, qlik_file, tmp_path):
    """End-to-end test of the complete pipeline."""
    # 1. Ingest Qlik data
    with open(qlik_file, "rb") as f:
        qlik_batch = IngestionBatch.objects.create(
            source_type=IngestionBatch.SourceType.QLIK,
            uploaded_by=test_user,
            source_file=File(f, name="qlik_data.xlsx"),
        )

    stage_batch(qlik_batch.id)
    process_batch(qlik_batch.id)

    # 2. Verify items created
    assert CopyrightItem.objects.count() > 0

    # 3. Export
    export_dir = tmp_path / "exports"
    exporter = ExportService()
    result = exporter.export_workflow_tree(output_dir=export_dir)

    # 4. Verify export succeeded
    assert export_dir.exists()
    assert len(result.get("files", [])) > 0 or len(result.get("faculties", [])) == 0

    print(f"\nPipeline test complete:")
    print(f"  - Qlik items created: {qlik_batch.items_created}")
    print(f"  - Export directory: {export_dir}")
    print(f"  - Files exported: {len(result.get('files', []))}")
