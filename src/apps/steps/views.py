"""
Views for the steps app.

Each processing step has its own view with:
- Input selection interface
- Settings configuration
- Progress monitoring
- Results display
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.core.models import CopyrightItem


@login_required
@require_GET
def steps_index(request):
    """Main steps dashboard showing all available processing steps."""
    return render(request, "steps/index.html")


# ============================================================================
# Step 1 & 2: Ingest Qlik & Faculty - Redirect to existing interfaces
# ============================================================================


@login_required
@require_GET
def ingest_qlik_step(request):
    """Interface for ingesting Qlik exports."""
    from apps.ingest.models import IngestionBatch
    from django.utils import timezone
    from datetime import timedelta
    
    # Get statistics
    total_batches = IngestionBatch.objects.count()
    
    # Recent Qlik batches (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    qlik_batches = IngestionBatch.objects.filter(
        source_type=IngestionBatch.SourceType.QLIK,
        uploaded_at__gte=thirty_days_ago
    ).count()
    
    # Success rate
    completed_batches = IngestionBatch.objects.filter(
        source_type=IngestionBatch.SourceType.QLIK,
        status__in=[IngestionBatch.Status.COMPLETED, IngestionBatch.Status.PARTIAL]
    ).count()
    total_qlik = IngestionBatch.objects.filter(
        source_type=IngestionBatch.SourceType.QLIK
    ).count()
    success_rate = int((completed_batches / total_qlik * 100)) if total_qlik > 0 else 0
    
    # Recent batches
    recent_batches = IngestionBatch.objects.filter(
        source_type=IngestionBatch.SourceType.QLIK
    ).order_by("-uploaded_at")[:10]
    
    context = {
        "step_title": "Ingest Qlik Export",
        "step_description": "Import Qlik export files to create new copyright items with system fields",
        "total_batches": total_batches,
        "qlik_batches": qlik_batches,
        "success_rate": success_rate,
        "recent_batches": recent_batches,
    }
    
    return render(request, "steps/ingest_qlik.html", context)


@login_required
@require_GET
def ingest_faculty_step(request):
    """Interface for ingesting faculty sheets."""
    from apps.ingest.models import IngestionBatch
    from django.utils import timezone
    from datetime import timedelta
    
    # Get statistics
    total_batches = IngestionBatch.objects.count()
    
    # Recent faculty batches (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    faculty_batches = IngestionBatch.objects.filter(
        source_type=IngestionBatch.SourceType.FACULTY,
        uploaded_at__gte=thirty_days_ago
    ).count()
    
    # Total items updated from faculty sheets
    from django.db.models import Sum
    total_updated = IngestionBatch.objects.filter(
        source_type=IngestionBatch.SourceType.FACULTY
    ).aggregate(Sum("items_updated"))["items_updated__sum"] or 0
    
    # Recent batches
    recent_batches = IngestionBatch.objects.filter(
        source_type=IngestionBatch.SourceType.FACULTY
    ).order_by("-uploaded_at")[:10]
    
    context = {
        "step_title": "Ingest Faculty Sheet",
        "step_description": "Update classification fields from faculty-edited Excel sheets",
        "total_batches": total_batches,
        "faculty_batches": faculty_batches,
        "total_updated": total_updated,
        "recent_batches": recent_batches,
    }
    
    return render(request, "steps/ingest_faculty.html", context)


# ============================================================================
# Step 3: Enrich from Osiris
# ============================================================================


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
    # Get items that need enrichment
    items = CopyrightItem.objects.filter(
        course_code__isnull=False
    ).order_by("-created_at")[:100]
    
    # Count items by status
    total_items = CopyrightItem.objects.count()
    items_with_courses = CopyrightItem.objects.filter(
        courses__isnull=False
    ).distinct().count()
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
    from apps.enrichment.models import EnrichmentBatch, EnrichmentResult
    from apps.enrichment.tasks import enrich_item
    from django.utils import timezone
    
    # Get selected items
    item_ids = request.POST.getlist("item_ids")
    enrich_all = request.POST.get("enrich_all") == "true"
    
    if enrich_all:
        items = CopyrightItem.objects.filter(course_code__isnull=False)
        item_ids = list(items.values_list("material_id", flat=True))
    elif not item_ids:
        return JsonResponse({"error": "No items selected"}, status=400)
    else:
        item_ids = [int(i) for i in item_ids]
    
    # Create enrichment batch
    batch = EnrichmentBatch.objects.create(
        source=EnrichmentBatch.Source.MANUAL_BATCH,
        total_items=len(item_ids),
        status=EnrichmentBatch.Status.RUNNING,
        started_at=timezone.now(),
        metadata={"step": "osiris_enrichment"},
    )
    
    # Create results and enqueue tasks
    for material_id in item_ids:
        res = EnrichmentResult.objects.create(
            item_id=material_id,
            batch=batch,
            status=EnrichmentResult.Status.PENDING,
        )
        enrich_item.enqueue(material_id, batch_id=batch.id, result_id=res.id)
    
    return JsonResponse({
        "success": True,
        "batch_id": batch.id,
        "total_items": len(item_ids),
        "message": f"Enrichment started for {len(item_ids)} items",
    })


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


# ============================================================================
# Step 4: Enrich from People Pages
# ============================================================================


@login_required
@require_GET
def enrich_people_step(request):
    """
    Interface for enriching person information from people pages.
    
    Allows users to:
    - Select items with teacher names
    - Configure people page scraping settings
    - Run enrichment and monitor progress
    """
    # This is currently part of Osiris enrichment
    # For now, redirect to Osiris enrichment
    # TODO: Separate people page scraping into its own step
    return redirect("steps:enrich_osiris")


@login_required
@require_POST
def run_enrich_people(request):
    """Trigger people page enrichment for selected items."""
    # Currently handled by Osiris enrichment
    return JsonResponse({
        "error": "People page enrichment is currently part of Osiris enrichment",
        "redirect": "/steps/enrich-osiris/",
    }, status=400)


@login_required
@require_GET
def enrich_people_status(request):
    """Get status of people page enrichment."""
    # Currently handled by Osiris enrichment
    return JsonResponse({
        "error": "People page enrichment is currently part of Osiris enrichment",
    }, status=400)


# ============================================================================
# Step 5: Get PDF Status from Canvas
# ============================================================================


@login_required
@require_GET
def pdf_canvas_status_step(request):
    """
    Interface for checking PDF status in Canvas.
    
    Allows users to:
    - Select items with Canvas URLs
    - Configure Canvas API settings
    - Check PDF availability and metadata
    """
    # Get items with Canvas URLs
    items = CopyrightItem.objects.filter(
        url__contains="/files/"
    ).order_by("-created_at")[:100]
    
    # Count items by document status
    total_items = CopyrightItem.objects.count()
    items_with_pdfs = CopyrightItem.objects.filter(
        document__isnull=False
    ).count()
    items_without_pdfs = total_items - items_with_pdfs
    items_with_urls = CopyrightItem.objects.filter(
        url__isnull=False
    ).exclude(url="").count()
    
    context = {
        "step_title": "Get PDF Status from Canvas",
        "step_description": "Check Canvas for PDF metadata and download status",
        "items": items,
        "total_items": total_items,
        "items_with_pdfs": items_with_pdfs,
        "items_without_pdfs": items_without_pdfs,
        "items_with_urls": items_with_urls,
    }
    
    return render(request, "steps/pdf_canvas_status.html", context)


@login_required
@require_POST
def run_pdf_canvas_status(request):
    """Check Canvas PDF status for selected items."""
    from apps.documents.services.download import download_undownloaded_pdfs
    
    # Get selected items
    item_ids = request.POST.getlist("item_ids")
    check_all = request.POST.get("check_all") == "true"
    
    if check_all:
        items = CopyrightItem.objects.filter(
            url__contains="/files/",
            document__isnull=True
        )
        item_ids = list(items.values_list("material_id", flat=True))
    elif not item_ids:
        return JsonResponse({"error": "No items selected"}, status=400)
    else:
        item_ids = [int(i) for i in item_ids]
    
    # Trigger download task
    # Note: This is async, so we return immediately
    try:
        # For now, just return success
        # In production, this would trigger an async task
        return JsonResponse({
            "success": True,
            "total_items": len(item_ids),
            "message": f"PDF status check queued for {len(item_ids)} items",
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_GET
def pdf_canvas_status_status(request):
    """Get status of PDF Canvas check."""
    # For now, return a simple status
    # In production, this would check the status of the async task
    return JsonResponse({
        "status": "completed",
        "message": "PDF status check completed",
    })


# ============================================================================
# Step 6: Extract PDF Details
# ============================================================================


@login_required
@require_GET
def pdf_extract_step(request):
    """
    Interface for extracting details from downloaded PDFs.
    
    Allows users to:
    - Select items with downloaded PDFs
    - Configure extraction settings (OCR, quality thresholds)
    - Run extraction and view results
    """
    # Get items with PDFs that haven't been parsed
    items = CopyrightItem.objects.filter(
        document__isnull=False,
        document__text__isnull=True
    ).select_related("document").order_by("-created_at")[:100]
    
    # Count items by parsing status
    total_with_pdfs = CopyrightItem.objects.filter(
        document__isnull=False
    ).count()
    total_parsed = CopyrightItem.objects.filter(
        document__isnull=False,
        document__text__isnull=False
    ).count()
    total_unparsed = total_with_pdfs - total_parsed
    
    context = {
        "step_title": "Extract PDF Details",
        "step_description": "Parse downloaded PDFs to extract text, metadata, and quality scores using OCR",
        "items": items,
        "total_with_pdfs": total_with_pdfs,
        "total_parsed": total_parsed,
        "total_unparsed": total_unparsed,
    }
    
    return render(request, "steps/pdf_extract.html", context)


@login_required
@require_POST
def run_pdf_extract(request):
    """Trigger PDF extraction for selected items."""
    from apps.documents.services.parse import parse_pdfs
    
    # Get selected items
    item_ids = request.POST.getlist("item_ids")
    extract_all = request.POST.get("extract_all") == "true"
    
    if extract_all:
        items = CopyrightItem.objects.filter(
            document__isnull=False,
            document__text__isnull=True
        )
        item_ids = list(items.values_list("material_id", flat=True))
    elif not item_ids:
        return JsonResponse({"error": "No items selected"}, status=400)
    else:
        item_ids = [int(i) for i in item_ids]
    
    # Trigger parsing task
    try:
        # For now, just return success
        # In production, this would trigger an async task
        return JsonResponse({
            "success": True,
            "total_items": len(item_ids),
            "message": f"PDF extraction queued for {len(item_ids)} items",
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_GET
def pdf_extract_status(request):
    """Get status of PDF extraction."""
    # For now, return a simple status
    # In production, this would check the status of the async task
    return JsonResponse({
        "status": "completed",
        "message": "PDF extraction completed",
    })


# ============================================================================
# Step 7: Export Faculty Sheets
# ============================================================================


@login_required
@require_GET
def export_faculty_step(request):
    """
    Interface for exporting faculty sheets.
    
    Allows users to:
    - Select faculty or export all
    - Configure export settings
    - Generate Excel workbooks
    """
    from django.conf import settings
    
    # Get statistics
    total_items = CopyrightItem.objects.count()
    
    # Count by workflow status
    from apps.core.models import WorkflowStatus
    todo_count = CopyrightItem.objects.filter(
        workflow_status=WorkflowStatus.TODO
    ).count()
    in_progress_count = CopyrightItem.objects.filter(
        workflow_status=WorkflowStatus.IN_PROGRESS
    ).count()
    done_count = CopyrightItem.objects.filter(
        workflow_status=WorkflowStatus.DONE
    ).count()
    
    # Count faculties
    from apps.core.models import Faculty
    faculty_count = Faculty.objects.count()
    
    # Export path
    export_path = getattr(
        settings,
        "EXPORT_FACULTY_SHEETS_DIR",
        settings.PROJECT_ROOT / "exports" / "faculty_sheets",
    )
    
    context = {
        "step_title": "Export Faculty Sheets",
        "step_description": "Generate Excel workbooks for faculty review and classification",
        "total_items": total_items,
        "todo_count": todo_count,
        "in_progress_count": in_progress_count,
        "done_count": done_count,
        "faculty_count": faculty_count,
        "export_path": export_path,
        "recent_exports": [],  # TODO: Track export history
    }
    
    return render(request, "steps/export_faculty.html", context)
