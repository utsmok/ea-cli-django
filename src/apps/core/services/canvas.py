"""
Canvas LMS API service for file existence verification.
Ports logic from ea-cli/easy_access/maintenance/file_existence.py
"""

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any, TypedDict

import httpx
from django.conf import settings
from django.utils import timezone

from apps.core.models import CopyrightItem
from apps.core.services.cache_service import cache_async_result
from apps.core.services.retry_logic import async_retry

logger = logging.getLogger(__name__)


class Item(TypedDict):
    material_id: int | None
    url: str


class FileExistenceResult(TypedDict):
    material_id: int | None
    file_exists: bool
    last_canvas_check: Any  # timezone-aware datetime
    canvas_course_id: int | None


class FileData(TypedDict):
    id: int | str | None
    folder_id: int | str | None
    display_name: str | None
    filename: str | None
    uuid: str | None
    url: str | None


async def select_items_needing_check(
    ttl_days: int | None = None,
    batch_size: int = 1000,
    force: bool = False,
) -> list[Item]:
    """
    Select copyright items that need file existence verification.

    Args:
        ttl_days: TTL in days (None means check all unchecked items)
        batch_size: Maximum number of items to return
        force: If True, check all items regardless of TTL

    Returns:
        List of item dictionaries with material_id and url
    """
    logger.info("Selecting items that need file existence verification...")

    # Build queryset
    queryset = CopyrightItem.objects.filter(url__isnull=False).exclude(url="")

    if not force:
        if ttl_days is not None:
            cutoff_date = timezone.now() - timedelta(days=ttl_days)
            # Check items that are either unchecked or older than TTL
            from django.db.models import Q

            queryset = queryset.filter(
                Q(file_exists__isnull=True) | Q(last_canvas_check__lt=cutoff_date)
            )
            logger.info(f"Using cutoff date: {cutoff_date}")
        else:
            # Check only unchecked items
            queryset = queryset.filter(file_exists__isnull=True)
            logger.info("Only checking files that have not been checked ever")

    # Order by last_canvas_check (nulls first)
    queryset = queryset.order_by("last_canvas_check")

    # Limit
    if batch_size > 0:
        queryset = queryset[:batch_size]

    # Convert to list of Items
    items: list[Item] = []
    async for item in queryset:
        if item.material_id and item.url:
            items.append(Item(material_id=item.material_id, url=item.url))

    logger.info(f"Selected {len(items)} items needing file existence verification")
    return items


@cache_async_result(
    timeout=86400, key_prefix="canvas_file_exists", cache_name="queries"
)
@async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def check_single_file_existence(
    item_data: Item,
    client: httpx.AsyncClient,
) -> FileExistenceResult:
    """
    Check file existence for a single item.

    Cached for 24 hours because file existence in Canvas LMS
    is stable (files are rarely deleted).

    Args:
        item_data: Dictionary with material_id and url
        client: HTTP client session

    Returns:
        Dictionary with material_id, file_exists, last_canvas_check, canvas_course_id
    """
    material_id = item_data.get("material_id")
    url = item_data.get("url")

    try:
        # Extract file_id from URL
        # Handle None, empty string, or invalid URL format
        if not url or "/files/" not in url:
            logger.warning(f"Invalid URL format for material_id {material_id}: {url}")
            return FileExistenceResult(
                material_id=material_id,
                file_exists=False,
                last_canvas_check=timezone.now(),
                canvas_course_id=None,
            )

        file_id = url.split("/files/")[1].split("/")[0].split("?")[0]
        api_url = f"{settings.CANVAS_API_URL}/files/{file_id}"

        response = await client.get(api_url)
        file_exists = response.status_code == 200

        # Don't retry on 401/403 (auth failures) or 404 (file not found)
        if response.status_code in (401, 403, 404):
            return FileExistenceResult(
                material_id=material_id,
                file_exists=False,
                last_canvas_check=timezone.now(),
                canvas_course_id=None,
            )

        # Raise for other errors - retry logic will handle retryable ones
        response.raise_for_status()

        canvas_course_id = None
        if file_exists:
            file_data = response.json()
            folder_id = file_data.get("folder_id")
            if folder_id:
                canvas_course_id = await determine_course_id_from_folder(
                    folder_id, client
                )

        return FileExistenceResult(
            material_id=material_id,
            file_exists=file_exists,
            last_canvas_check=timezone.now(),
            canvas_course_id=canvas_course_id,
        )

    except Exception as e:
        logger.error(
            f"Error checking file existence for material_id {material_id}: {e}"
        )
        return FileExistenceResult(
            material_id=material_id,
            file_exists=False,
            last_canvas_check=timezone.now(),
            canvas_course_id=None,
        )


async def determine_course_id_from_folder(
    folder_id: int | str,
    client: httpx.AsyncClient,
) -> int | None:
    """
    Determine Canvas course ID from folder ID.
    """
    try:
        folder_url = f"{settings.CANVAS_API_URL}/folders/{folder_id}"
        response = await client.get(folder_url)

        if response.status_code != 200:
            logger.warning(f"Failed to get folder info for folder_id {folder_id}")
            return None

        folder_data = response.json()
        context_type = folder_data.get("context_type")
        context_id = folder_data.get("context_id")

        if context_type == "Course" and context_id:
            if isinstance(context_id, int):
                return context_id
            elif str(context_id).isdigit():
                return int(context_id)

        return None

    except Exception as e:
        logger.error(f"Error getting folder info for folder_id {folder_id}: {e}")
        return None


async def update_file_existence_batch(results: list[FileExistenceResult]) -> None:
    """
    Update file existence status for a batch of items.
    """
    if not results:
        return

    logger.info(f"Updating file existence for {len(results)} items")

    for result in results:
        try:
            await CopyrightItem.objects.filter(
                material_id=result["material_id"]
            ).aupdate(
                file_exists=result["file_exists"],
                last_canvas_check=result["last_canvas_check"],
                canvas_course_id=result["canvas_course_id"],
            )
        except Exception as e:
            logger.error(f"Error updating material_id {result['material_id']}: {e}")

    logger.info(f"Successfully updated {len(results)} items")


async def refresh_file_existence_async(
    ttl_days: int | None = None,
    batch_size: int = 1000,
    max_concurrent: int = 50,
    force: bool = False,
    rate_limit_delay: float = 0.05,
) -> dict[str, Any]:
    """
    Refresh file existence status for copyright items based on TTL policy.

    Args:
        ttl_days: TTL in days for file existence checks
        batch_size: Number of items to process in each batch
        max_concurrent: Maximum concurrent requests
        force: If True, check all items regardless of TTL
        rate_limit_delay: Delay in seconds between requests

    Returns:
        Dictionary with statistics about the operation
    """
    logger.info("Starting file existence verification...")

    api_token = settings.CANVAS_API_TOKEN
    if not api_token:
        logger.error("Canvas API token not found in settings")
        return {"error": "No API token", "checked": 0, "exists": 0, "not_exists": 0}

    # Select items needing verification
    items_to_check = await select_items_needing_check(ttl_days, batch_size, force)

    if not items_to_check:
        logger.info("No items need file existence verification")
        return {"checked": 0, "exists": 0, "not_exists": 0}

    # Set up HTTP client
    headers = {"Authorization": f"Bearer {api_token}"}
    async with httpx.AsyncClient(
        headers=headers, follow_redirects=True, timeout=20.0
    ) as client:
        logger.info(f"Checking file existence for {len(items_to_check)} items")

        # Check files concurrently with rate limiting
        semaphore = asyncio.Semaphore(max_concurrent)
        results: list[FileExistenceResult] = []

        async def check_with_rate_limit(item_data: Item) -> None:
            async with semaphore:
                result = await check_single_file_existence(item_data, client)
                results.append(result)
                if rate_limit_delay > 0:
                    await asyncio.sleep(rate_limit_delay)

        # Execute concurrently
        start_time = time.time()
        tasks = [check_with_rate_limit(item) for item in items_to_check]
        await asyncio.gather(*tasks, return_exceptions=True)
        duration = time.time() - start_time

        logger.info(
            f"Completed file existence checks in {duration:.2f}s "
            f"({len(results) / max(duration, 0.001):.1f} req/sec)"
        )

        # Update database
        await update_file_existence_batch(results)

        # Calculate statistics
        exists_count = sum(1 for r in results if r["file_exists"])
        not_exists_count = sum(1 for r in results if not r["file_exists"])

        logger.info(
            f"File existence verification complete: "
            f"{exists_count} exist, {not_exists_count} not found"
        )

        return {
            "checked": len(results),
            "exists": exists_count,
            "not_exists": not_exists_count,
            "duration_seconds": int(duration),
        }
