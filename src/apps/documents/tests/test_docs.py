from unittest.mock import patch

import pytest
from django.core.files.base import ContentFile

from apps.core.models import CopyrightItem, Faculty
from apps.documents.models import Document, PDFCanvasMetadata, PDFText


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_document_deduplication(tmp_path):
    """
    Test that documents with same filehash are deduplicated at DB level (unique constraint).
    """
    from asgiref.sync import sync_to_async
    from django.db import IntegrityError

    # Create metadata
    meta1 = await PDFCanvasMetadata.objects.acreate(
        uuid="uuid1",
        display_name="test1.pdf",
        filename="test1.pdf",
        size=10,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
        download_url="http://example.com/1"
    )

    # Create first document
    doc1 = await Document.objects.acreate(
        canvas_metadata=meta1,
        filehash="hash123",
        filename="test1.pdf"
    )
    await sync_to_async(doc1.file.save)("test1.pdf", ContentFile(b"content"))

    # Create second metadata
    meta2 = await PDFCanvasMetadata.objects.acreate(
        uuid="uuid2",
        display_name="test2.pdf",
        filename="test2.pdf",
        size=10,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
        download_url="http://example.com/2"
    )

    # Try to create second document with same hash - should fail due to unique constraint
    with pytest.raises(IntegrityError):
        await Document.objects.acreate(
            canvas_metadata=meta2,
            filehash="hash123",
            filename="test2.pdf"
        )

    # Verify we can use aget_or_create to handle it gracefully (deduplication)
    doc2, created = await Document.objects.aget_or_create(
        filehash="hash123",
        defaults={
            "canvas_metadata": meta2,
            "filename": "test2.pdf"
        }
    )

    assert not created
    assert doc2.id == doc1.id
    assert doc2.filehash == "hash123"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_extraction_service_call():
    # This test verifies that parse_pdfs calls the extraction service
    from apps.documents.services.parse import parse_pdfs
    from asgiref.sync import sync_to_async

    _faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS-2"},
    )
    meta = await PDFCanvasMetadata.objects.acreate(
        uuid="uuid2",
        display_name="test2.pdf",
        filename="test2.pdf",
        size=10,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
    )
    doc = await Document.objects.acreate(
        canvas_metadata=meta, filehash="somehash", filename="test.pdf"
    )
    # file.save is sync, need to wrap
    await sync_to_async(doc.file.save)("test.pdf", ContentFile(b"something"))

    with patch("apps.documents.services.parse.extract_text_from_pdf") as mock_extract:
        mock_extract.return_value = {
            "content": "extracted text",
            "quality_score": 0.9,
            "num_pages": 1,
        }
        await parse_pdfs()

        assert mock_extract.called
        await doc.arefresh_from_db()
        assert doc.extraction_attempted is True
        assert doc.extraction_successful is True
        # Check pdftext
        pdftext = await PDFText.objects.aget(document=doc)
        assert pdftext.extracted_text == "extracted text"
