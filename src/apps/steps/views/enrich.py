"""
Views for Steps 3 & 4: Enrich from Osiris and Enrich from People Pages.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.core.models import CopyrightItem

from .helpers import _parse_item_ids


@login_required
@require_GET
def enrich_osiris_step(request):
    """
    Interface for enriching items with Osiris data.

    Allows users to:
    - Select specific items or all items
    - Configure Osiris connection settings
    - Run enrichment and monitor progress
    """
    from django.db.models import Exists, OuterRef

    # Get items that need enrichment with has_courses annotation to avoid N+1
    items = (
        CopyrightItem.objects.filter(course_code__isnull=False)
        .annotate(
            has_courses=Exists(
                CopyrightItem.courses.through.objects.filter(
                    copyrightitem_id=OuterRef("pk")
                )
            )
        )
        .order_by("-created_at")[:100]
    )

    # Count items by status
    total_items = CopyrightItem.objects.count()
    items_with_courses = (
        CopyrightItem.objects.filter(courses__isnull=False).distinct().count()
    )
    items_without_courses = total_items - items_with_courses

    context = {
        "step_title": "Enrich from Osiris",
        "step_description": "Fetch course details, teachers, and program information from the Osiris system",
        "items": items,
        "total_items": total_items,
        "items_with_courses": items_with_courses,
        "items_without_courses": items_without_courses,
    }

    return render(request, "steps/enrich_osiris.html", context)


@login_required
@require_POST
def run_enrich_osiris(request):
    """Trigger Osiris enrichment for selected items."""
    from django.utils import timezone

    from apps.enrichment.models import EnrichmentBatch, EnrichmentResult
    from apps.enrichment.tasks import enrich_item

    # Get selected items
    item_ids = request.POST.getlist("item_ids")
    enrich_all = request.POST.get("enrich_all") == "true"

    if enrich_all:
        items = CopyrightItem.objects.filter(course_code__isnull=False)
        item_ids = list(items.values_list("material_id", flat=True))
    elif not item_ids:
        return JsonResponse({"error": "No items selected"}, status=400)
    else:
        parsed_ids, error = _parse_item_ids(item_ids)
        if error:
            return JsonResponse({"error": error}, status=400)
        item_ids = parsed_ids

    # Create enrichment batch
    batch = EnrichmentBatch.objects.create(
        source=EnrichmentBatch.Source.MANUAL_BATCH,
        total_items=len(item_ids),
        status=EnrichmentBatch.Status.RUNNING,
        started_at=timezone.now(),
        metadata={"step": "osiris_enrichment"},
    )

    # Bulk create results for better performance
    results = EnrichmentResult.objects.bulk_create(
        [
            EnrichmentResult(
                item_id=material_id,
                batch=batch,
                status=EnrichmentResult.Status.PENDING,
            )
            for material_id in item_ids
        ]
    )

    # Enqueue tasks
    for res in results:
        enrich_item.enqueue(res.item_id, batch_id=batch.id, result_id=res.id)

    return JsonResponse(
        {
            "success": True,
            "batch_id": batch.id,
            "total_items": len(item_ids),
            "message": f"Enrichment started for {len(item_ids)} items",
        }
    )


@login_required
@require_GET
def enrich_osiris_status(request):
    """Get status of Osiris enrichment batch."""
    from apps.enrichment.models import EnrichmentBatch

    batch_id = request.GET.get("batch_id")
    if not batch_id:
        return JsonResponse({"error": "No batch_id provided"}, status=400)

    batch = get_object_or_404(EnrichmentBatch, id=batch_id)

    # Calculate progress
    total = batch.total_items
    processed = batch.processed_items
    failed = batch.failed_items
    remaining = total - processed - failed
    progress_pct = int((processed + failed) / total * 100) if total > 0 else 0

    response = {
        "batch_id": batch.id,
        "status": batch.status,
        "total": total,
        "processed": processed,
        "failed": failed,
        "remaining": remaining,
        "progress_pct": progress_pct,
        "is_complete": batch.status == EnrichmentBatch.Status.COMPLETED,
    }

    return JsonResponse(response)


@login_required
@require_GET
def enrich_people_step(request):
    """
    Interface for enriching person information from people pages.

    Note: People page enrichment is integrated with Osiris enrichment
    (Step 3). Person scraping occurs automatically when items are enriched
    from Osiris, fetching:
    - Main name, email, people page URL
    - Organization hierarchy (faculty, departments)
    - Course/teacher relationships

    Use Step 3 (Enrich from Osiris) for both course and person enrichment.
    """
    messages.info(
        request,
        "People page enrichment is integrated with Osiris enrichment (Step 3). "
        "Person data is automatically fetched when enriching course information.",
    )
    return redirect("steps:enrich_osiris")


@login_required
@require_POST
def run_enrich_people(request):
    """Trigger people page enrichment for selected items."""
    # People page enrichment is integrated with Osiris enrichment
    # Redirect to Step 3 for both course and person enrichment
    return JsonResponse(
        {
            "error": "People page enrichment is integrated with Osiris enrichment (Step 3)",
            "redirect": reverse("steps:enrich_osiris"),
        },
        status=400,
    )


@login_required
@require_GET
def enrich_people_status(request):
    """Get status of people page enrichment."""
    # People page enrichment is integrated with Osiris enrichment
    return JsonResponse(
        {
            "error": "People page enrichment is integrated with Osiris enrichment (Step 3)",
        },
        status=400,
    )
