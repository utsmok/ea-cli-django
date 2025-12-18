from typing import List, Optional
from apps.core.utils.safecast import safe_int
from loguru import logger
from django.utils import timezone

from apps.core.models import CopyrightItem, EnrichmentStatus
from apps.enrichment.services.osiris_scraper import OsirisScraperService
from apps.documents.services.download import download_undownloaded_pdfs
from apps.documents.services.parse import parse_pdfs


async def enrich_item(item_id: int):
    """Enrich a single item with Osiris data and download PDF."""
    try:
        item = await CopyrightItem.objects.aget(material_id=item_id)
        item.enrichment_status = EnrichmentStatus.RUNNING
        await item.asave(update_fields=["enrichment_status"])

        enrichment_successful = True
        error_messages = []

        async with OsirisScraperService() as scraper:
            # 1. Enrichment from Osiris (Course)
            if item.course_code:
                try:
                    # Robust parsing for course ID
                    # Formats: "202200096", "2024-202200096-1B", "202200096|202300001"
                    raw_codes = item.course_code.split('|')
                    course_code_int = None

                    for raw in raw_codes:
                        clean = raw.strip()
                        if "-" in clean:
                            parts = clean.split("-")
                            # Try to find the 9-digit part
                            for part in parts:
                                if len(part) == 9 and part.isdigit():
                                    course_code_int = int(part)
                                    break
                        elif clean.isdigit():
                            course_code_int = int(clean)

                        if course_code_int:
                            break

                    if course_code_int:
                        course_info = await scraper.fetch_course_details(course_code_int)
                        if course_info:
                            # Update Course model
                            from apps.core.models import Course, Person, CourseEmployee, Faculty

                            # Faculty lookup if available
                            faculty = None
                            if course_info.get("faculty_abbr"):
                                faculty = await Faculty.objects.filter(abbreviation=course_info["faculty_abbr"]).afirst()

                            course, _ = await Course.objects.aupdate_or_create(
                                cursuscode=course_code_int,
                                defaults={
                                    "name": course_info.get("name") or "Unknown",
                                    "short_name": course_info.get("short_name"),
                                    "programme_text": course_info.get("programme"),
                                    "faculty": faculty,
                                    "internal_id": course_info.get("internal_id"),
                                    "year": safe_int(course_info.get("year")) or 2024,
                                }
                            )

                            # Link item to course
                            await item.courses.aadd(course)

                            # Fetch and persist persons
                            all_names = set(course_info.get("teachers", [])) | set(course_info.get("contacts", []))
                            for name in all_names:
                                p_data = await scraper.fetch_person_data(name)
                                if p_data:
                                    person, _ = await Person.objects.aupdate_or_create(
                                        input_name=name,
                                        defaults={
                                            "main_name": p_data.get("main_name"),
                                            "email": p_data.get("email"),
                                            "people_page_url": p_data.get("people_page_url"),
                                            "is_verified": True,
                                        }
                                    )

                                    # Link person to course
                                    role = "contacts" if name in course_info.get("contacts", []) else "teachers"
                                    # Use aupdate_or_create to avoid duplicate key errors if already exists
                                    await CourseEmployee.objects.aupdate_or_create(
                                        course=course,
                                        person=person,
                                        defaults={"role": role}
                                    )
                    else:
                        logger.warning(f"Could not parse valid course ID from {item.course_code}")

                except Exception as e:
                    logger.warning(f"Error enriching course for item {item_id}: {e}")
                    enrichment_successful = False
                    error_messages.append(str(e))

            # 2. Download from Canvas
            if item.url and "/files/" in item.url:
                try:
                    await download_undownloaded_pdfs(limit=0)
                except Exception as e:
                    logger.warning(f"Error downloading PDF for item {item_id}: {e}")
                    # Download failure shouldn't necessarily fail the whole job if enrichment worked?
                    # But if both fail, it's bad.

            # 3. Parse PDFs
            try:
                await parse_pdfs(filter_ids=[item_id])
            except Exception as e:
                logger.warning(f"Error parsing PDF for item {item_id}: {e}")

        if enrichment_successful:
            item.enrichment_status = EnrichmentStatus.COMPLETED
        else:
            item.enrichment_status = EnrichmentStatus.FAILED

        item.last_enrichment_attempt = timezone.now()
        await item.asave(update_fields=["enrichment_status", "last_enrichment_attempt"])

    except Exception as e:
        logger.error(f"Failed to enrich item {item_id}: {e}")
        # Need to re-fetch item in case it was modified/deleted, or just use filter update
        try:
           item = await CopyrightItem.objects.aget(material_id=item_id)
           item.enrichment_status = EnrichmentStatus.FAILED
           await item.asave(update_fields=["enrichment_status"])
        except Exception:
           pass


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
