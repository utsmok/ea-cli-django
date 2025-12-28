"""
Views for Steps 1 & 2: Ingest Qlik Export and Ingest Faculty Sheet.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET


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
