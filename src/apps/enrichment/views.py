from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.models import CopyrightItem
from apps.enrichment.models import EnrichmentBatch, EnrichmentResult
from apps.enrichment.tasks import enrich_item


@require_POST
def trigger_item_enrichment(request, material_id):
    """Trigger enrichment for a single item (manual)."""
    item = get_object_or_404(CopyrightItem, material_id=material_id)

    # Create tracked batch and result
    batch = EnrichmentBatch.objects.create(
        source=EnrichmentBatch.Source.MANUAL_SINGLE,
        total_items=1,
        status=EnrichmentBatch.Status.RUNNING,
        started_at=timezone.now(),
    )
    res = EnrichmentResult.objects.create(
        item=item, batch=batch, status=EnrichmentResult.Status.PENDING
    )

    # Enqueue task
    enrich_item.enqueue(material_id, batch_id=batch.id, result_id=res.id)

    # Return status with delay for HTMX
    return HttpResponse(
        f'<span class="badge badge-info animate-pulse" hx-get="/enrichment/item/{material_id}/status/" hx-trigger="load delay:2s" hx-swap="outerHTML">Running...</span>'
    )


@require_POST
def trigger_batch_enrichment_ui(request):
    """Trigger enrichment for all items currently in the system."""
    items = CopyrightItem.objects.all()
    item_ids = list(items.values_list("material_id", flat=True))

    if not item_ids:
        return HttpResponse("No items to enrich.")

    batch = EnrichmentBatch.objects.create(
        source=EnrichmentBatch.Source.MANUAL_BATCH,
        total_items=len(item_ids),
        status=EnrichmentBatch.Status.RUNNING,
        started_at=timezone.now(),
    )

    for material_id in item_ids:
        res = EnrichmentResult.objects.create(
            item_id=material_id, batch=batch, status=EnrichmentResult.Status.PENDING
        )
        enrich_item.enqueue(material_id, batch_id=batch.id, result_id=res.id)

    return HttpResponse(f"Enrichment started for {len(item_ids)} items.")


def item_enrichment_status(request, material_id):
    """Return the enrichment status partial for an item with detailed feedback."""
    item = get_object_or_404(CopyrightItem, material_id=material_id)
    latest_result = (
        EnrichmentResult.objects.filter(item=item).order_by("-created_at").first()
    )

    status_classes = {
        "PENDING": "badge-ghost",
        "RUNNING": "badge-info animate-pulse",
        "COMPLETED": "badge-success",
        "FAILED": "badge-error",
    }

    status_class = status_classes.get(item.enrichment_status, "badge-ghost")
    content = item.enrichment_status
    tooltip = ""

    if item.enrichment_status == "COMPLETED" and latest_result:
        # Generate summary of what was added
        before = latest_result.data_before or {}
        after = latest_result.data_after or {}

        diffs = []

        # Courses diff
        before_courses = {c["code"] for c in before.get("courses", [])}
        after_courses = {c["code"]: c["name"] for c in after.get("courses", [])}
        new_courses = [
            after_courses[code] for code in after_courses if code not in before_courses
        ]
        if new_courses:
            diffs.append(f"Linked: {', '.join(new_courses)}")

        # Teachers diff
        before_teachers = set(before.get("teachers", []))
        after_teachers = set(after.get("teachers", []))
        new_teachers = after_teachers - before_teachers
        if new_teachers:
            diffs.append(f"Found: {', '.join(new_teachers)}")

        # PDF diff
        if not before.get("has_document") and after.get("has_document"):
            diffs.append("PDF Attached")

        if diffs:
            tooltip = " | ".join(diffs)
            content = "Enriched"

    elif item.enrichment_status == "FAILED" and latest_result:
        tooltip = latest_result.error_log or "Unknown error"

    # HTMX Polling for running state
    hx_attrs = ""
    if item.enrichment_status == "RUNNING":
        hx_attrs = f'hx-get="/enrichment/item/{material_id}/status/" hx-trigger="load delay:3s" hx-swap="outerHTML"'

    # View PDF link
    extra_html = ""
    if item.enrichment_status == "COMPLETED" and item.document:
        extra_html = f'<a href="{item.document.file.url}" class="ml-2 underline text-xs" target="_blank">View PDF</a>'

    # Real-time Enriched Date OOB Swap
    oob_date = ""
    if item.enrichment_status == "COMPLETED" and item.last_enrichment_attempt:
        formatted_date = item.last_enrichment_attempt.strftime("%Y-%m-%d %H:%M")
        oob_date = (
            f'<p id="enriched-date-{material_id}" hx-swap-oob="outerHTML">'
            f'<span class="font-semibold" title="Last checked">Enriched:</span> {formatted_date}'
            "</p>"
        )

    return HttpResponse(
        f'<span class="badge {status_class}" {hx_attrs} title="{tooltip}">{content}</span>{extra_html}{oob_date}'
    )
