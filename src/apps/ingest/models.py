from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class IngestionBatch(models.Model):
    """
    Tracks a single file ingestion operation.

    One batch = one uploaded file (either Qlik export or Faculty sheet).
    Maintains complete audit trail of ingestion process.
    """

    class SourceType(models.TextChoices):
        QLIK = "QLIK", _("Qlik Export")
        FACULTY = "FACULTY", _("Faculty Sheet")

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending Processing")
        STAGING = "STAGING", _("Staging Data")
        STAGED = "STAGED", _("Data Staged")
        PROCESSING = "PROCESSING", _("Processing Items")
        COMPLETED = "COMPLETED", _("Completed Successfully")
        FAILED = "FAILED", _("Failed with Errors")
        PARTIAL = "PARTIAL", _("Partially Completed")

    # Identity & Source
    source_type = models.CharField(
        max_length=20,
        choices=SourceType.choices,
        help_text="Type of data source (Qlik or Faculty)",
    )
    source_file = models.FileField(
        upload_to="ingestion_batches/%Y/%m/%d/", help_text="Original uploaded file"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_batches",
        help_text="User who uploaded this file",
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True, help_text="When file was uploaded"
    )

    # Processing State
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    started_at = models.DateTimeField(
        null=True, blank=True, help_text="When processing started"
    )
    completed_at = models.DateTimeField(
        null=True, blank=True, help_text="When processing finished"
    )

    # Statistics
    total_rows = models.IntegerField(default=0, help_text="Total rows in source file")
    rows_staged = models.IntegerField(default=0, help_text="Rows successfully staged")
    items_created = models.IntegerField(
        default=0, help_text="New CopyrightItems created"
    )
    items_updated = models.IntegerField(
        default=0, help_text="Existing CopyrightItems updated"
    )
    items_skipped = models.IntegerField(
        default=0, help_text="Items skipped (no changes)"
    )
    items_failed = models.IntegerField(
        default=0, help_text="Items that failed processing"
    )

    # Error Tracking
    error_message = models.TextField(
        null=True, blank=True, help_text="Top-level error if batch failed"
    )

    # Faculty-specific field (only for Faculty sheets)
    faculty_code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="Faculty abbreviation (e.g., 'EEMCS') for Faculty sheets",
    )

    class Meta:
        db_table = "ingest_batches"
        verbose_name = "Ingestion Batch"
        verbose_name_plural = "Ingestion Batches"
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["status", "source_type"]),
            models.Index(fields=["uploaded_by", "uploaded_at"]),
        ]

    def __str__(self):
        return f"{self.source_type} - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')} ({self.status})"

    @property
    def duration(self):
        """Calculate processing duration if completed."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


class FacultyEntry(models.Model):
    """
    Staging table for Faculty sheet rows.

    Stores standardized data from Faculty Excel uploads.
    Contains ONLY human-managed fields (classification, workflow_status, remarks, scope).
    """

    batch = models.ForeignKey(
        IngestionBatch,
        on_delete=models.CASCADE,
        related_name="faculty_entries",
        help_text="Which ingestion batch this entry belongs to",
    )

    # Primary identifier (must match existing item)
    material_id = models.BigIntegerField(
        db_index=True, help_text="Material ID (must exist in CopyrightItem)"
    )

    # Human-managed fields from Faculty sheet
    workflow_status = models.CharField(max_length=50, null=True, blank=True)
    classification = models.CharField(max_length=100, null=True, blank=True)
    v2_manual_classification = models.CharField(max_length=100, null=True, blank=True)
    v2_overnamestatus = models.CharField(max_length=100, null=True, blank=True)
    v2_lengte = models.CharField(max_length=50, null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    scope = models.CharField(max_length=50, null=True, blank=True)
    manual_identifier = models.CharField(max_length=2048, null=True, blank=True)
    manual_classification = models.CharField(max_length=2048, null=True, blank=True)

    # Processing state
    processed = models.BooleanField(
        default=False, db_index=True, help_text="Whether this entry has been processed"
    )
    processed_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    row_number = models.IntegerField(
        help_text="Row number in original Excel file (for error reporting)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ingest_faculty_entries"
        verbose_name = "Faculty Entry"
        verbose_name_plural = "Faculty Entries"
        ordering = ["batch", "row_number"]
        indexes = [
            models.Index(fields=["batch", "processed"]),
            models.Index(fields=["material_id"]),
        ]

    def __str__(self):
        return f"Faculty Entry {self.material_id} (Row {self.row_number})"


class QlikEntry(models.Model):
    """
    Staging table for Qlik export rows.

    Stores standardized data from Qlik/CRC system exports.
    Contains ALL system-managed fields (student counts, status, metadata, etc.).
    """

    batch = models.ForeignKey(
        IngestionBatch,
        on_delete=models.CASCADE,
        related_name="qlik_entries",
        help_text="Which ingestion batch this entry belongs to",
    )

    # Primary identifier
    material_id = models.BigIntegerField(
        db_index=True, help_text="Material ID from Qlik"
    )

    # System-managed fields from Qlik
    filename = models.CharField(max_length=2048, null=True, blank=True)
    filehash = models.CharField(max_length=255, null=True, blank=True)
    filetype = models.CharField(max_length=50, null=True, blank=True)
    url = models.URLField(max_length=2048, null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True)

    title = models.CharField(max_length=2048, null=True, blank=True)
    author = models.CharField(max_length=2048, null=True, blank=True)
    publisher = models.CharField(max_length=2048, null=True, blank=True)

    period = models.CharField(max_length=50, null=True, blank=True)
    department = models.CharField(max_length=2048, null=True, blank=True)
    course_code = models.CharField(max_length=2048, null=True, blank=True)
    course_name = models.CharField(max_length=2048, null=True, blank=True)

    isbn = models.CharField(max_length=255, null=True, blank=True)
    doi = models.CharField(max_length=255, null=True, blank=True)
    owner = models.CharField(max_length=2048, null=True, blank=True)
    in_collection = models.BooleanField(null=True, blank=True)

    # Metrics
    picturecount = models.IntegerField(default=0)
    reliability = models.IntegerField(default=0)
    pages_x_students = models.IntegerField(default=0)
    count_students_registered = models.IntegerField(default=0)
    pagecount = models.IntegerField(default=0)
    wordcount = models.IntegerField(default=0)

    # Canvas metadata
    canvas_course_id = models.BigIntegerField(null=True, blank=True)

    # Infringement analysis
    infringement = models.CharField(max_length=50, null=True, blank=True)
    possible_fine = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    # ML and human-input fields that may be present in Qlik data
    ml_classification = models.CharField(max_length=100, null=True, blank=True)
    last_canvas_check = models.DateTimeField(null=True, blank=True)
    manual_classification = models.CharField(max_length=2048, null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    scope = models.CharField(max_length=50, null=True, blank=True)
    auditor = models.CharField(max_length=2048, null=True, blank=True)
    last_change = models.DateTimeField(null=True, blank=True)

    # Processing state
    processed = models.BooleanField(
        default=False, db_index=True, help_text="Whether this entry has been processed"
    )
    processed_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    row_number = models.IntegerField(
        help_text="Row number in original Excel file (for error reporting)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ingest_qlik_entries"
        verbose_name = "Qlik Entry"
        verbose_name_plural = "Qlik Entries"
        ordering = ["batch", "row_number"]
        indexes = [
            models.Index(fields=["batch", "processed"]),
            models.Index(fields=["material_id"]),
        ]

    def __str__(self):
        return f"Qlik Entry {self.material_id} (Row {self.row_number})"


class ProcessingFailure(models.Model):
    """
    Records individual item processing failures for debugging.

    When an item fails to process (validation error, constraint violation, etc.),
    record the details here for inspection and retry.
    """

    batch = models.ForeignKey(
        IngestionBatch,
        on_delete=models.CASCADE,
        related_name="failures",
        help_text="Which batch this failure occurred in",
    )

    material_id = models.BigIntegerField(
        null=True, blank=True, help_text="Material ID if known"
    )

    row_number = models.IntegerField(help_text="Row number in source file")

    error_type = models.CharField(
        max_length=100,
        help_text="Type of error (e.g., 'ValidationError', 'IntegrityError')",
    )

    error_message = models.TextField(help_text="Detailed error message")

    row_data = models.JSONField(help_text="Raw row data that caused the failure")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ingest_failures"
        verbose_name = "Processing Failure"
        verbose_name_plural = "Processing Failures"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["batch", "created_at"]),
            models.Index(fields=["error_type"]),
        ]

    def __str__(self):
        return f"{self.error_type} - Row {self.row_number} (import from file {self.batch.source_file})"
