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
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.core.models import CopyrightItem


def _parse_item_ids(item_ids_str: list[str]) -> tuple[list[int] | None, str | None]:
    """
    Parse and validate item IDs from request.

    Returns:
        Tuple of (parsed_ids, error_message). If successful, error_message is None.
    """
    try:
        return [int(i) for i in item_ids_str], None
    except (ValueError, TypeError):
        return None, "Invalid item IDs"


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
    from datetime import timedelta

    from django.utils import timezone

    from apps.ingest.models import IngestionBatch

    # Get statistics
    total_batches = IngestionBatch.objects.count()

    # Recent Qlik batches (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    qlik_batches = IngestionBatch.objects.filter(
        source_type=IngestionBatch.SourceType.QLIK, uploaded_at__gte=thirty_days_ago
    ).count()

    # Success rate
    total_qlik = IngestionBatch.objects.filter(
        source_type=IngestionBatch.SourceType.QLIK
    ).count()
    if total_qlik > 0:
        completed_batches = IngestionBatch.objects.filter(
            source_type=IngestionBatch.SourceType.QLIK,
            status__in=[IngestionBatch.Status.COMPLETED, IngestionBatch.Status.PARTIAL],
        ).count()
        success_rate = int((completed_batches / total_qlik) * 100)
    else:
        success_rate = 0

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
    from datetime import timedelta

    from django.db.models import Sum
    from django.utils import timezone

    from apps.ingest.models import IngestionBatch

    # Get statistics
    total_batches = IngestionBatch.objects.count()

    # Recent faculty batches (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    faculty_batches = IngestionBatch.objects.filter(
        source_type=IngestionBatch.SourceType.FACULTY, uploaded_at__gte=thirty_days_ago
    ).count()

    # Total items updated from faculty sheets
    total_updated = (
        IngestionBatch.objects.filter(
            source_type=IngestionBatch.SourceType.FACULTY
        ).aggregate(Sum("items_updated"))["items_updated__sum"]
        or 0
    )

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


# ============================================================================
# Step 4: Enrich from People Pages
# ============================================================================


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
    items = CopyrightItem.objects.filter(url__contains="/files/").order_by(
        "-created_at"
    )[:100]

    # Count items by document status
    total_items = CopyrightItem.objects.count()
    items_with_pdfs = CopyrightItem.objects.filter(document__isnull=False).count()
    items_without_pdfs = total_items - items_with_pdfs
    items_with_urls = (
        CopyrightItem.objects.filter(url__isnull=False).exclude(url="").count()
    )

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
    from apps.documents.tasks import check_and_download_pdfs

    # Get selected items
    item_ids = request.POST.getlist("item_ids")
    check_all = request.POST.get("check_all") == "true"

    if check_all:
        items = CopyrightItem.objects.filter(
            url__contains="/files/", document__isnull=True
        )
        item_ids = list(items.values_list("material_id", flat=True))
    elif not item_ids:
        return JsonResponse({"error": "No items selected"}, status=400)
    else:
        parsed_ids, error = _parse_item_ids(item_ids)
        if error:
            return JsonResponse({"error": error}, status=400)
        item_ids = parsed_ids

    # Trigger async Canvas check and download task
    check_and_download_pdfs.enqueue(item_ids)

    return JsonResponse(
        {
            "success": True,
            "total_items": len(item_ids),
            "message": f"Canvas file check and PDF download queued for {len(item_ids)} items",
        }
    )


@login_required
@require_GET
def pdf_canvas_status_status(request):
    """Get status of PDF Canvas check."""
    # Check extraction status of items

    total_pending = CopyrightItem.objects.filter(
        extraction_status__in=["download_pending", "extraction_pending"]
    ).count()

    total_downloaded = CopyrightItem.objects.filter(document__isnull=False).count()

    return JsonResponse(
        {
            "status": "running" if total_pending > 0 else "completed",
            "total_downloaded": total_downloaded,
            "pending": total_pending,
            "message": f"{'Download in progress' if total_pending > 0 else 'Download completed'}",
        }
    )


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
    items = (
        CopyrightItem.objects.filter(
            document__isnull=False, document__extracted_text__isnull=True
        )
        .select_related("document")
        .order_by("-created_at")[:100]
    )

    # Count items by parsing status
    total_with_pdfs = CopyrightItem.objects.filter(document__isnull=False).count()
    total_parsed = CopyrightItem.objects.filter(
        document__isnull=False, document__extracted_text__isnull=False
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
    from apps.documents.tasks import extract_pdfs_for_items

    # Get selected items
    item_ids = request.POST.getlist("item_ids")
    extract_all = request.POST.get("extract_all") == "true"

    if extract_all:
        items = CopyrightItem.objects.filter(
            document__isnull=False, document__extracted_text__isnull=True
        )
        item_ids = list(items.values_list("material_id", flat=True))
    elif not item_ids:
        return JsonResponse({"error": "No items selected"}, status=400)
    else:
        parsed_ids, error = _parse_item_ids(item_ids)
        if error:
            return JsonResponse({"error": error}, status=400)
        item_ids = parsed_ids

    # Trigger async extraction task
    extract_pdfs_for_items.enqueue(item_ids)

    return JsonResponse(
        {
            "success": True,
            "total_items": len(item_ids),
            "message": f"PDF extraction queued for {len(item_ids)} items",
        }
    )


@login_required
@require_GET
def pdf_extract_status(request):
    """Get status of PDF extraction."""
    # Check extraction status of items
    total_pending = CopyrightItem.objects.filter(
        extraction_status="extraction_pending"
    ).count()

    total_parsed = CopyrightItem.objects.filter(
        document__isnull=False, document__extracted_text__isnull=False
    ).count()

    total_unparsed = CopyrightItem.objects.filter(
        document__isnull=False, document__extracted_text__isnull=True
    ).count()

    return JsonResponse(
        {
            "status": "running" if total_pending > 0 else "completed",
            "total_parsed": total_parsed,
            "total_unparsed": total_unparsed,
            "pending": total_pending,
            "message": f"{'Extraction in progress' if total_pending > 0 else 'Extraction completed'}",
        }
    )


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
    - Download previously exported files
    """
    from django.conf import settings

    from apps.ingest.models import ExportHistory

    # Get statistics
    total_items = CopyrightItem.objects.count()

    # Count by workflow status
    from apps.core.models import Faculty, WorkflowStatus

    todo_count = CopyrightItem.objects.filter(
        workflow_status=WorkflowStatus.TODO
    ).count()
    in_progress_count = CopyrightItem.objects.filter(
        workflow_status=WorkflowStatus.IN_PROGRESS
    ).count()
    done_count = CopyrightItem.objects.filter(
        workflow_status=WorkflowStatus.DONE
    ).count()

    # Get faculties
    faculties = Faculty.objects.all()

    # Export path
    export_path = getattr(
        settings,
        "EXPORT_FACULTY_SHEETS_DIR",
        settings.PROJECT_ROOT / "exports" / "faculty_sheets",
    )

    # Recent exports (last 10)
    recent_exports = ExportHistory.objects.filter(
        status=ExportHistory.Status.COMPLETED
    ).order_by("-created_at")[:10]

    context = {
        "step_title": "Export Faculty Sheets",
        "step_description": "Generate Excel workbooks for faculty review and classification",
        "total_items": total_items,
        "todo_count": todo_count,
        "in_progress_count": in_progress_count,
        "done_count": done_count,
        "faculty_count": faculties.count(),
        "faculties": faculties,
        "export_path": export_path,
        "recent_exports": recent_exports,
    }

    return render(request, "steps/export_faculty.html", context)


@login_required
@require_POST
def run_export_faculty(request):
    """Trigger faculty sheet export for selected faculties."""
    from django.utils import timezone

    from apps.core.models import Faculty
    from apps.ingest.models import ExportHistory
    from apps.ingest.services.export import ExportService

    # Get selected faculties
    faculty_codes = request.POST.getlist("faculty_codes")
    export_all = request.POST.get("export_all") == "true"

    if export_all:
        faculty_codes = list(Faculty.objects.values_list("abbreviation", flat=True))
    elif not faculty_codes:
        return JsonResponse({"error": "No faculties selected"}, status=400)

    # Create export history record
    export_history = ExportHistory.objects.create(
        faculties=faculty_codes,
        export_all=export_all,
        status=ExportHistory.Status.RUNNING,
        started_at=timezone.now(),
        triggered_by=request.user,
        metadata={"source": "steps_ui"},
    )

    # Run export synchronously (could be made async in the future)
    try:
        export_service = ExportService()
        result = export_service.export_workflow_tree()

        # Extract data from result
        files_created = result.get("files", [])
        faculties = result.get("faculties", [])

        # Count total items exported
        from apps.core.models import CopyrightItem

        total_items = CopyrightItem.objects.count()

        # Update export history with results
        export_history.status = ExportHistory.Status.COMPLETED
        export_history.completed_at = timezone.now()
        export_history.total_items = total_items
        export_history.total_files = len(files_created)
        export_history.files_created = files_created
        export_history.output_dir = str(result.get("output_dir", ""))
        export_history.save()

        return JsonResponse(
            {
                "success": True,
                "export_id": export_history.id,
                "total_files": len(files_created),
                "total_items": total_items,
                "message": f"Export completed: {len(files_created)} files created for {len(faculties)} faculties",
            }
        )

    except Exception as e:
        export_history.status = ExportHistory.Status.FAILED
        export_history.error_message = str(e)
        export_history.completed_at = timezone.now()
        export_history.save()

        return JsonResponse(
            {
                "error": f"Export failed: {e}",
            },
            status=500,
        )


@login_required
@require_GET
def download_export_file(request, export_id: int, file_index: int):
    """Download a file from a previous export."""
    from apps.ingest.models import ExportHistory

    export = get_object_or_404(ExportHistory, id=export_id)

    if file_index < 0 or file_index >= len(export.files_created):
        return HttpResponse("File index out of range", status=400)

    file_path = export.files_created[file_index]

    try:
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            return HttpResponse("File not found", status=404)

        # Determine content type
        if file_path.endswith(".xlsx"):
            content_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        elif file_path.endswith(".csv"):
            content_type = "text/csv"
        elif file_path.endswith(".txt"):
            content_type = "text/plain"
        else:
            content_type = "application/octet-stream"

        # Serve the file

        with path.open("rb") as f:
            response = HttpResponse(f.read(), content_type=content_type)
            response["Content-Disposition"] = f'attachment; filename="{path.name}"'
            return response

    except Exception as e:
        return HttpResponse(f"Error serving file: {e}", status=500)
