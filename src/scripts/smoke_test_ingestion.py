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
    print("\n" + "=" * 70)
    print("TESTING QLIK INGESTION")
    print("=" * 70)

    # Get admin user
    user = User.objects.first()
    if not user:
        print("ERROR: No users in database. Create one first.")
        return

    print(f"Using user: {user}")

    # Create batch
    qlik_file = Path("test_data/qlik_data.xlsx")
    batch = IngestionBatch.objects.create(
        source_type=IngestionBatch.SourceType.QLIK,
        source_file=qlik_file.read_bytes()
        and qlik_file.name,  # Need to attach file properly
        uploaded_by=user,
    )
    print(f"Created batch {batch.id}")

    # We need to attach the file properly using Django's file handling
    with open(qlik_file, "rb") as f:
        from django.core.files import File

        batch.source_file = File(f, name=qlik_file.name)
        batch.save()

    # Stage the batch
    print("\nStaging batch...")
    result = stage_batch(batch.id)
    print(f"Stage result: {result}")

    # Refresh and check
    batch.refresh_from_db()
    print(f"Batch status: {batch.status}")
    print(f"Total rows: {batch.total_rows}")
    print(f"Rows staged: {batch.rows_staged}")

    # Process the batch
    print("\nProcessing batch...")
    result = process_batch(batch.id)
    print(f"Process result: {result}")

    # Final check
    batch.refresh_from_db()
    print(f"\nFinal Status: {batch.status}")
    print(f"Items Created: {batch.items_created}")
    print(f"Items Updated: {batch.items_updated}")
    print(f"Items Skipped: {batch.items_skipped}")
    print(f"Items Failed: {batch.items_failed}")

    return batch


def test_faculty_ingestion():
    """Test importing Faculty data."""
    print("\n" + "=" * 70)
    print("TESTING FACULTY INGESTION")
    print("=" * 70)

    # Get admin user
    user = User.objects.first()
    if not user:
        print("ERROR: No users in database. Create one first.")
        return

    # Test with EEMCS faculty
    faculties = ["EEMCS", "BMS", "ET"]

    for faculty in faculties:
        print(f"\n--- Testing {faculty} ---")

        # Process inbox, in_progress, done for this faculty
        for sheet_name in ["inbox", "in_progress", "done"]:
            faculty_file = Path(f"test_data/faculty_sheets/{faculty}/{sheet_name}.xlsx")

            if not faculty_file.exists():
                print(f"  Skipping {sheet_name}.xlsx (not found)")
                continue

            print(f"  Processing {sheet_name}.xlsx...")

            # Create batch
            batch = IngestionBatch.objects.create(
                source_type=IngestionBatch.SourceType.FACULTY,
                uploaded_by=user,
                faculty_code=faculty,
            )

            # Attach file
            with open(faculty_file, "rb") as f:
                from django.core.files import File

                batch.source_file = File(f, name=f"{faculty}_{sheet_name}.xlsx")
                batch.save()

            # Stage
            result = stage_batch(batch.id)
            if not result["success"]:
                print(f"    Staging failed: {result}")
                continue

            # Process
            result = process_batch(batch.id)

            batch.refresh_from_db()
            print(f"    Status: {batch.status}")
            print(
                f"    Updated: {batch.items_updated}, Skipped: {batch.items_skipped}, Failed: {batch.items_failed}"
            )


if __name__ == "__main__":
    print("Starting Phase A Test Suite")

    try:
        # Test Qlik ingestion
        qlik_batch = test_qlik_ingestion()

        # Test Faculty ingestion
        test_faculty_ingestion()

        print("\n" + "=" * 70)
        print("ALL TESTS COMPLETE")
        print("=" * 70)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback

        traceback.print_exc()
