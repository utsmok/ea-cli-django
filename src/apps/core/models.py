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


class ClassificationV2(models.TextChoices):
    JA_OPEN_LICENTIE = "Ja (open licentie)", _("Ja (Open Licentie)")
    JA_EIGEN_WERK = "Ja (eigen werk)", _("Ja (Eigen Werk)")
    JA_EASY_ACCESS = "Ja (easy access)", _("Ja (Easy Access)")
    NEE = "Nee", _("Nee")
    ONBEKEND = "Onbekend", _("Onbekend")


class OvernameStatus(models.TextChoices):
    OVERNAME_INBREUKMAKENDE = "Overname (inbreukmakende)", _("Inbreukmakend")
    GEEN_OVERNAME = "Geen overname", _("Geen Overname")
    ONBEKEND = "Onbekend", _("Onbekend")


class Lengte(models.TextChoices):
    KORT = "Kort", _("Kort")
    MIDDELLANG = "Middellang", _("Middellang")
    LANG = "Lang", _("Lang")
    ONBEKEND = "Onbekend", _("Onbekend")


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
    material_id = models.BigIntegerField(primary_key=True)
    filename = models.CharField(max_length=2048, null=True, blank=True, db_index=True)
    filehash = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    filetype = models.CharField(
        max_length=50, choices=Filetype.choices, default=Filetype.UNKNOWN
    )
    url = models.URLField(max_length=2048, null=True, blank=True)

    workflow_status = models.CharField(
        max_length=50,
        choices=WorkflowStatus.choices,
        default=WorkflowStatus.TODO,
        db_index=True,
    )
    status = models.CharField(
        max_length=50, choices=Status.choices, default=Status.PUBLISHED
    )

    manual_classification = models.CharField(max_length=2048, null=True, blank=True)
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

    title = models.CharField(max_length=2048, null=True, blank=True)
    author = models.CharField(max_length=2048, null=True, blank=True)
    publisher = models.CharField(max_length=2048, null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)

    pagecount = models.IntegerField(default=0)
    wordcount = models.IntegerField(default=0)

    faculty = models.ForeignKey(
        Faculty, on_delete=models.SET_NULL, null=True, blank=True, related_name="items"
    )
    courses = models.ManyToManyField(Course, related_name="copyright_items", blank=True)
    canvas_course_id = models.BigIntegerField(null=True, blank=True, db_index=True)

    file_exists = models.BooleanField(null=True, blank=True)
    last_canvas_check = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-modified_at"]
        indexes = [models.Index(fields=["workflow_status", "faculty"])]


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


class StagedItem(TimestampedModel):
    """Unified staging table for both CRC exports and Faculty Sheets."""

    class SourceType(models.TextChoices):
        CRC_EXPORT = "CRC", "CRC Export"
        FACULTY_SHEET = "SHEET", "Faculty Excel Sheet"

    target_material_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=50, default="PENDING")
    error_message = models.TextField(null=True, blank=True)
