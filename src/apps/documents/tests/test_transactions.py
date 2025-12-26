"""
Tests for transaction management in document download service.

Tests verify that atomic operations properly roll back on failure,
preventing orphaned records and partial data.
"""

from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile

from apps.core.models import CopyrightItem, Faculty
from apps.documents.models import Document, PDFCanvasMetadata
from apps.documents.services.download import (
    create_or_link_document,
    download_undownloaded_pdfs,
)


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_create_document_rollback_on_item_save_failure(tmp_path):
    """
    Test that if linking document to item fails, the document is rolled back.
    """
    # Setup
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )
    item, _ = await CopyrightItem.objects.aget_or_create(
        material_id=1,
        defaults={
            "url": "http://canvas/files/1",
            "file_exists": True,
            "faculty": faculty,
        },
    )

    # Create metadata
    metadata = await PDFCanvasMetadata.objects.acreate(
        id=1,
        uuid="uuid1",
        display_name="test.pdf",
        filename="test.pdf",
        size=100,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
    )

    # Create a test file
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"PDF CONTENT")

    # Mock item.asave to raise an exception
    original_asave = item.asave

    async def failing_asave(**kwargs):
        # Fail on the second call (after document creation)
        if hasattr(item, "_save_count"):
            item._save_count += 1
        else:
            item._save_count = 1
        if item._save_count > 1:
            raise RuntimeError("Database connection lost")
        return await original_asave(**kwargs)

    with patch.object(CopyrightItem, "asave", failing_asave):
        with pytest.raises(RuntimeError, match="Database connection lost"):
            await create_or_link_document(item, test_file, metadata)

    # Verify that the document was NOT created (rolled back)
    doc_count = await Document.objects.acount()
    assert doc_count == 0, "Document should be rolled back"


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_create_document_rollback_on_file_save_failure(tmp_path):
    """
    Test that if file save fails, no document record is created.
    """
    # Setup
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )
    item, _ = await CopyrightItem.objects.aget_or_create(
        material_id=2,
        defaults={
            "url": "http://canvas/files/2",
            "file_exists": True,
            "faculty": faculty,
        },
    )

    # Create metadata
    metadata = await PDFCanvasMetadata.objects.acreate(
        id=2,
        uuid="uuid2",
        display_name="test2.pdf",
        filename="test2.pdf",
        size=100,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
    )

    # Create a test file
    test_file = tmp_path / "test2.pdf"
    test_file.write_bytes(b"PDF CONTENT 2")

    # Mock the file.save to fail
    async def mock_file_save(name, content, save=False):
        raise OSError("Storage full")

    with patch("apps.documents.models.Document.file.save", new=mock_file_save):
        with pytest.raises(IOError, match="Storage full"):
            await create_or_link_document(item, test_file, metadata)

    # Verify that the document was NOT created (rolled back)
    doc_count = await Document.objects.acount()
    assert doc_count == 0, "Document should be rolled back after file save failure"

    # Verify item was not linked
    await item.arefresh_from_db()
    assert item.document_id is None


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_successful_create_document_commits(tmp_path):
    """
    Test that successful document creation commits all changes.
    """
    # Setup
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )
    item, _ = await CopyrightItem.objects.aget_or_create(
        material_id=3,
        defaults={
            "url": "http://canvas/files/3",
            "file_exists": True,
            "faculty": faculty,
        },
    )

    # Create metadata
    metadata = await PDFCanvasMetadata.objects.acreate(
        id=3,
        uuid="uuid3",
        display_name="test3.pdf",
        filename="test3.pdf",
        size=100,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
    )

    # Create a test file
    test_file = tmp_path / "test3.pdf"
    test_file.write_bytes(b"PDF CONTENT 3")

    # Should succeed
    doc = await create_or_link_document(item, test_file, metadata)

    # Verify document was created
    assert doc is not None
    assert await Document.objects.acount() == 1

    # Verify item was linked
    await item.arefresh_from_db()
    assert item.document_id == doc.id
    assert item.filehash == doc.filehash


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_link_existing_document_no_rollback_needed(tmp_path):
    """
    Test that linking to an existing document with same hash works.
    """
    # Setup - create an existing document
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )

    metadata = await PDFCanvasMetadata.objects.acreate(
        id=4,
        uuid="uuid4",
        display_name="existing.pdf",
        filename="existing.pdf",
        size=100,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
    )

    # Create existing document with known hash
    existing_content = b"EXISTING PDF CONTENT"
    doc = await Document.objects.acreate(
        filehash="existing_hash",
        canvas_metadata=metadata,
        filename="existing.pdf",
        original_url="http://canvas/files/4",
    )
    # Note: file.save is sync, need to wrap
    from asgiref.sync import sync_to_async

    await sync_to_async(doc.file.save)("existing.pdf", ContentFile(existing_content))

    # Create two items with the same file content
    test_file = tmp_path / "same.pdf"
    test_file.write_bytes(existing_content)

    item1, _ = await CopyrightItem.objects.aget_or_create(
        material_id=5,
        defaults={
            "url": "http://canvas/files/5",
            "file_exists": True,
            "faculty": faculty,
        },
    )

    item2, _ = await CopyrightItem.objects.aget_or_create(
        material_id=6,
        defaults={
            "url": "http://canvas/files/6",
            "file_exists": True,
            "faculty": faculty,
        },
    )

    # Both items should link to the same document
    await create_or_link_document(item1, test_file, metadata)
    await create_or_link_document(item2, test_file, metadata)

    # Verify only one document exists
    assert await Document.objects.acount() == 1

    # Verify both items link to same document
    await item1.arefresh_from_db()
    await item2.arefresh_from_db()
    assert item1.document_id == item2.document_id
    assert item1.filehash == item2.filehash == "existing_hash"


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
    item1, _ = await CopyrightItem.objects.aget_or_create(
        material_id=7,
        defaults={
            "url": "http://canvas/files/7",  # Will return 404
            "file_exists": True,
            "faculty": faculty,
        },
    )

    item2, _ = await CopyrightItem.objects.aget_or_create(
        material_id=8,
        defaults={
            "url": "http://canvas/files/8",  # Will return 404
            "file_exists": True,
            "faculty": faculty,
        },
    )

    # Mock download to fail
    async def mock_download(url, filepath, client):
        return None  # Simulate download failure

    with (
        patch(
            "apps.documents.services.download.download_pdf_from_canvas",
            side_effect=mock_download,
        ),
        patch(
            "apps.documents.services.download.settings.CANVAS_API_TOKEN", "fake-token"
        ),
        patch("apps.documents.services.download.settings.PDF_DOWNLOAD_DIR", tmp_path),
    ):
        result = await download_undownloaded_pdfs()

    # Verify no documents were created
    assert await Document.objects.acount() == 0

    # Verify items are still unlinked
    await item1.arefresh_from_db()
    await item2.arefresh_from_db()
    assert item1.document_id is None
    assert item2.document_id is None

    # Verify result reflects failures
    assert result["downloaded"] == 0
    assert result["failed"] >= 2


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_partial_failure_rolls_back_only_failed_items(tmp_path):
    """
    Test that when some items fail, only failed items roll back.
    """
    # Setup
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )

    metadata = await PDFCanvasMetadata.objects.acreate(
        id=10,
        uuid="uuid10",
        display_name="test.pdf",
        filename="test.pdf",
        size=100,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
    )

    # Create successful item
    test_file = tmp_path / "success.pdf"
    test_file.write_bytes(b"SUCCESS")

    item_success, _ = await CopyrightItem.objects.aget_or_create(
        material_id=10,
        defaults={
            "url": "http://canvas/files/10",
            "file_exists": True,
            "faculty": faculty,
        },
    )

    # Create failing item
    test_file_fail = tmp_path / "fail.pdf"
    test_file_fail.write_bytes(b"FAIL")

    item_fail, _ = await CopyrightItem.objects.aget_or_create(
        material_id=11,
        defaults={
            "url": "http://canvas/files/11",
            "file_exists": True,
            "faculty": faculty,
        },
    )

    # Process successful item
    await create_or_link_document(item_success, test_file, metadata)

    # Mock failure for second item
    with patch.object(CopyrightItem, "asave", side_effect=RuntimeError("DB error")):
        with pytest.raises(RuntimeError):
            await create_or_link_document(item_fail, test_file_fail, metadata)

    # Verify successful item has document
    await item_success.arefresh_from_db()
    assert item_success.document_id is not None

    # Verify failed item does NOT have document
    await item_fail.arefresh_from_db()
    assert item_fail.document_id is None

    # Verify only one document exists
    assert await Document.objects.acount() == 1
