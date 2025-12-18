from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

# -----------------------------------------------------------------------------
# Choices (Enums)
# -----------------------------------------------------------------------------


class WorkflowStatus(models.TextChoices):
    TODO = "ToDo", _("To Do")
    IN_PROGRESS = "InProgress", _("In Progress")
    DONE = "Done", _("Done")


class Status(models.TextChoices):
    PUBLISHED = "Published", _("Published")
    UNPUBLISHED = "Unpublished", _("Unpublished")
    DELETED = "Deleted", _("Deleted")


class Filetype(models.TextChoices):
    PDF = "pdf", _("PDF")
    PPT = "ppt", _("PowerPoint")
    DOC = "doc", _("Word")
    XLSX = "xlsx", _("Excel")
    UNKNOWN = "unknown", _("Unknown")


class Classification(models.TextChoices):
    OPEN_ACCESS = "open access", _("open access")
    KORTE_OVERNAME = "korte overname", _("korte overname")
    MIDDELLANGE_OVERNAME = "middellange overname", _("middellange overname")
    LANGE_OVERNAME = "lange overname", _("lange overname")

    EIGEN_MATERIAAL_POWERPOINT = (
        "eigen materiaal - powerpoint",
        _("eigen materiaal - powerpoint"),
    )
    EIGEN_MATERIAAL_TITELINDICATIE = (
        "eigen materiaal - titelindicatie",
        _("eigen materiaal - titelindicatie"),
    )
    EIGEN_MATERIAAL_OVERIG = "eigen materiaal - overig", _("eigen materiaal - overig")
    EIGEN_MATERIAAL = "eigen materiaal", _("eigen materiaal")

    ONBEKEND = "onbekend", _("onbekend")
    NIET_GEANALYSEERD = "niet geanalyseerd", _("niet geanalyseerd")
    IN_ONDERZOEK = "in onderzoek", _("in onderzoek")
    VERWIJDERVERZOEK_VERSTUURD = (
        "verwijderverzoek verstuurd",
        _("verwijderverzoek verstuurd"),
    )
    LICENTIE_BESCHIKBAAR = "licentie beschikbaar", _("licentie beschikbaar")


class ClassificationV2(models.TextChoices):
    JA_OPEN_LICENTIE = "Ja (open licentie)", _("Ja (Open Licentie)")
    JA_EIGEN_WERK = "Ja (eigen werk)", _("Ja (Eigen Werk)")
    JA_EASY_ACCESS = "Ja (easy access)", _("Ja (Easy Access)")
    NEE = "Nee", _("Nee")
    ONBEKEND = "Onbekend", _("Onbekend")
    JA_BIBLIOTHEEK_LICENTIE = (
        "Ja (bibilotheek licentie)",
        _("Ja (Bibliotheek Licentie)"),
    )
    JA_DIRECTE_TOESTEMMING = "Ja (directe toestemming)", _("Ja (Directe Toestemming)")
    JA_PUBLIEK_DOMEIN = "Ja (Publiek domein)", _("Ja (Publiek Domein)")
    JA_STUDENTWERK = "Ja (studentwerk)", _("Ja (Studentwerk)")
    JA_ANDERS = "Ja (anders)", _("Ja (Anders)")

    JA_DIRECTE_TOESTEMMING_TIJDELIJK = (
        "Ja (directe toestemming) - tijdelijk",
        _("Ja (Directe Toestemming) - Tijdelijk"),
    )
    JA_BIBLIOTHEEK_LICENTIE_TIJDELIJK = (
        "Ja (bibilotheek licentie)- tijdelijk",
        _("Ja (Bibliotheek Licentie) - Tijdelijk"),
    )
    JA_ANDERS_TIJDELIJK = "Ja (anders) - tijdelijk", _("Ja (Anders) - Tijdelijk")

    # No classifications
    NEE_LINK_BESCHIKBAAR = "Nee (Link beschikbaar)", _("Nee (Link Beschikbaar)")
    NEE_STUDENTWERK = "Nee (studentwerk)", _("Nee (Studentwerk)")


class OvernameStatus(models.TextChoices):
    OVERNAME_INBREUKMAKENDE = "Overname (inbreukmakende)", _("Inbreukmakend")
    OVERNAME_ANDERE = "Overname (andere)", _("Overname (Andere)")
    GEEN_OVERNAME = "Geen overname", _("Geen Overname")
    ONBEKEND = "Onbekend", _("Onbekend")


class Infringement(models.TextChoices):
    YES = "yes", _("Yes")
    NO = "no", _("No")
    MAYBE = "maybe", _("Maybe")
    UNDETERMINED = "undetermined", _("Undetermined")


class Lengte(models.TextChoices):
    KORT = "Kort", _("Kort")
    MIDDELLANG = "Middellang", _("Middellang")
    LANG = "Lang", _("Lang")
    ONBEKEND = "Onbekend", _("Onbekend")


class EnrichmentStatus(models.TextChoices):
    PENDING = "PENDING", _("Pending")
    RUNNING = "RUNNING", _("Running")
    COMPLETED = "COMPLETED", _("Completed")
    FAILED = "FAILED", _("Failed")


# -----------------------------------------------------------------------------
# Abstract Base
# -----------------------------------------------------------------------------


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# -----------------------------------------------------------------------------
# Organizations & People
# -----------------------------------------------------------------------------


class Organization(TimestampedModel):
    hierarchy_level = models.IntegerField(help_text="0=Uni, 1=Faculty, 2=Dept")
    name = models.CharField(max_length=2048, db_index=True)
    abbreviation = models.CharField(max_length=255, db_index=True)
    full_abbreviation = models.CharField(max_length=2048, unique=True)

    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
    )

    class Meta:
        unique_together = ("name", "abbreviation")

    def __str__(self):
        return f"{self.abbreviation}"


class Faculty(Organization):
    pass


class Person(TimestampedModel):
    input_name = models.CharField(max_length=2048, unique=True, db_index=True)
    main_name = models.CharField(max_length=2048, null=True, blank=True)
    match_confidence = models.FloatField(null=True, blank=True)
    email = models.EmailField(max_length=2048, null=True, blank=True)
    people_page_url = models.URLField(max_length=2048, null=True, blank=True)

    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    orgs = models.ManyToManyField(Organization, related_name="personnel", blank=True)

    is_verified = models.BooleanField(default=False)
    metadata = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.main_name or self.input_name


# -----------------------------------------------------------------------------
# Courses
# -----------------------------------------------------------------------------


class Course(TimestampedModel):
    cursuscode = models.BigIntegerField(primary_key=True)
    internal_id = models.BigIntegerField(unique=True, null=True, blank=True)
    year = models.IntegerField()
    name = models.CharField(max_length=2048)
    short_name = models.CharField(max_length=255, null=True, blank=True)

    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses",
    )
    programme_text = models.CharField(max_length=2048, null=True, blank=True)
    teachers = models.ManyToManyField(
        Person, through="CourseEmployee", related_name="courses"
    )

    def __str__(self):
        return f"{self.name} ({self.cursuscode})"


class CourseEmployee(TimestampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    role = models.CharField(max_length=255, null=True, blank=True)


# -----------------------------------------------------------------------------
# Copyright Data
# -----------------------------------------------------------------------------


class CopyrightItem(TimestampedModel):
    # Core data
    material_id = models.BigIntegerField(primary_key=True)
    filename = models.CharField(max_length=2048, null=True, blank=True, db_index=True)
    filehash = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    filetype = models.CharField(
        max_length=50, choices=Filetype.choices, default=Filetype.UNKNOWN
    )
    url = models.URLField(max_length=2048, null=True, blank=True)

    # CRC extracted metadata
    title = models.CharField(max_length=2048, null=True, blank=True)
    author = models.CharField(max_length=2048, null=True, blank=True)
    publisher = models.CharField(max_length=2048, null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)

    period = models.CharField(max_length=50, null=True, blank=True)
    department = models.CharField(max_length=2048, null=True, blank=True)
    course_code = models.CharField(max_length=2048, null=True, blank=True)
    course_name = models.CharField(max_length=2048, null=True, blank=True)

    status = models.CharField(
        max_length=50, choices=Status.choices, default=Status.PUBLISHED
    )

    classification = models.CharField(
        max_length=100,
        choices=Classification.choices,
        default=Classification.NIET_GEANALYSEERD,
    )

    ml_classification = models.CharField(
        max_length=100,
        choices=Classification.choices,
        default=Classification.NIET_GEANALYSEERD,
        null=True,
        blank=True,
    )

    isbn = models.CharField(max_length=255, null=True, blank=True)
    doi = models.CharField(max_length=255, null=True, blank=True)

    owner = models.CharField(max_length=2048, null=True, blank=True)
    in_collection = models.BooleanField(null=True, blank=True)

    picturecount = models.IntegerField(default=0)
    reliability = models.IntegerField(default=0)
    pages_x_students = models.IntegerField(default=0)
    count_students_registered = models.IntegerField(default=0)
    retrieved_from_copyright_on = models.DateTimeField(null=True, blank=True)

    pagecount = models.IntegerField(default=0)
    wordcount = models.IntegerField(default=0)

    # Human-managed fields
    workflow_status = models.CharField(
        max_length=50,
        choices=WorkflowStatus.choices,
        default=WorkflowStatus.TODO,
        db_index=True,
    )
    manual_classification = models.CharField(
        max_length=2048, choices=Classification.choices, default=Classification.ONBEKEND,
        null=True,
        blank=True,
    )
    manual_identifier = models.CharField(max_length=2048, null=True, blank=True)
    scope = models.CharField(max_length=50, null=True, blank=True)
    v2_manual_classification = models.CharField(
        max_length=100,
        choices=ClassificationV2.choices,
        default=ClassificationV2.ONBEKEND,
        db_index=True,
    )
    v2_overnamestatus = models.CharField(
        max_length=100, choices=OvernameStatus.choices, default=OvernameStatus.ONBEKEND
    )
    v2_lengte = models.CharField(
        max_length=50, choices=Lengte.choices, default=Lengte.ONBEKEND
    )

    # Added by this codebase

    auditor = models.CharField(max_length=2048, null=True, blank=True)
    last_change = models.DateTimeField(null=True, blank=True)
    faculty = models.ForeignKey(
        Faculty, on_delete=models.SET_NULL, null=True, blank=True, related_name="items"
    )
    file_exists = models.BooleanField(null=True, blank=True)
    last_canvas_check = models.DateTimeField(null=True, blank=True)

    courses = models.ManyToManyField(Course, related_name="copyright_items", blank=True)
    canvas_course_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    # Enrichment tracking
    enrichment_status = models.CharField(
        max_length=20,
        choices=EnrichmentStatus.choices,
        default=EnrichmentStatus.PENDING,
    )
    last_enrichment_attempt = models.DateTimeField(null=True, blank=True)
    extraction_status = models.CharField(
        max_length=20,
        choices=EnrichmentStatus.choices,
        default=EnrichmentStatus.PENDING,
    )
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )

    class Meta:
        ordering = ["-modified_at"]
        indexes = [
            models.Index(
                fields=[
                    "workflow_status",
                    "faculty",
                    "material_id",
                    "v2_manual_classification",
                    "manual_classification",
                ]
            )
        ]


class LegacyCopyrightItem(TimestampedModel):
    """Archive of V1 items for matching decisions."""

    material_id = models.BigIntegerField(primary_key=True)
    filehash = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    filename = models.CharField(max_length=2048, null=True, blank=True)
    manual_classification = models.CharField(max_length=2048, null=True, blank=True)
    matched_item = models.ForeignKey(
        CopyrightItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legacy_matches",
    )


class MissingCourse(TimestampedModel):
    """Store cursus codes that do not yet have a 'Course' entry in the db."""

    cursuscode = models.BigIntegerField(primary_key=True)

    def __str__(self):
        return str(self.cursuscode)


# -----------------------------------------------------------------------------
# Audit Trail
# -----------------------------------------------------------------------------


class ChangeLog(models.Model):
    """
    Complete audit trail for all changes to CopyrightItems.

    Records what changed, when, who made the change, and the source.
    Supports both batch ingestion and manual edits.
    """

    class ChangeSource(models.TextChoices):
        QLIK_INGESTION = "QLIK", _("Qlik Ingestion")
        FACULTY_INGESTION = "FACULTY", _("Faculty Ingestion")
        MANUAL_EDIT = "MANUAL", _("Manual Edit")
        ENRICHMENT = "ENRICHMENT", _("Enrichment Process")
        MIGRATION = "MIGRATION", _("Data Migration")
        SYSTEM = "SYSTEM", _("System Process")

    # What changed
    item = models.ForeignKey(
        CopyrightItem,
        on_delete=models.CASCADE,
        related_name="change_logs",
        help_text="The item that was changed",
    )

    # Change details
    changes = models.JSONField(
        help_text="Dictionary of changed fields: {'field_name': {'old': ..., 'new': ...}}"
    )

    # When & Who
    changed_at = models.DateTimeField(
        auto_now_add=True, db_index=True, help_text="When the change occurred"
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="changes_made",
        null=True,
        blank=True,
        help_text="User who made the change (null for system changes)",
    )

    # Source tracking
    change_source = models.CharField(
        max_length=20, choices=ChangeSource.choices, help_text="Source of the change"
    )

    # Link to ingestion batch if applicable
    batch = models.ForeignKey(
        "ingest.IngestionBatch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="changes",
        help_text="Ingestion batch that caused this change (if applicable)",
    )

    class Meta:
        db_table = "change_logs"
        verbose_name = "Change Log"
        verbose_name_plural = "Change Logs"
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["item", "-changed_at"]),
            models.Index(fields=["changed_by", "-changed_at"]),
            models.Index(fields=["batch"]),
            models.Index(fields=["change_source", "-changed_at"]),
        ]

    def __str__(self):
        return f"Change to {self.item.material_id} at {self.changed_at.strftime('%Y-%m-%d %H:%M')}"
