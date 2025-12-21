from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimestampedModel


class EnrichmentBatch(TimestampedModel):
    """
    Tracks a group of items being enriched together.
    """

    class Source(models.TextChoices):
        QLIK_BATCH = "QLIK_BATCH", _("Qlik Batch")
        MANUAL_SINGLE = "MANUAL_SINGLE", _("Manual Single")
        MANUAL_BATCH = "MANUAL_BATCH", _("Manual Batch")

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        RUNNING = "RUNNING", _("Running")
        COMPLETED = "COMPLETED", _("Completed")
        FAILED = "FAILED", _("Failed")

    source = models.CharField(max_length=50, choices=Source.choices)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    total_items = models.IntegerField(default=0)
    processed_items = models.IntegerField(default=0)
    failed_items = models.IntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    metadata = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Batch {self.id} ({self.source}) - {self.status}"


class EnrichmentResult(TimestampedModel):
    """
    Tracks the result of enriching a single item within a batch.
    Stores 'before' and 'after' snapshots of relations for comparison.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        SUCCESS = "SUCCESS", _("Success")
        FAILURE = "FAILURE", _("Failure")

    item = models.ForeignKey(
        "core.CopyrightItem",
        on_delete=models.CASCADE,
        related_name="enrichment_results",
    )
    batch = models.ForeignKey(
        EnrichmentBatch, on_delete=models.CASCADE, related_name="results"
    )

    status = models.CharField(max_length=20, choices=Status.choices, db_index=True)
    error_log = models.TextField(null=True, blank=True)

    # Snapshots stores relations: { "courses": [...], "teachers": [...], "has_document": bool }
    data_before = models.JSONField(null=True, blank=True)
    data_after = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Result {self.id} - Item {self.item_id} ({self.status})"
