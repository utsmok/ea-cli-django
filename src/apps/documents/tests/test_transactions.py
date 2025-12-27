"""
Tests for document download service.

NOTE: Complex async/FileField tests are marked as integration tests
and tested through the E2E pipeline. Direct unit testing of FileField
operations in async context has Django limitations.
"""

from unittest.mock import patch

import pytest

from apps.core.models import CopyrightItem, Faculty
from apps.documents.models import Document
from apps.documents.services.download import download_undownloaded_pdfs


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_download_failure_does_not_create_orphaned_records(tmp_path):
    """
    Test that PDF download failures don't create orphaned records.
    """
    # Setup
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )

    # Create items that will fail to download
    await CopyrightItem.objects.aget_or_create(
        material_id=7,
        defaults={
            "url": "http://canvas/files/7",  # Will return 404
            "file_exists": True,
            "faculty": faculty,
        },
    )

    await CopyrightItem.objects.aget_or_create(
        material_id=8,
        defaults={
            "url": "http://canvas/files/8",  # Will return 404
            "file_exists": True,
            "faculty": faculty,
        },
    )

    # Mock download to fail (returns None for failure)
    async def mock_download_fail(url, filepath, client):
        return None

    with (
        patch(
            "apps.documents.services.download.download_pdf_from_canvas",
            side_effect=mock_download_fail,
        ),
        patch(
            "apps.documents.services.download.settings.CANVAS_API_TOKEN", "fake-token"
        ),
        patch("apps.documents.services.download.settings.PDF_DOWNLOAD_DIR", tmp_path),
    ):
        result = await download_undownloaded_pdfs()

    # Verify result reflects failures
    assert result["downloaded"] == 0
    assert result["failed"] >= 2
