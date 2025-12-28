"""
Views for Steps 5 & 6: PDF Canvas Status and PDF Extract.
"""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from loguru import logger

from apps.core.models import CopyrightItem

from .helpers import _parse_item_ids


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
    logger.debug("Rendering PDF Canvas status step...")
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


@require_POST
async def run_pdf_canvas_status(request):
    if not (await request.auser()).is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=403)

    """Check Canvas PDF status for selected items."""
    from apps.documents.tasks import check_and_download_pdfs

    logger.debug(f"received POST data for run_pdf_canvas_status: {request.POST}")
    # Get selected items
    item_ids = request.POST.getlist("item_ids")
    check_all = request.POST.get("check_all") == "true"

    if check_all:
        items = CopyrightItem.objects.filter(
            url__contains="/files/", document__isnull=True
        )
        item_ids = [i async for i in items.values_list("material_id", flat=True)]

    elif not item_ids:
        return JsonResponse({"error": "No items selected"}, status=400)
    else:
        parsed_ids, error = _parse_item_ids(item_ids)
        if error:
            return JsonResponse({"error": error}, status=400)
        item_ids = parsed_ids

    # Trigger async Canvas check and download task
    logger.debug(
        f"Queueing Canvas file check and PDF download for {len(item_ids)} items"
    )
    await check_and_download_pdfs.aenqueue(item_ids)

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
    logger.debug("Checking PDF Canvas status...")

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
