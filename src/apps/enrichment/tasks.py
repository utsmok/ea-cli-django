from typing import List, Optional
from loguru import logger
from django.utils import timezone

from apps.core.models import CopyrightItem, EnrichmentStatus
from apps.enrichment.services.osiris_scraper import OsirisScraperService
from apps.documents.services.download import download_undownloaded_pdfs
from apps.documents.services.parse import parse_pdfs


async def enrich_item(item_id: int):
    """Enrich a single item with Osiris data and download PDF."""
    try:
        item = CopyrightItem.objects.get(material_id=item_id)
        item.enrichment_status = EnrichmentStatus.RUNNING
        item.save(update_fields=["enrichment_status"])

        async with OsirisScraperService() as scraper:
            # 1. Enrichment from Osiris (Course)
            if item.course_code:
                try:
                    # simplistic: course_code might be multiple, but we take first valid for now
                    course_code_int = int(item.course_code.split('|')[0].strip())
                    course_info = await scraper.fetch_course_details(course_code_int)
                    # TODO: Update Course/Person models with fetched info
                    # Legcay code has complex linking logic, for now we just mark as COMPLETED
                except Exception as e:
                    logger.warning(f"Error enriching course for item {item_id}: {e}")

            # 2. Download from Canvas
            if item.url and "/files/" in item.url:
                # This service handles batching, but we can call it for one item by filtering
                await download_undownloaded_pdfs(limit=0) # For now just run the batch downloader

            # 3. Parse PDFs
            await parse_pdfs(filter_ids=[item_id])

        item.enrichment_status = EnrichmentStatus.COMPLETED
        item.last_enrichment_attempt = timezone.now()
        item.save(update_fields=["enrichment_status", "last_enrichment_attempt"])

    except Exception as e:
        logger.error(f"Failed to enrich item {item_id}: {e}")
        if 'item' in locals():
            item.enrichment_status = EnrichmentStatus.FAILED
            item.save(update_fields=["enrichment_status"])


def trigger_batch_enrichment(batch_id: int):
    """Trigger enrichment for all items in a batch."""
    # This should be a Celery task in a real production environment
    logger.info(f"Triggering enrichment for batch {batch_id}")

    items = CopyrightItem.objects.filter(change_logs__batch_id=batch_id).distinct()
    logger.info(f"Found {items.count()} items in batch {batch_id} to enrich")

    import asyncio

    async def run_enrichment():
        for item in items:
            await enrich_item(item.material_id)

    # In a real app, we'd use a task queue. Here we just run it.
    # We use a thread-safe way to run the loop if needed, but for simplicity:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(run_enrichment())
        else:
            loop.run_until_complete(run_enrichment())
    except Exception as e:
        logger.error(f"Error running batch enrichment: {e}")
