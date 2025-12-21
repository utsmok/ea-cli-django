from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimestampedModel


class EntityTypes(models.TextChoices):
    PERSON = "Person", _("Person")
    ORG = "Organization", _("Organization")
    DATE = "Date", _("Date")
    LOCATION = "Location", _("Location")
    OTHER = "Other", _("Other")


class PDFCanvasMetadata(TimestampedModel):
    """Metadata about a PDF file as retrieved from Canvas."""

    uuid = models.CharField(max_length=255)
    folder_id = models.BigIntegerField(null=True, blank=True)
    display_name = models.CharField(max_length=2048)
    filename = models.CharField(max_length=2048)
    upload_status = models.CharField(max_length=255)
    content_type = models.CharField(max_length=255)
    mime_class = models.CharField(max_length=255)
    category = models.CharField(max_length=255)
    download_url = models.CharField(max_length=2048)
    size = models.BigIntegerField()  # in bytes
    thumbnail_url = models.CharField(max_length=2048, null=True, blank=True)

    canvas_created_at = models.DateTimeField()
    canvas_updated_at = models.DateTimeField()
    canvas_modified_at = models.DateTimeField(null=True, blank=True)

    locked = models.BooleanField()
    hidden = models.BooleanField()
    lock_at = models.DateTimeField(null=True, blank=True)
    unlock_at = models.DateTimeField(null=True, blank=True)
    visibility_level = models.CharField(max_length=255)

    user_id = models.BigIntegerField(null=True, blank=True)
    user_anonymous_id = models.CharField(max_length=255, null=True, blank=True)
    user_display_name = models.CharField(max_length=2048, null=True, blank=True)
    user_avatar_image_url = models.CharField(max_length=2048, null=True, blank=True)
    user_html_url = models.CharField(max_length=2048, null=True, blank=True)
    user_pronouns = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name_plural = "PDF Canvas Metadata"


class PDFText(TimestampedModel):
    """Extracted text from a PDF file."""

    extracted_text = models.TextField(null=True, blank=True)
    num_pages = models.IntegerField(null=True, blank=True)
    text_quality = models.FloatField(default=0)
    is_ocr = models.BooleanField(default=False)

    # Language detection
    detected_language = models.CharField(max_length=50, null=True, blank=True)

    # Keywords extracted by YAKE/RAKE
    extracted_keywords = models.JSONField(null=True, blank=True)

    # Chunks with embeddings (stored as JSON until pgvector is available)
    # Format: [{"content": "...", "embedding": [...], "start": 0, "end": 512}, ...]
    chunks_with_embeddings = models.JSONField(null=True, blank=True)


class Entity(TimestampedModel):
    """Extracted entity from a PDF file."""

    label = models.CharField(max_length=255)
    raw_text = models.CharField(max_length=2048)
    canonical_form = models.CharField(max_length=2048, null=True, blank=True)
    recognized = models.BooleanField(default=False)
    recognition_type = models.CharField(max_length=50, choices=EntityTypes.choices)
    confidence = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Entities"


class Document(TimestampedModel):
    """
    Data for a document file (usually PDF).
    Multiple CopyrightItems can point to a single Document (deduplication).
    """

    canvas_metadata = models.OneToOneField(
        PDFCanvasMetadata, on_delete=models.CASCADE, related_name="pdf"
    )

    file = models.FileField(upload_to="downloads/%Y/%m/", null=True, blank=True)
    filehash = models.CharField(max_length=255, unique=True, db_index=True)
    original_url = models.URLField(max_length=2048, null=True, blank=True)

    filename = models.CharField(max_length=2048, null=True, blank=True)

    # Metadata fields
    author = models.CharField(max_length=2048, null=True, blank=True)
    title = models.CharField(max_length=2048, null=True, blank=True)
    subject = models.CharField(max_length=2048, null=True, blank=True)
    keywords = models.JSONField(null=True, blank=True)
    producer = models.CharField(max_length=2048, null=True, blank=True)
    creation_date = models.DateTimeField(null=True, blank=True)
    mod_date = models.DateTimeField(null=True, blank=True)
    creator = models.CharField(max_length=2048, null=True, blank=True)
    summary = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)

    filehash = models.CharField(max_length=255, null=True, blank=True, db_index=True)

    extraction_attempted = models.BooleanField(default=False)
    extraction_successful = models.BooleanField(default=False)

    num_pages = models.IntegerField(null=True, blank=True)
    num_words = models.IntegerField(null=True, blank=True)
    num_images = models.IntegerField(null=True, blank=True)

    extracted_text = models.OneToOneField(
        PDFText,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document",
    )

    extracted_entities = models.ManyToManyField(
        Entity, through="DocumentEntity", related_name="documents"
    )

    def __str__(self):
        return self.filename or self.file.name


class DocumentEntity(models.Model):
    """Through model for Document <-> Entity relation."""

    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE)
