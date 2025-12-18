from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from apps.core.models import CopyrightItem
from apps.enrichment.tasks import enrich_item


@require_POST
def trigger_item_enrichment(request, material_id):
    """Trigger enrichment for a single item (manual)."""
    item = get_object_or_404(CopyrightItem, material_id=material_id)

    # In a real environment, this should be a background task (e.g. Celery)
    # For this simplified implementation, we'll run it and return a status indicator
    import asyncio

    # Run async function in background if possible, or just run it
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(enrich_item(material_id))
        else:
            loop.run_until_complete(enrich_item(material_id))
    except Exception as e:
        # Fallback for thread/loop issues
        import threading
        def run_in_thread():
            asyncio.run(enrich_item(material_id))
        threading.Thread(target=run_in_thread).start()

    # Return the status partial for HTMX to swap
    return HttpResponse(
        f'<span class="badge badge-info animate-pulse" hx-get="/enrichment/item/{material_id}/status/" hx-trigger="load delay:2s" hx-swap="outerHTML">Running...</span>'
    )


def item_enrichment_status(request, material_id):
    """Return the enrichment status partial for an item."""
    item = get_object_or_404(CopyrightItem, material_id=material_id)

    status_classes = {
        "PENDING": "badge-ghost",
        "RUNNING": "badge-info animate-pulse",
        "COMPLETED": "badge-success",
        "FAILED": "badge-error",
    }

    status_class = status_classes.get(item.enrichment_status, "badge-ghost")

    # If completed, show a link to view/download if we have a document
    extra_html = ""
    if item.enrichment_status == "COMPLETED" and item.document:
        extra_html = f'<a href="{item.document.file.url}" class="ml-2 underline text-xs" target="_blank">View PDF</a>'

    if item.enrichment_status == "RUNNING":
         return HttpResponse(
            f'<span class="badge {status_class}" hx-get="/enrichment/item/{material_id}/status/" hx-trigger="load delay:2s" hx-swap="outerHTML">{item.enrichment_status}</span>'
        )

    return HttpResponse(
        f'<span class="badge {status_class}">{item.enrichment_status}</span>{extra_html}'
    )
