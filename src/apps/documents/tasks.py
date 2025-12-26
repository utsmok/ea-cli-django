"""
Async tasks for document processing.

Provides separate tasks for:
- PDF download from Canvas
- PDF text extraction
"""

from django.tasks import task
from loguru import logger

from apps.documents.services.download import download_undownloaded_pdfs
from apps.documents.services.parse import parse_pdfs


@task
async def check_and_download_pdfs(item_ids: list[int]) -> dict:
    """
    Check Canvas file existence and then download PDFs for CopyrightItems.

    This task first checks which files exist on Canvas (setting file_exists=True),
    then downloads the ones that exist.

    Args:
        item_ids: List of CopyrightItem material_id values

    Returns:
        Dictionary with combined statistics
    """
    from apps.core.services.canvas import refresh_file_existence_async

    try:
        # Step 1: Check file existence on Canvas
        logger.info(f"Checking Canvas file existence for {len(item_ids)} items...")

        # Only check items that haven't been checked or need rechecking
        from apps.core.models import CopyrightItem

        items_to_check = CopyrightItem.objects.filter(
            material_id__in=item_ids,
        )
        # make async w/ async for loop

        unchecked_ids = [
            i async for i in items_to_check.values_list("material_id", flat=True)
        ]

        if unchecked_ids:
            # Limit batch size to avoid overwhelming the Canvas API
            batch_size = min(len(unchecked_ids), 100)
            for i in range(0, len(unchecked_ids), batch_size):
                batch_ids = unchecked_ids[i : i + batch_size]
                existence_result = await refresh_file_existence_async(
                    item_ids=batch_ids, force=False
                )
                logger.info(
                    f"Canvas file existence check (batch {i // batch_size + 1}): {existence_result}"
                )
            existence_result = await refresh_file_existence_async(
                batch_size=batch_size, force=False
            )
            logger.info(f"Canvas file existence check: {existence_result}")

        # Step 2: Download PDFs for items with file_exists=True
        logger.info(f"Downloading PDFs for {len(item_ids)} items...")
        download_result = await download_pdfs_for_items.aenqueue(item_ids)

        return {
            "existence_check": existence_result if unchecked_ids else {"checked": 0},
            "download": download_result,
            "total_items": len(item_ids),
        }

    except Exception as e:
        logger.error(f"Error in check_and_download_pdfs: {e}")
        logger.exception(e)
        return {"error": str(e), "downloaded": 0, "failed": len(item_ids)}


@task
async def download_pdfs_for_items(item_ids: list[int]) -> dict:
    """
    Download PDFs for specific CopyrightItem IDs.

    Args:
        item_ids: List of CopyrightItem material_id values

    Returns:
        Dictionary with download statistics
    """
    from apps.core.models import CopyrightItem

    try:
        # Get items
        items = CopyrightItem.objects.filter(material_id__in=item_ids)
        count = items.count()

        # Mark items as having download in progress
        for item in items:
            item.extraction_status = "download_pending"
            item.save(update_fields=["extraction_status"])

        # Trigger download for specific items
        # The download service looks for items with file_exists=True and no document
        result = await download_undownloaded_pdfs(limit=0)

        # Update status
        for item in items:
            if item.document:
                item.extraction_status = "downloaded"
            else:
                item.extraction_status = "download_failed"
            await item.asave(update_fields=["extraction_status"])

        logger.info(f"Download task completed for {count} items: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in download_pdfs_for_items: {e}")
        return {"error": str(e), "downloaded": 0, "failed": len(item_ids)}


@task
async def extract_pdfs_for_items(item_ids: list[int]) -> dict:
    """
    Extract text from PDFs for specific CopyrightItem IDs.

    Args:
        item_ids: List of CopyrightItem material_id values

    Returns:
        Dictionary with extraction statistics
    """
    from apps.core.models import CopyrightItem

    try:
        # Get items that have documents
        items = CopyrightItem.objects.filter(
            material_id__in=item_ids, document__isnull=False
        )
        count = items.count()

        # Mark items as having extraction in progress
        for item in items:
            item.extraction_status = "extraction_pending"
            item.save(update_fields=["extraction_status"])

        # Trigger extraction for specific items
        result = await parse_pdfs(filter_ids=item_ids, skip_text=False)

        # Update status
        for item in items:
            item.extraction_status = "completed"
            item.save(update_fields=["extraction_status"])

        logger.info(f"Extraction task completed for {count} items: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in extract_pdfs_for_items: {e}")
        return {
            "error": str(e),
            "processed": 0,
            "successful": 0,
            "failed": len(item_ids),
        }


@task
async def download_and_extract_pdfs(item_ids: list[int]) -> dict:
    """
    Download and extract PDFs for specific CopyrightItem IDs.

    This is a convenience task that combines download and extraction.

    Args:
        item_ids: List of CopyrightItem material_id values

    Returns:
        Dictionary with combined statistics
    """
    try:
        # First download
        download_result = await download_pdfs_for_items(item_ids)

        # Then extract
        extraction_result = await extract_pdfs_for_items(item_ids)

        return {
            "download": download_result,
            "extraction": extraction_result,
        }

    except Exception as e:
        logger.error(f"Error in download_and_extract_pdfs: {e}")
        return {"error": str(e)}
