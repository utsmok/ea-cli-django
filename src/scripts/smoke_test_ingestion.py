"""
Test script for Phase A ingestion pipeline.

Tests importing both Qlik and Faculty data.
"""

# NOTE: This file is a *manual* smoke-test script, not an automated pytest test.
# It requires a configured database and real input files.
# To avoid failing CI/automation, we skip it at collection time.
import pytest

pytest.skip(
    "Manual ingestion smoke script (not an automated test)", allow_module_level=True
)

from pathlib import Path

from django.contrib.auth import get_user_model

from apps.ingest.models import IngestionBatch
from apps.ingest.tasks import process_batch, stage_batch

User = get_user_model()


def test_qlik_ingestion():
    """Test importing Qlik data."""

    # Get admin user
    user = User.objects.first()
    if not user:
        return

    # Create batch
    qlik_file = Path("test_data/qlik_data.xlsx")
    batch = IngestionBatch.objects.create(
        source_type=IngestionBatch.SourceType.QLIK,
        source_file=qlik_file.read_bytes()
        and qlik_file.name,  # Need to attach file properly
        uploaded_by=user,
    )

    # We need to attach the file properly using Django's file handling
    with Path.open(qlik_file, "rb") as f:
        from django.core.files import File

        batch.source_file = File(f, name=qlik_file.name)
        batch.save()

    # Stage the batch
    stage_batch(batch.id)

    # Refresh and check
    batch.refresh_from_db()

    # Process the batch
    process_batch(batch.id)

    # Final check
    batch.refresh_from_db()

    return batch


def test_faculty_ingestion():
    """Test importing Faculty data."""

    # Get admin user
    user = User.objects.first()
    if not user:
        return

    # Test with EEMCS faculty
    faculties = ["EEMCS", "BMS", "ET"]

    for faculty in faculties:
        # Process inbox, in_progress, done for this faculty
        for sheet_name in ["inbox", "in_progress", "done"]:
            faculty_file = Path(f"test_data/faculty_sheets/{faculty}/{sheet_name}.xlsx")

            if not faculty_file.exists():
                continue

            # Create batch
            batch = IngestionBatch.objects.create(
                source_type=IngestionBatch.SourceType.FACULTY,
                uploaded_by=user,
                faculty_code=faculty,
            )

            # Attach file
            with Path.open(faculty_file, "rb") as f:
                from django.core.files import File

                batch.source_file = File(f, name=f"{faculty}_{sheet_name}.xlsx")
                batch.save()

            # Stage
            result = stage_batch(batch.id)
            if not result["success"]:
                continue

            # Process
            result = process_batch(batch.id)

            batch.refresh_from_db()


if __name__ == "__main__":
    try:
        # Test Qlik ingestion
        qlik_batch = test_qlik_ingestion()

        # Test Faculty ingestion
        test_faculty_ingestion()

    except Exception:
        import traceback

        traceback.print_exc()
