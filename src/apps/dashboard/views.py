"""
Dashboard views: Thin HTMX endpoints using service layer.

These views are intentionally simple - they:
1. Extract parameters from request
2. Call service layer
3. Render appropriate template
4. Return response

All business logic lives in services for testability.
"""

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.views.decorators.http import require_GET, require_POST
from loguru import logger

from apps.core.models import CopyrightItem

from .forms import WorkflowFilterForm
from .services.detail_service import ItemDetailService
from .services.query_service import (
    ItemQueryFilter,
    ItemQueryService,
)
from .services.update_service import ItemUpdateService


@login_required
@require_GET
def dashboard_index(request):
    """
    Main dashboard view with Excel-like table.

    Replaces card grid with dense data table for efficient classification.

    Features:
    - Workflow status tabs (Inbox/InProgress/Done/All)
    - Faculty filtering
    - Full-text search
    - Pagination
    - Inline editing
    """
    # Build filter from request parameters
    try:
        page = int(request.GET.get("page", 1))
        per_page = int(request.GET.get("per_page", 50))
    except (ValueError, TypeError):
        page = 1
        per_page = 50

    filters = ItemQueryFilter(
        workflow_status=request.GET.get("status", "ToDo"),  # Default to Inbox
        faculty_abbreviation=request.GET.get("faculty"),
        search_query=request.GET.get("search"),
        page=page,
        per_page=per_page,
    )

    # Fetch data via service
    query_service = ItemQueryService()
    result = query_service.get_paginated_items(filters)
    faculties = query_service.get_faculties()
    workflow_choices = query_service.get_workflow_choices()
    classification_choices = query_service.get_classification_choices()
    overnamestatus_choices = query_service.get_overnamestatus_choices()
    lengte_choices = query_service.get_lengte_choices()

    # Build form for rendering
    filter_form = WorkflowFilterForm(
        initial={
            "workflow_status": filters.workflow_status,
            "faculty": filters.faculty_abbreviation or "",
            "search": filters.search_query,
            "per_page": str(filters.per_page),
        }
    )

    context = {
        "items": result.items,
        "page_obj": result.page_obj,
        "total_count": result.total_count,
        "filter_counts": result.filter_counts,
        "faculties": faculties,
        "workflow_choices": workflow_choices,
        "classification_choices": classification_choices,
        "overnamestatus_choices": overnamestatus_choices,
        "lengte_choices": lengte_choices,
        "filter_form": filter_form,
        "current_filters": {
            "status": filters.workflow_status,
            "faculty": filters.faculty_abbreviation,
            "search": filters.search_query,
            "per_page": filters.per_page,
        },
    }

    # HTMX partial response
    if request.headers.get("HX-Request"):
        return TemplateResponse(request, "dashboard/_table.html", context)

    # Full page response
    return TemplateResponse(request, "dashboard/dashboard.html", context)


@login_required
@require_POST
def update_item_field(request, material_id: int):
    """
    Handle inline field updates via HTMX.

    Expects POST with:
    - field: Field name to update
    - value: New value

    Returns: Updated table row HTML with optional toast notification
    """
    item = get_object_or_404(CopyrightItem, pk=material_id)

    field_name = request.POST.get("field")
    value = request.POST.get("value", "")

    # Use service to perform update
    update_service = ItemUpdateService(user=request.user)
    result = update_service.update_field(item, field_name, value)

    if result.error:
        # Return error response with toast
        response = TemplateResponse(
            request,
            "dashboard/_error_cell.html",
            {"error": result.error, "material_id": material_id},
            status=400,
        )
        # Add error toast trigger
        response["HX-Trigger"] = json.dumps(
            {"show-toast": {"type": "error", "message": "Update failed"}}
        )
        return response

    # Build context for updated row
    query_service = ItemQueryService()
    context = {
        "item": result.updated_item,
        "workflow_choices": query_service.get_workflow_choices(),
        "classification_choices": query_service.get_classification_choices(),
        "overnamestatus_choices": query_service.get_overnamestatus_choices(),
        "lengte_choices": query_service.get_lengte_choices(),
        "current_filters": {
            "status": "",
            "faculty": "",
            "search": "",
        },
    }

    # Create response
    response = TemplateResponse(request, "dashboard/_table_row.html", context)

    # Add toast notification if workflow transitioned
    if result.workflow_transitioned:
        old_status = result.changes_made.get("workflow_status", {}).get("old")
        new_status = result.changes_made.get("workflow_status", {}).get("new")
        item_id = result.updated_item.material_id

        # Set HX-Trigger header with JSON payload
        response["HX-Trigger"] = json.dumps(
            {
                "show-toast": {
                    "type": "success",
                    "title": f"Item #{item_id}",
                    "message": f"Classification changed - Status: {old_status} → {new_status}",
                }
            }
        )

    return response


@login_required
@require_GET
def item_detail_panel(request, material_id: int):
    """
    Render split-panel detail view (right side).

    This is the first tier of the detail system - shows:
    - PDF preview
    - Basic course info
    - Quick classification fields
    """
    detail_service = ItemDetailService()
    item = detail_service.get_minimal_detail(material_id)

    context = {
        "item": item,
        "pdf_available": bool(item.document and item.document.file),
        "pdf_url": item.document.file.url if item.document else None,
    }

    return TemplateResponse(request, "dashboard/_detail_panel.html", context)


@login_required
@require_GET
def item_detail_modal(request, material_id: int):
    """
    Render full detail modal.

    Second tier - complete information:
    - All metadata
    - Enrichment history
    - Change logs
    - Related items
    - Navigation (prev/next)
    """
    detail_service = ItemDetailService()

    # Rebuild filters for navigation - handle "None" string values
    status = request.GET.get("status", "ToDo")
    faculty = request.GET.get("faculty", None)
    search = request.GET.get("search", None)

    # Convert string "None" to actual None
    if faculty == "None":
        faculty = None
    if search == "None":
        search = None

    filters = ItemQueryFilter(
        workflow_status=status,
        faculty_abbreviation=faculty,
        search_query=search,
    )

    data = detail_service.get_detail_data(material_id)
    prev_id, next_id = detail_service.get_navigation_ids(material_id, filters)

    # Get latest enrichment result to check for errors
    from apps.enrichment.models import EnrichmentResult

    latest_result = (
        EnrichmentResult.objects.filter(item__material_id=material_id)
        .order_by("-created_at")
        .first()
    )

    context = {
        "item": data.item,
        "courses": data.courses,
        "course_teachers": data.course_teachers,
        "pdf_available": data.pdf_available,
        "pdf_url": data.pdf_url,
        "enrichment_history": data.enrichment_history,
        "recent_changes": data.recent_changes,
        "related_items": data.related_items,
        "prev_id": prev_id,
        "next_id": next_id,
        "enrichment_result": latest_result,
        "current_filters": {
            "status": filters.workflow_status,
            "faculty": filters.faculty_abbreviation,
            "search": filters.search_query,
        },
    }

    response = TemplateResponse(request, "dashboard/_detail_modal.html", context)

    # Trigger enrichment if data is missing
    from apps.core.models import EnrichmentStatus
    from apps.enrichment.tasks import enrich_item

    needs_enrichment = (
        not data.pdf_available
        or not data.item.course_code
        or not data.item.count_students_registered
        or data.item.file_exists is None
    )

    # Check if enrichment is already running
    is_enriching = data.item.enrichment_status == EnrichmentStatus.RUNNING

    if needs_enrichment and not is_enriching:
        # Create EnrichmentResult to track errors first
        from django.utils import timezone

        from apps.enrichment.models import EnrichmentBatch, EnrichmentResult

        batch = EnrichmentBatch.objects.create(
            source=EnrichmentBatch.Source.MANUAL_SINGLE,
            total_items=1,
            status=EnrichmentBatch.Status.RUNNING,
            started_at=timezone.now(),
        )
        result = EnrichmentResult.objects.create(
            item=data.item, batch=batch, status=EnrichmentResult.Status.PENDING
        )

        # Enqueue enrichment task with result tracking
        try:
            enrich_item.enqueue(material_id, batch_id=batch.id, result_id=result.id)
            logger.info(
                f"Enqueued enrichment for item {material_id} (batch={batch.id}, result={result.id})"
            )

            # Only set status to RUNNING after successful enqueue (prevents race condition)
            data.item.enrichment_status = EnrichmentStatus.RUNNING
            data.item.save(update_fields=["enrichment_status"])

            # Re-render modal with enrichment_status = RUNNING (includes poller)
            context["item"] = data.item
            response = TemplateResponse(
                request, "dashboard/_detail_modal.html", context
            )
        except Exception as e:
            logger.error(f"Failed to enqueue enrichment for {material_id}: {e}")
            # If enqueue fails, do not set RUNNING status - keep as NOT_STARTED

    return response


@login_required
@require_GET
def item_enrichment_status(request, material_id: int):
    """
    Enrichment status endpoint using HTMX polling.

    While enrichment is RUNNING:
    - Returns HTTP 204 (HTMX keeps polling every 2s)
    - Very lightweight response

    When enrichment completes:
    - Returns the full updated modal content
    - Polling stops naturally (no poller div in response)

    HTMX docs: 204 does nothing but keeps polling, 286 stops polling.
    """
    from apps.core.models import EnrichmentStatus

    item = get_object_or_404(CopyrightItem, material_id=material_id)

    # If enrichment is still running, return 204 to keep polling
    if item.enrichment_status == EnrichmentStatus.RUNNING:
        logger.info(
            f"Item {material_id} enrichment still RUNNING, returning 204 to keep polling"
        )
        return HttpResponse(status=204)

    # Enrichment complete - return full updated modal content
    logger.info(f"Item {material_id} enrichment complete, returning full modal")
    detail_service = ItemDetailService()

    # Get filters from query params
    status = request.GET.get("status", "ToDo")
    faculty = request.GET.get("faculty", None)
    search = request.GET.get("search", None)

    if faculty == "None":
        faculty = None
    if search == "None":
        search = None

    filters = ItemQueryFilter(
        workflow_status=status,
        faculty_abbreviation=faculty,
        search_query=search,
    )

    data = detail_service.get_detail_data(material_id)
    prev_id, next_id = detail_service.get_navigation_ids(material_id, filters)

    # Get latest enrichment result to check for errors
    from apps.enrichment.models import EnrichmentResult

    latest_result = (
        EnrichmentResult.objects.filter(item__material_id=material_id)
        .order_by("-created_at")
        .first()
    )

    context = {
        "item": data.item,
        "courses": data.courses,
        "course_teachers": data.course_teachers,
        "pdf_available": data.pdf_available,
        "pdf_url": data.pdf_url,
        "enrichment_history": data.enrichment_history,
        "recent_changes": data.recent_changes,
        "related_items": data.related_items,
        "prev_id": prev_id,
        "next_id": next_id,
        "enrichment_result": latest_result,
        "current_filters": {
            "status": filters.workflow_status,
            "faculty": filters.faculty_abbreviation,
            "search": filters.search_query,
        },
    }

    return TemplateResponse(request, "dashboard/_detail_modal.html", context)


@login_required
@require_GET
def item_detail_page(request, material_id: int):
    """
    Dedicated detail page.

    Third tier - shareable URL for direct access.
    Same content as modal but as full page.
    """
    detail_service = ItemDetailService()
    data = detail_service.get_detail_data(material_id)

    query_service = ItemQueryService()

    context = {
        "item": data.item,
        "courses": data.courses,
        "course_teachers": data.course_teachers,
        "pdf_available": data.pdf_available,
        "pdf_url": data.pdf_url,
        "enrichment_history": data.enrichment_history,
        "recent_changes": data.recent_changes,
        "related_items": data.related_items,
        "workflow_choices": query_service.get_workflow_choices(),
        "classification_choices": query_service.get_classification_choices(),
    }

    return TemplateResponse(request, "dashboard/_detail_page.html", context)
