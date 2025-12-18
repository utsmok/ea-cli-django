from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.core.models import TimestampedModel


class EnrichmentJob(TimestampedModel):
    """
    Tracks a batch of items being enriched from Osiris or other sources.
    """

    class JobType(models.TextChoices):
        OSIRIS = "OSIRIS", _("Osiris Scraping")
        PEOPLE_PAGE = "PEOPLE_PAGE", _("People Page Scraping")
        CANVAS = "CANVAS", _("Canvas Download")

    job_type = models.CharField(max_length=50, choices=JobType.choices)
    items_processed = models.IntegerField(default=0)
    items_failed = models.IntegerField(default=0)
    errors = models.JSONField(null=True, blank=True, help_text="List of error messages")

    class Meta:
        verbose_name = "Enrichment Job"
        verbose_name_plural = "Enrichment Jobs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_job_type_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
