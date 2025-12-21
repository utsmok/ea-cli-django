"""
Views for the ingestion dashboard.

Provides a simple web interface for:
- Uploading Qlik exports and Faculty sheets
- Monitoring batch processing status
- Viewing batch history
- Downloading exports
"""

from typing import TYPE_CHECKING

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.ingest.models import IngestionBatch
from apps.ingest.services.export import ExportAbortedError, ExportService
from apps.ingest.tasks import process_batch, stage_batch

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile


@login_required
@require_http_methods(["GET"])
def dashboard(request):
    """Dashboard home page with recent batches."""
    recent_batches = IngestionBatch.objects.select_related("uploaded_by").order_by(
        "-uploaded_at"
    )[:20]

    stats = {
        "total_batches": IngestionBatch.objects.count(),
        "pending": IngestionBatch.objects.filter(
            status=IngestionBatch.Status.PENDING
        ).count(),
        "processing": IngestionBatch.objects.filter(
            status__in=[
                IngestionBatch.Status.STAGING,
                IngestionBatch.Status.PROCESSING,
            ]
        ).count(),
        "completed": IngestionBatch.objects.filter(
            status=IngestionBatch.Status.COMPLETED
        ).count(),
        "failed": IngestionBatch.objects.filter(
            status=IngestionBatch.Status.FAILED
        ).count(),
    }

    return render(
        request,
        "ingest/dashboard.html",
        {"recent_batches": recent_batches, "stats": stats},
    )


@login_required
@require_http_methods(["GET", "POST"])
def upload(request):
    """Upload a new file for ingestion."""
    if request.method == "POST":
        # Get uploaded file
        uploaded_file: UploadedFile | None = request.FILES.get("file")
        if not uploaded_file:
            messages.error(request, "No file was uploaded.")
            return redirect("ingest:upload")

        # Get source type and faculty code
        source_type = request.POST.get("source_type")
        faculty_code = request.POST.get("faculty_code", "").strip() or None

        # Validate source type
        if source_type not in [
            choice[0] for choice in IngestionBatch.SourceType.choices
        ]:
            messages.error(request, "Invalid source type.")
            return redirect("ingest:upload")

        # Validate faculty code for Faculty sheets
        if source_type == IngestionBatch.SourceType.FACULTY and not faculty_code:
            messages.error(request, "Faculty code is required for Faculty sheets.")
            return redirect("ingest:upload")

        # Create batch
        batch = IngestionBatch.objects.create(
            source_type=source_type,
            source_file=uploaded_file,
            uploaded_by=request.user,
            faculty_code=faculty_code,
        )

        # Auto-process option
        auto_process = request.POST.get("auto_process") == "on"
        if auto_process:
            stage_batch.enqueue(batch.id)
            messages.success(
                request,
                f"Batch #{batch.id} uploaded. Background processing started.",
            )
        else:
            messages.success(
                request,
                f"Batch #{batch.id} uploaded successfully. Ready for processing.",
            )

        return redirect("ingest:batch_detail", batch_id=batch.id)

    # GET request - show upload form
    return render(request, "ingest/upload.html")


@login_required
@require_http_methods(["GET"])
def batch_list(request):
    """List all batches with filtering."""
    batches = IngestionBatch.objects.select_related("uploaded_by").order_by(
        "-uploaded_at"
    )

    # Filter by status
    status_filter = request.GET.get("status")
    if status_filter:
        batches = batches.filter(status=status_filter)

    # Filter by source type
    source_type_filter = request.GET.get("source_type")
    if source_type_filter:
        batches = batches.filter(source_type=source_type_filter)

    # Filter by faculty
    faculty_filter = request.GET.get("faculty")
    if faculty_filter:
        batches = batches.filter(faculty_code=faculty_filter)

    return render(
        request,
        "ingest/batch_list.html",
        {
            "batches": batches[:100],  # Limit to 100 for performance
            "status_choices": IngestionBatch.Status.choices,
            "source_type_choices": IngestionBatch.SourceType.choices,
        },
    )


@login_required
@require_http_methods(["GET"])
def batch_detail(request, batch_id: int):
    """Show detailed information about a batch."""
    batch = get_object_or_404(
        IngestionBatch.objects.select_related("uploaded_by"), id=batch_id
    )

    # Get related entries (limited to avoid performance issues)
    qlik_entries = []
    faculty_entries = []

    if batch.source_type == IngestionBatch.SourceType.QLIK:
        qlik_entries = batch.qlik_entries.all()[:20]
    else:
        faculty_entries = batch.faculty_entries.all()[:20]

    processing_failures = batch.failures.all()[:20]

    return render(
        request,
        "ingest/batch_detail.html",
        {
            "batch": batch,
            "qlik_entries": qlik_entries,
            "faculty_entries": faculty_entries,
            "processing_failures": processing_failures,
        },
    )


@login_required
@require_http_methods(["GET"])
def batch_status_api(request, batch_id: int):
    """API endpoint for polling batch status."""
    batch = get_object_or_404(IngestionBatch, id=batch_id)

    return JsonResponse(
        {
            "id": batch.id,
            "status": batch.status,
            "progress": {
                "total_rows": batch.total_rows,
                "rows_staged": batch.rows_staged,
                "items_created": batch.items_created,
                "items_updated": batch.items_updated,
                "items_skipped": batch.items_skipped,
                "items_failed": batch.items_failed,
            },
            "error_message": batch.error_message,
            "started_at": batch.started_at.isoformat() if batch.started_at else None,
            "completed_at": (
                batch.completed_at.isoformat() if batch.completed_at else None
            ),
        }
    )


@login_required
@require_http_methods(["GET"])
def batch_status_partial(request, batch_id: int):
    """View to render the batch status partial for HTMX."""
    batch = get_object_or_404(IngestionBatch, id=batch_id)
    return render(request, "ingest/partials/batch_status.html", {"batch": batch})


@login_required
@require_http_methods(["POST"])
def batch_process(request, batch_id: int):
    """Manually trigger batch processing."""
    batch = get_object_or_404(IngestionBatch, id=batch_id)

    # Check if already processed
    if batch.status in [
        IngestionBatch.Status.COMPLETED,
        IngestionBatch.Status.PARTIAL,
    ]:
        messages.warning(request, f"Batch #{batch_id} has already been processed.")
        return redirect("ingest:batch_detail", batch_id=batch_id)

    try:
        # Stage if needed
        if batch.status == IngestionBatch.Status.PENDING:
            stage_batch.enqueue(batch_id)
            messages.success(
                request, f"Batch #{batch_id} staging started in background."
            )

        # Process if staged
        elif batch.status == IngestionBatch.Status.STAGED:
            process_batch.enqueue(batch_id)
            messages.success(
                request, f"Batch #{batch_id} processing started in background."
            )

        else:
            messages.warning(
                request,
                f"Batch #{batch_id} cannot be processed in current status: {batch.status}",
            )

    except Exception as e:
        messages.error(request, f"Error triggering batch processing: {e!s}")

    return redirect("ingest:batch_detail", batch_id=batch_id)


@login_required
@require_http_methods(["GET"])
def export_faculty_sheets(request):
    """Export faculty sheets to Excel."""
    faculty_code = request.GET.get("faculty")

    try:
        exporter = ExportService(faculty_abbr=faculty_code)
        result = exporter.export_workflow_tree()

        messages.success(
            request,
            f"Exported {len(result['files'])} files for {len(result['faculties'])} faculties to {result['output_dir']}.",
        )

    except ExportAbortedError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f"An unexpected error occurred during export: {e!s}")

    # Return to dashboard
    return redirect("ingest:dashboard")


@login_required
@require_http_methods(["GET"])
def download_export(request, faculty: str, filename: str):
    """Download an exported faculty sheet."""
    from pathlib import Path

    from django.conf import settings

    # Build path to export
    export_dir = getattr(
        settings,
        "EXPORT_FACULTY_SHEETS_DIR",
        settings.PROJECT_ROOT / "exports" / "faculty_sheets",
    )
    file_path = Path(export_dir) / faculty / filename

    # Security check: ensure file is within export directory
    if not file_path.resolve().is_relative_to(Path(export_dir).resolve()):
        raise Http404("Invalid file path")

    if not file_path.exists():
        raise Http404("File not found")

    return FileResponse(
        Path.open(file_path, "rb"),
        as_attachment=True,
        filename=filename,
    )
