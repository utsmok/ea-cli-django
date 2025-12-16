"""
PDF Download service for Canvas LMS.
Ports logic from ea-cli/easy_access/pdf/download.py
"""

import asyncio
import datetime
import logging
from pathlib import Path

import httpx
from django.conf import settings

from apps.core.models import CopyrightItem
from apps.documents.models import PDF, PDFCanvasMetadata

logger = logging.getLogger(__name__)


async def download_pdf_from_canvas(
    url: str,
    filepath: Path,
    client: httpx.AsyncClient,
) -> tuple[Path, PDFCanvasMetadata] | None:
    """
    Downloads a PDF from Canvas and saves it to the given filepath.

    Returns tuple of (filepath, metadata) if successful, else None.
    """
    if not url or "/files/" not in url:
        logger.error(f"Invalid URL format: {url}")
        return None

    file_id = url.split("/files/")[1].split("/")[0].split("?")[0]
    api_url = f"{settings.CANVAS_API_URL}/files/{file_id}"

    try:
        # Get file metadata
        response = await client.get(api_url, params={"include[]": ["usage_rights", "user"]})
        response.raise_for_status()

        # Check rate limit
        rate_limit_remaining = response.headers.get("X-Rate-Limit-Remaining", "1000000")
        if float(rate_limit_remaining) < 10:
            logger.warning(f"Rate limit critically low: {rate_limit_remaining}. Pausing.")
            await asyncio.sleep(10)

        metadata = response.json()

        # Create or update PDFCanvasMetadata
        meta_defaults = {
            "uuid": metadata.get("uuid", ""),
            "folder_id": int(metadata.get("folder_id")) if metadata.get("folder_id") else None,
            "display_name": metadata.get("display_name", ""),
            "filename": metadata.get("filename", ""),
            "upload_status": metadata.get("upload_status", ""),
            "content_type": metadata.get("content-type", ""),
            "mime_class": metadata.get("mime_class", ""),
            "category": metadata.get("category", ""),
            "download_url": metadata.get("url", ""),
            "size": int(metadata.get("size", 0)),
            "thumbnail_url": metadata.get("thumbnail_url"),
            "canvas_created_at": metadata.get("created_at"),
            "canvas_updated_at": metadata.get("updated_at"),
            "canvas_modified_at": metadata.get("modified_at"),
            "locked": metadata.get("locked", False),
            "hidden": metadata.get("hidden", False),
            "lock_at": metadata.get("lock_at"),
            "unlock_at": metadata.get("unlock_at"),
            "visibility_level": metadata.get("visibility_level", ""),
        }

        # Add user info if present
        if metadata.get("user"):
            meta_defaults.update({
                "user_id": metadata["user"].get("id"),
                "user_anonymous_id": metadata["user"].get("anonymous_id"),
                "user_display_name": metadata["user"].get("display_name"),
                "user_avatar_image_url": metadata["user"].get("avatar_image_url"),
                "user_html_url": metadata["user"].get("html_url"),
                "user_pronouns": metadata["user"].get("pronouns"),
            })

        # Use sync ORM for now (will be wrapped in sync_to_async if needed)
        from asgiref.sync import sync_to_async

        @sync_to_async
        def create_metadata():
            obj, _ = PDFCanvasMetadata.objects.update_or_create(
                id=int(metadata.get("id")),
                defaults=meta_defaults,
            )
            return obj

        pdf_metadata_obj = await create_metadata()

        # Download the file
        download_link = metadata.get("url")
        if not download_link:
            logger.error(f"No download URL found for file ID {file_id}")
            return None

        async with client.stream("GET", download_link) as file_response:
            file_response.raise_for_status()

            # Check rate limit on download
            rate_limit_remaining = file_response.headers.get("X-Rate-Limit-Remaining", "1000000")
            if float(rate_limit_remaining) < 10:
                logger.warning(f"Rate limit critically low: {rate_limit_remaining}. Pausing.")
                await asyncio.sleep(10)

            with open(filepath, "wb") as f:
                async for chunk in file_response.aiter_bytes():
                    f.write(chunk)

        return filepath, pdf_metadata_obj

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        logger.error(f"HTTP error downloading from {url}: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error downloading from {url}: {e}")
        return None


async def download_undownloaded_pdfs(limit: int = 0) -> dict:
    """
    Downloads all PDFs that have file_exists=True but no PDF record yet.

    Args:
        limit: Maximum number of PDFs to download (0 = no limit)

    Returns:
        Dictionary with statistics
    """
    api_token = settings.CANVAS_API_TOKEN
    if not api_token:
        logger.error("Canvas API token not found in settings")
        return {"error": "No API token", "downloaded": 0, "failed": 0}

    download_dir = settings.PDF_DOWNLOAD_DIR

    # Find items that need downloading
    # Items where file_exists=True but no PDF record
    from asgiref.sync import sync_to_async

    @sync_to_async
    def get_items_to_download():
        queryset = CopyrightItem.objects.filter(
            file_exists=True,
            pdf__isnull=True,
        ).exclude(url__isnull=True).exclude(url="")

        if limit > 0:
            queryset = queryset[:limit]

        return list(queryset)

    items = await get_items_to_download()

    if not items:
        logger.info("No undownloaded PDFs to download")
        return {"downloaded": 0, "failed": 0}

    logger.info(f"Downloading {len(items)} PDFs")

    # Set up client
    headers = {"Authorization": f"Bearer {api_token}"}
    semaphore = asyncio.Semaphore(5)  # Limit concurrent downloads

    downloaded = 0
    failed = 0

    async with httpx.AsyncClient(
        headers=headers, follow_redirects=True, timeout=60.0
    ) as client:

        async def download_single(item: CopyrightItem) -> bool:
            nonlocal downloaded, failed
            try:
                async with semaphore:
                    # Generate safe filename
                    filename = item.filename or f"{item.material_id}.pdf"
                    safe_filename = "".join(
                        c for c in filename if c.isalnum() or c in "._- "
                    ).strip()
                    if not safe_filename:
                        safe_filename = f"{item.material_id}.pdf"

                    filepath = download_dir / f"{item.material_id}_{safe_filename}"
                    if not str(filepath).endswith(".pdf"):
                        filepath = Path(str(filepath) + ".pdf")

                    result = await download_pdf_from_canvas(item.url, filepath, client)

                    if result:
                        file_path, pdf_metadata_obj = result

                        @sync_to_async
                        def create_pdf_record():
                            return PDF.objects.create(
                                copyright_item=item,
                                canvas_metadata=pdf_metadata_obj,
                                current_file_name=file_path.name,
                                filename=pdf_metadata_obj.filename,
                                url=item.url,
                                file_size=file_path.stat().st_size,
                                retrieved_on=datetime.datetime.now(datetime.UTC),
                            )

                        await create_pdf_record()
                        downloaded += 1
                        return True
                    else:
                        failed += 1
                        return False

            except Exception as e:
                logger.error(f"Error downloading material_id {item.material_id}: {e}")
                failed += 1
                return False

        tasks = [download_single(item) for item in items]
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info(f"Download complete: {downloaded} successful, {failed} failed")
    return {"downloaded": downloaded, "failed": failed}
