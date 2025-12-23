from unittest.mock import patch

import pytest
from asgiref.sync import sync_to_async
from django.core.files.base import ContentFile

from apps.core.models import CopyrightItem, Faculty
from apps.documents.models import Document, PDFCanvasMetadata, PDFText
from apps.documents.services.download import download_undownloaded_pdfs


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_document_deduplication(tmp_path):
    # Setup
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )
    item1, _ = await CopyrightItem.objects.aget_or_create(
        material_id=1,
        defaults={
            "url": "http://canvas/files/1",
            "file_exists": True,
            "faculty": faculty,
        },
    )
    item2, _ = await CopyrightItem.objects.aget_or_create(
        material_id=2,
        defaults={
            "url": "http://canvas/files/2",
            "file_exists": True,
            "faculty": faculty,
        },
    )

    file_content = b"PDF CONTENT"

    # Mock download_pdf_from_canvas to return a local file with the same content for both
    mock_metadata = await PDFCanvasMetadata.objects.acreate(
        id=1,
        uuid="uuid1",
        display_name="test.pdf",
        filename="test.pdf",
        size=len(file_content),
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
    )

    async def mock_download(url, filepath, client):
        filepath.write_bytes(file_content)
        return filepath, mock_metadata

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
        await download_undownloaded_pdfs()

    # Verify both items point to the SAME Document object
    await item1.arefresh_from_db()
    await item2.arefresh_from_db()

    # Use sync ORM since we are outside the loop or wrap again
    # But arefresh_from_db worked.
    assert item1.document_id is not None
    assert item2.document_id is not None
    assert item1.document_id == item2.document_id
    assert await Document.objects.acount() == 1
    assert item1.filehash == item2.filehash


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_extraction_service_call():
    # This test verifies that parse_pdfs calls the extraction service
    from apps.documents.services.parse import parse_pdfs

    _faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS-2"},
    )
    meta = await PDFCanvasMetadata.objects.acreate(
        id=2,
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
