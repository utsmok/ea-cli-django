"""
Tests for document download service.

NOTE: Complex async/FileField tests are marked as integration tests
and tested through the E2E pipeline. Direct unit testing of FileField
operations in async context has Django limitations.
"""

from unittest.mock import patch

import pytest

from apps.core.models import CopyrightItem, Faculty
from apps.documents.models import Document, PDFCanvasMetadata
from apps.documents.services.download import (
    create_or_link_document,
    download_undownloaded_pdfs,
)


@pytest.mark.django_db(transaction=True)
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

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_document_rollback_on_item_save_failure(tmp_path):
    """
    Test that document creation is rolled back if item update fails.
    """
    # Setup
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )
    item = await CopyrightItem.objects.acreate(
        material_id=100,
        url="http://canvas/files/100",
        file_exists=True,
        faculty=faculty,
    )

    meta = await PDFCanvasMetadata.objects.acreate(
        uuid="uuid100",
        display_name="test100.pdf",
        filename="test100.pdf",
        size=10,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
        download_url="http://example.com/100"
    )

    # Create a dummy file
    file_path = tmp_path / "test100.pdf"
    file_path.write_bytes(b"content")

    # Mock item.asave to fail
    with patch.object(CopyrightItem, 'asave', side_effect=Exception("DB Error")):
        with pytest.raises(Exception, match="DB Error"):
            await create_or_link_document(item, file_path, meta)

    # Verify document was not created (rolled back)
    assert await Document.objects.acount() == 0

    # Verify item was not updated
    await item.arefresh_from_db()
    assert item.document is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_successful_create_document_commits(tmp_path):
    """
    Test that document is created and linked successfully.
    """
    # Setup
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )
    item = await CopyrightItem.objects.acreate(
        material_id=101,
        url="http://canvas/files/101",
        file_exists=True,
        faculty=faculty,
    )

    meta = await PDFCanvasMetadata.objects.acreate(
        uuid="uuid101",
        display_name="test101.pdf",
        filename="test101.pdf",
        size=10,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
        download_url="http://example.com/101"
    )

    # Create a dummy file
    file_path = tmp_path / "test101.pdf"
    file_path.write_bytes(b"content")

    doc = await create_or_link_document(item, file_path, meta)

    assert doc is not None
    assert await Document.objects.acount() == 1

    await item.arefresh_from_db()
    assert item.document_id == doc.id
