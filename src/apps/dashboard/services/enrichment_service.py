from django.utils import timezone
from loguru import logger

from apps.core.models import EnrichmentStatus
from apps.enrichment.models import EnrichmentBatch, EnrichmentResult
from apps.enrichment.tasks import enrich_item


class DashboardEnrichmentService:
    """
    Service to handle enrichment operations for the dashboard.
    Encapsulates logic for fetching results and triggering manual enrichment.
    """

    def get_latest_result(self, material_id: int) -> EnrichmentResult | None:
        """Get the most recent enrichment result for an item."""
        return (
            EnrichmentResult.objects.filter(item__material_id=material_id)
            .order_by("-created_at")
            .first()
        )

    def trigger_enrichment_if_needed(self, item) -> bool:
        """
        Trigger enrichment for a single item if required.

        Checks if enrichment is needed (missing checks) and not already running.
        If triggered, updates item status and returns True.
        """
        # Logic copied from views.py - defining "needs enrichment"
        needs_enrichment = (
            not (item.document and item.document.file)  # pdf_available check proxy
            or not item.course_code
            or not item.count_students_registered
            or item.file_exists is None
        )

        is_enriching = item.enrichment_status == EnrichmentStatus.RUNNING

        if needs_enrichment and not is_enriching:
            return self._enqueue_enrichment(item)

        return False

    def _enqueue_enrichment(self, item) -> bool:
        """Internal method to create batch/result and enqueue task."""
        try:
            # Create EnrichmentResult to track errors first
            batch = EnrichmentBatch.objects.create(
                source=EnrichmentBatch.Source.MANUAL_SINGLE,
                total_items=1,
                status=EnrichmentBatch.Status.RUNNING,
                started_at=timezone.now(),
            )
            result = EnrichmentResult.objects.create(
                item=item,
                batch=batch,
                status=EnrichmentResult.Status.PENDING
            )

            # Enqueue enrichment task with result tracking
            enrich_item.enqueue(item.material_id, batch_id=batch.id, result_id=result.id)
            logger.info(
                f"Enqueued enrichment for item {item.material_id} (batch={batch.id}, result={result.id})"
            )

            # Only set status to RUNNING after successful enqueue (prevents race condition)
            item.enrichment_status = EnrichmentStatus.RUNNING
            item.save(update_fields=["enrichment_status"])

            return True

        except Exception as e:
            logger.error(f"Failed to enqueue enrichment for {item.material_id}: {e}")
            return False
