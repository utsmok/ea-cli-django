"""
Tests for native async ORM usage in document services.

Tests verify that Django 6.0 native async ORM methods work correctly.
"""

import tempfile
from pathlib import Path

import pytest

from apps.core.models import CopyrightItem, Faculty
from apps.documents.models import Document, PDFCanvasMetadata


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_async_aget_or_create_creates_new_document():
    """Test that aget_or_create creates a new document when hash doesn't exist."""
    metadata = await PDFCanvasMetadata.objects.acreate(
        id=100,
        uuid="uuid100",
        display_name="test.pdf",
        filename="test.pdf",
        size=100,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
    )

    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )

    _item, _ = await CopyrightItem.objects.aget_or_create(
        material_id=100,
        defaults={
            "url": "http://canvas/files/100",
            "file_exists": True,
            "faculty": faculty,
        },
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(b"NEW PDF CONTENT")
        test_path = Path(f.name)

    try:
        doc, created = await Document.objects.aget_or_create(
            filehash="new_hash_123",
            defaults={
                "canvas_metadata": metadata,
                "filename": "test.pdf",
                "original_url": "http://canvas/files/100",
            },
        )

        assert created is True
        assert doc.filehash == "new_hash_123"
    finally:
        test_path.unlink(missing_ok=True)


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_async_aget_or_create_fetches_existing_document():
    """Test that aget_or_create fetches existing document when hash exists."""
    metadata = await PDFCanvasMetadata.objects.acreate(
        id=101,
        uuid="uuid101",
        display_name="test.pdf",
        filename="test.pdf",
        size=100,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
    )

    # Create initial document
    existing_doc = await Document.objects.acreate(
        filehash="existing_hash_456",
        canvas_metadata=metadata,
        filename="existing.pdf",
        original_url="http://canvas/files/101",
    )

    # Try to get or create with same hash
    doc, created = await Document.objects.aget_or_create(
        filehash="existing_hash_456",
        defaults={
            "canvas_metadata": metadata,
            "filename": "should_not_be_used.pdf",
            "original_url": "http://canvas/files/dummy",
        },
    )

    assert created is False
    assert doc.id == existing_doc.id
    assert doc.filehash == "existing_hash_456"
    assert doc.filename == "existing.pdf"  # Original value preserved


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_async_aupdate_or_create_updates_existing_document():
    """Test that aupdate_or_create updates existing document."""
    metadata = await PDFCanvasMetadata.objects.acreate(
        id=102,
        uuid="uuid102",
        display_name="original.pdf",
        filename="original.pdf",
        size=100,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
    )

    # Create initial metadata
    assert metadata.filename == "original.pdf"

    # Update with aupdate_or_create
    updated_meta, created = await PDFCanvasMetadata.objects.aupdate_or_create(
        id=102,
        defaults={
            "uuid": "uuid102",
            "display_name": "updated.pdf",
            "filename": "updated.pdf",
            "size": 200,
            "canvas_created_at": "2024-01-01T00:00:00Z",
            "canvas_updated_at": "2024-01-01T00:00:00Z",
            "locked": False,
            "hidden": False,
            "visibility_level": "public",
        },
    )

    assert created is False  # Was updated, not created
    assert updated_meta.id == 102
    assert updated_meta.filename == "updated.pdf"
    assert updated_meta.display_name == "updated.pdf"
    assert updated_meta.size == 200

    # Verify persisted
    await updated_meta.arefresh_from_db()
    assert updated_meta.filename == "updated.pdf"


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_async_asave_updates_item_fields():
    """Test that asave correctly updates item fields."""
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )

    item = await CopyrightItem.objects.acreate(
        material_id=103,
        url="http://canvas/files/103",
        file_exists=True,
        faculty=faculty,
        filehash="old_hash",
    )

    assert item.filehash == "old_hash"

    # Update using asave with specific fields
    item.filehash = "new_hash_789"
    await item.asave(update_fields=["filehash"])

    # Re-fetch to verify
    await item.arefresh_from_db()
    assert item.filehash == "new_hash_789"


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_async_acount_counts_documents():
    """Test that acount correctly counts documents."""
    metadata = await PDFCanvasMetadata.objects.acreate(
        id=104,
        uuid="uuid104",
        display_name="test.pdf",
        filename="test.pdf",
        size=100,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
    )

    # Create multiple documents
    await Document.objects.acreate(
        filehash="hash1", canvas_metadata=metadata, filename="file1.pdf"
    )
    await Document.objects.acreate(
        filehash="hash2", canvas_metadata=metadata, filename="file2.pdf"
    )
    await Document.objects.acreate(
        filehash="hash3", canvas_metadata=metadata, filename="file3.pdf"
    )

    count = await Document.objects.acount()
    assert count == 3

    # Test with filter
    filtered_count = await Document.objects.filter(filehash="hash1").acount()
    assert filtered_count == 1


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_async_afilter_with_related():
    """Test that afilter correctly handles related fields."""
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )

    metadata = await PDFCanvasMetadata.objects.acreate(
        id=105,
        uuid="uuid105",
        display_name="test.pdf",
        filename="test.pdf",
        size=100,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
    )

    doc = await Document.objects.acreate(
        filehash="hash_with_doc",
        canvas_metadata=metadata,
        filename="has_doc.pdf",
    )

    # Create item with document
    _item_with_doc = await CopyrightItem.objects.acreate(
        material_id=104,
        url="http://canvas/files/104",
        file_exists=True,
        faculty=faculty,
        document=doc,
    )

    # Create item without document
    _item_without_doc = await CopyrightItem.objects.acreate(
        material_id=105,
        url="http://canvas/files/105",
        file_exists=True,
        faculty=faculty,
    )

    # Count items with documents
    with_doc_count = await CopyrightItem.objects.filter(document__isnull=False).acount()
    assert with_doc_count >= 1

    # Count items without documents
    without_doc_count = await CopyrightItem.objects.filter(
        document__isnull=True
    ).acount()
    assert without_doc_count >= 1


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_async_aiter_iterates_over_queryset():
    """Test that async for iteration works correctly."""
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )

    # Create multiple items
    for i in range(5):
        await CopyrightItem.objects.acreate(
            material_id=200 + i,
            url=f"http://canvas/files/{200 + i}",
            file_exists=True,
            faculty=faculty,
        )

    # Iterate using async for
    collected_ids = []
    async for item in CopyrightItem.objects.filter(
        material_id__gte=200, material_id__lt=205
    ):
        collected_ids.append(item.material_id)

    assert len(collected_ids) == 5
    assert set(collected_ids) == {200, 201, 202, 203, 204}


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_async_adelete_removes_records():
    """Test that adelete correctly removes records."""
    _faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )

    metadata = await PDFCanvasMetadata.objects.acreate(
        id=106,
        uuid="uuid106",
        display_name="test.pdf",
        filename="test.pdf",
        size=100,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
    )

    doc = await Document.objects.acreate(
        filehash="to_delete",
        canvas_metadata=metadata,
        filename="delete_me.pdf",
    )

    # Verify it exists
    assert await Document.objects.filter(filehash="to_delete").acount() == 1

    # Delete using adelete
    await doc.adelete()

    # Verify it's gone
    assert await Document.objects.filter(filehash="to_delete").acount() == 0


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_async_afirst_gets_first_result():
    """Test that afirst returns the first record or None."""
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )

    # Create items
    await CopyrightItem.objects.acreate(
        material_id=300, url="http://a", file_exists=True, faculty=faculty
    )
    await CopyrightItem.objects.acreate(
        material_id=301, url="http://b", file_exists=True, faculty=faculty
    )

    # Get first by material_id (ordered by pk by default)
    first = await CopyrightItem.objects.filter(material_id__gte=300).afirst()
    assert first is not None
    assert first.material_id >= 300

    # Try to get non-existent
    none_result = await CopyrightItem.objects.filter(material_id=99999).afirst()
    assert none_result is None


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_async_aupdate_updates_queryset():
    """Test that aupdate updates all matching records."""
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )

    # Create items with specific status
    await CopyrightItem.objects.acreate(
        material_id=400, url="http://a", file_exists=True, faculty=faculty
    )
    await CopyrightItem.objects.acreate(
        material_id=401, url="http://b", file_exists=True, faculty=faculty
    )

    # Update all with material_id >= 400
    updated_count = await CopyrightItem.objects.filter(material_id__gte=400).aupdate(
        file_exists=False
    )

    assert updated_count >= 2

    # Verify updates
    item400 = await CopyrightItem.objects.aget(material_id=400)
    item401 = await CopyrightItem.objects.aget(material_id=401)
    assert item400.file_exists is False
    assert item401.file_exists is False


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_async_select_related_works():
    """Test that select_related reduces queries in async context."""

    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="BMS",
        defaults={"name": "BMS", "hierarchy_level": 1, "full_abbreviation": "UT-BMS"},
    )

    metadata = await PDFCanvasMetadata.objects.acreate(
        id=107,
        uuid="uuid107",
        display_name="test.pdf",
        filename="test.pdf",
        size=100,
        canvas_created_at="2024-01-01T00:00:00Z",
        canvas_updated_at="2024-01-01T00:00:00Z",
        locked=False,
        hidden=False,
        visibility_level="public",
    )

    doc = await Document.objects.acreate(
        filehash="hash_related", canvas_metadata=metadata, filename="related.pdf"
    )

    _item = await CopyrightItem.objects.acreate(
        material_id=500,
        url="http://canvas/files/500",
        file_exists=True,
        faculty=faculty,
        document=doc,
    )

    # Fetch with select_related
    item_fetched = await CopyrightItem.objects.select_related(
        "document", "faculty"
    ).aget(material_id=500)

    # Access related attributes - should not trigger additional queries
    assert item_fetched.document is not None
    assert item_fetched.document.filehash == "hash_related"
    assert item_fetched.faculty is not None
    assert item_fetched.faculty.abbreviation == "BMS"
