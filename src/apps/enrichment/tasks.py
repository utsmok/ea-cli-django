from typing import Any

from django.tasks import task
from django.utils import timezone
from loguru import logger

from apps.core.models import CopyrightItem, EnrichmentStatus
from apps.core.utils.safecast import safe_int
from apps.documents.services.download import download_undownloaded_pdfs
from apps.documents.services.parse import parse_pdfs
from apps.enrichment.services.osiris_scraper import OsirisScraperService

OSIRIS_COURSE_CODE_LENGTH = 9


async def _get_item_snapshot(item: CopyrightItem) -> dict:
    """Helper to capture a snapshot of an item's relations."""
    courses = []
    async for c in item.courses.all():
        courses.append({"code": c.cursuscode, "name": c.name})

    teachers = []
    async for c in item.courses.all():
        async for teacher in c.teachers.all():
            teachers.append(teacher.main_name or teacher.input_name)

    return {
        "courses": courses,
        "teachers": list(set(teachers)),
        "has_document": item.document_id is not None,
    }


def parse_course_id(course_code_str: str) -> int | None:
    """Parse a valid Osiris course ID from various string formats."""
    raw_codes = course_code_str.split("|")
    for raw in raw_codes:
        clean = raw.strip()
        if "-" in clean:
            parts = clean.split("-")
            for part in parts:
                if len(part) == OSIRIS_COURSE_CODE_LENGTH and part.isdigit():
                    return int(part)
        elif clean.isdigit():
            return int(clean)
    return None


async def _enrich_person_and_link(
    name: str,
    course: Any,
    scraper: OsirisScraperService,
    contacts: list[str],
):
    """Enrich a person from Osiris and link them to a course."""
    from apps.core.models import CourseEmployee, Faculty, Organization, Person

    p_data = await scraper.fetch_person_data(name)
    if not p_data:
        return

    person, _ = await Person.objects.aupdate_or_create(
        input_name=name,
        defaults={
            "main_name": p_data.get("main_name"),
            "email": p_data.get("email"),
            "people_page_url": p_data.get("people_page_url"),
            "is_verified": True,
        },
    )

    parent_org = None
    full_abbr_parts = []
    for i, org_data in enumerate(p_data.get("orgs", [])):
        org_name = org_data.get("name")
        org_abbr = org_data.get("abbr")
        if not org_name or not org_abbr:
            continue

        level = 0 if org_abbr == "UT" else (1 if i == 1 else i)
        full_abbr_parts.append(org_abbr)
        full_abbr = "-".join(full_abbr_parts)

        defaults = {"name": org_name, "hierarchy_level": level, "parent": parent_org}

        if level == 1:
            org_obj, _ = await Faculty.objects.aupdate_or_create(
                abbreviation=org_abbr, full_abbreviation=full_abbr, defaults=defaults
            )
            person.faculty = org_obj
        else:
            org_obj, _ = await Organization.objects.aupdate_or_create(
                abbreviation=org_abbr, full_abbreviation=full_abbr, defaults=defaults
            )

        await person.orgs.aadd(org_obj)
        parent_org = org_obj

    await person.asave()

    role = "contacts" if name in contacts else "teachers"
    await CourseEmployee.objects.filter(course=course, person=person).adelete()
    await CourseEmployee.objects.aupdate_or_create(
        course=course, person=person, defaults={"role": role}
    )


async def _enrich_from_osiris(
    item: CopyrightItem, scraper: OsirisScraperService
) -> tuple[bool, list[str]]:
    """Enrich item relations from Osiris data."""
    if not item.course_code:
        return True, []

    course_code_int = parse_course_id(item.course_code)
    if not course_code_int:
        logger.warning(f"Could not parse valid course ID from {item.course_code}")
        return True, []

    try:
        course_info = await scraper.fetch_course_details(course_code_int)
        if not course_info:
            return True, []

        from apps.core.models import Course, Faculty

        faculty = None
        if course_info.get("faculty_abbr"):
            faculty = await Faculty.objects.filter(
                abbreviation=course_info["faculty_abbr"]
            ).afirst()

        course, _ = await Course.objects.aupdate_or_create(
            cursuscode=course_code_int,
            defaults={
                "name": course_info.get("name") or "Unknown",
                "short_name": course_info.get("short_name"),
                "programme_text": course_info.get("programme"),
                "faculty": faculty,
                "internal_id": course_info.get("internal_id"),
                "year": safe_int(course_info.get("year")) or 2024,
            },
        )

        await item.courses.aadd(course)

        all_names = set(course_info.get("teachers", [])) | set(
            course_info.get("contacts", [])
        )
        for name in all_names:
            await _enrich_person_and_link(
                name, course, scraper, course_info.get("contacts", [])
            )

        return True, []

    except Exception as e:
        logger.exception(f"Error enriching course for item {item.material_id}")
        return False, [f"Course enrichment failed: {e!s}"]


async def _process_documents(item: CopyrightItem):
    """Handle PDF downloading and parsing for an item."""
    error_messages = []

    if item.url and "/files/" in item.url:
        try:
            await download_undownloaded_pdfs(limit=0)
        except Exception as e:
            logger.exception(f"Error downloading PDF for item {item.material_id}")
            error_messages.append(f"PDF Download failed: {e!s}")

    try:
        # Re-fetch item to see if document was attached by downloader
        item_re = await CopyrightItem.objects.aget(material_id=item.material_id)
        await parse_pdfs(filter_ids=[item_re.material_id])
    except Exception as e:
        logger.exception(f"Error parsing PDF for item {item.material_id}")
        error_messages.append(f"PDF Parsing failed: {e!s}")

    return error_messages


async def _update_batch_status(
    batch_id: int, enrichment_successful: bool, total_items: int
):
    """Update progress and status for an enrichment batch."""
    from django.db.models import F

    from apps.enrichment.models import EnrichmentBatch

    if enrichment_successful:
        await EnrichmentBatch.objects.filter(id=batch_id).aupdate(
            processed_items=F("processed_items") + 1
        )
    else:
        await EnrichmentBatch.objects.filter(id=batch_id).aupdate(
            failed_items=F("failed_items") + 1
        )

    # Check if batch is done
    updated_batch = await EnrichmentBatch.objects.aget(id=batch_id)
    if (
        updated_batch.processed_items + updated_batch.failed_items
        >= updated_batch.total_items
    ):
        updated_batch.status = EnrichmentBatch.Status.COMPLETED
        updated_batch.completed_at = timezone.now()
        await updated_batch.asave()


async def _finalize_enrichment(
    item: CopyrightItem,
    enrichment_successful: bool,
    error_messages: list[str],
    result_id: int | None = None,
    batch_id: int | None = None,
):
    """Save final state of item and enrichment result."""
    from apps.enrichment.models import EnrichmentResult

    # Re-fetch item for final snapshot
    item = await CopyrightItem.objects.select_related("document").aget(
        material_id=item.material_id
    )
    data_after = await _get_item_snapshot(item)

    item.enrichment_status = (
        EnrichmentStatus.COMPLETED if enrichment_successful else EnrichmentStatus.FAILED
    )
    item.last_enrichment_attempt = timezone.now()
    await item.asave(update_fields=["enrichment_status", "last_enrichment_attempt"])

    if result_id:
        result = await EnrichmentResult.objects.filter(id=result_id).afirst()
        if result:
            result.status = (
                EnrichmentResult.Status.SUCCESS
                if enrichment_successful
                else EnrichmentResult.Status.FAILURE
            )
            result.data_after = data_after
            result.error_log = "\n".join(error_messages)
            await result.asave()

    if batch_id:
        await _update_batch_status(batch_id, enrichment_successful, item.material_id)


@task
async def enrich_item(
    item_id: int, batch_id: int | None = None, result_id: int | None = None
):
    """Enrich a single item with Osiris data and download PDF."""
    from apps.enrichment.models import EnrichmentResult

    try:
        item = await CopyrightItem.objects.select_related("document").aget(
            material_id=item_id
        )

        if result_id:
            result = await EnrichmentResult.objects.filter(id=result_id).afirst()
            if result:
                result.data_before = await _get_item_snapshot(item)
                await result.asave(update_fields=["data_before"])

        item.enrichment_status = EnrichmentStatus.RUNNING
        await item.asave(update_fields=["enrichment_status"])

        enrichment_successful = True
        error_messages = []

        async with OsirisScraperService() as scraper:
            success, osiris_errors = await _enrich_from_osiris(item, scraper)
            if not success:
                enrichment_successful = False
                error_messages.extend(osiris_errors)

            doc_errors = await _process_documents(item)
            error_messages.extend(doc_errors)

        await _finalize_enrichment(
            item, enrichment_successful, error_messages, result_id, batch_id
        )

    except Exception as e:
        logger.exception(f"Critical error in enrich_item for {item_id}")
        try:
            item = await CopyrightItem.objects.aget(material_id=item_id)
            item.enrichment_status = EnrichmentStatus.FAILED
            await item.asave(update_fields=["enrichment_status"])
        except Exception as inner_e:
            logger.error(f"Failed to update error status for item {item_id}: {inner_e}")

        if result_id:
            res = await EnrichmentResult.objects.filter(id=result_id).afirst()
            if res:
                res.status = EnrichmentResult.Status.FAILURE
                res.error_log = f"Critical error: {e!s}"
                await res.asave()


def trigger_batch_enrichment(batch_id: int):
    """Trigger enrichment for all items in an ingestion batch."""
    from apps.enrichment.models import EnrichmentBatch, EnrichmentResult

    logger.info(f"Triggering enrichment for ingestion batch {batch_id}")
    items = CopyrightItem.objects.filter(change_logs__batch_id=batch_id).distinct()
    item_ids = list(items.values_list("material_id", flat=True))

    if not item_ids:
        return

    # Create tracked batch
    e_batch = EnrichmentBatch.objects.create(
        source=EnrichmentBatch.Source.QLIK_BATCH,
        total_items=len(item_ids),
        status=EnrichmentBatch.Status.RUNNING,
        started_at=timezone.now(),
        metadata={"ingestion_batch_id": batch_id},
    )

    for material_id in item_ids:
        res = EnrichmentResult.objects.create(
            item_id=material_id, batch=e_batch, status=EnrichmentResult.Status.PENDING
        )
        enrich_item.enqueue(material_id, batch_id=e_batch.id, result_id=res.id)
