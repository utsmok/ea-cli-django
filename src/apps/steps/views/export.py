"""
Views for Step 7: Export Faculty Sheets.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from apps.core.models import CopyrightItem


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
        from django.http import JsonResponse

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

        from django.http import JsonResponse

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

        from django.http import JsonResponse

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
