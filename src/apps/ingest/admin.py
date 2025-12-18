from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import FacultyEntry, IngestionBatch, ProcessingFailure, QlikEntry


@admin.register(IngestionBatch)
class IngestionBatchAdmin(admin.ModelAdmin):
    """Admin interface for ingestion batches."""

    list_display = [
        "id",
        "source_type_badge",
        "faculty_code",
        "uploaded_by",
        "uploaded_at",
        "status_badge",
        "progress_display",
        "duration_display",
    ]
    list_filter = [
        "source_type",
        "status",
        "uploaded_at",
        "uploaded_by",
    ]
    search_fields = [
        "faculty_code",
        "uploaded_by__username",
        "error_message",
    ]
    readonly_fields = [
        "uploaded_at",
        "started_at",
        "completed_at",
        "duration_display",
        "progress_display",
        "error_message",
    ]
    date_hierarchy = "uploaded_at"

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "source_type",
                    "faculty_code",
                    "source_file",
                    "uploaded_by",
                    "uploaded_at",
                )
            },
        ),
        (
            "Processing State",
            {
                "fields": (
                    "status",
                    "started_at",
                    "completed_at",
                    "duration_display",
                )
            },
        ),
        (
            "Statistics",
            {
                "fields": (
                    "total_rows",
                    "rows_staged",
                    "items_created",
                    "items_updated",
                    "items_skipped",
                    "items_failed",
                    "progress_display",
                )
            },
        ),
        (
            "Errors",
            {
                "fields": ("error_message",),
                "classes": ("collapse",),
            },
        ),
    )

    def source_type_badge(self, obj):
        colors = {
            "QLIK": "#3b82f6",  # blue
            "FACULTY": "#10b981",  # green
        }
        color = colors.get(obj.source_type, "#6b7280")
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.get_source_type_display(),
        )

    source_type_badge.short_description = "Type"

    def status_badge(self, obj):
        colors = {
            "PENDING": "#f59e0b",  # amber
            "STAGING": "#3b82f6",  # blue
            "PROCESSING": "#8b5cf6",  # purple
            "COMPLETED": "#10b981",  # green
            "FAILED": "#ef4444",  # red
            "PARTIAL": "#f59e0b",  # amber
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def progress_display(self, obj):
        if obj.total_rows == 0:
            return "No data"

        processed = (
            obj.items_created + obj.items_updated + obj.items_skipped + obj.items_failed
        )
        percentage = (processed / obj.total_rows * 100) if obj.total_rows > 0 else 0

        return format_html(
            '<div style="width: 100px; background: #e5e7eb; border-radius: 3px; overflow: hidden;">'
            '<div style="width: {}%; background: #10b981; height: 20px; line-height: 20px; '
            'text-align: center; color: white; font-size: 11px; font-weight: bold;">{:.0f}%</div></div>'
            '<div style="font-size: 11px; color: #6b7280; margin-top: 2px;">'
            "{} / {} items</div>",
            percentage,
            percentage,
            processed,
            obj.total_rows,
        )

    progress_display.short_description = "Progress"

    def duration_display(self, obj):
        duration = obj.duration
        if duration:
            total_seconds = int(duration.total_seconds())
            minutes, seconds = divmod(total_seconds, 60)
            if minutes > 0:
                return f"{minutes}m {seconds}s"
            return f"{seconds}s"
        return "—"

    duration_display.short_description = "Duration"


@admin.register(FacultyEntry)
class FacultyEntryAdmin(admin.ModelAdmin):
    """Admin interface for staged faculty entries."""

    list_display = [
        "id",
        "material_id",
        "batch_link",
        "workflow_status",
        "processed_badge",
        "row_number",
    ]
    list_filter = [
        "processed",
        "batch__faculty_code",
        "workflow_status",
    ]
    search_fields = [
        "material_id",
        "remarks",
        "manual_identifier",
    ]
    readonly_fields = [
        "batch",
        "created_at",
        "processed_at",
    ]

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "batch",
                    "material_id",
                    "row_number",
                )
            },
        ),
        (
            "Faculty Fields",
            {
                "fields": (
                    "workflow_status",
                    "classification",
                    "v2_manual_classification",
                    "v2_overnamestatus",
                    "v2_lengte",
                    "remarks",
                    "scope",
                    "manual_identifier",
                    "manual_classification",
                )
            },
        ),
        (
            "Processing",
            {
                "fields": (
                    "processed",
                    "processed_at",
                    "created_at",
                )
            },
        ),
    )

    def batch_link(self, obj):
        url = reverse("admin:ingest_ingestionbatch_change", args=[obj.batch.id])
        return format_html('<a href="{}">{}</a>', url, obj.batch)

    batch_link.short_description = "Batch"

    def processed_badge(self, obj):
        if obj.processed:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; '
                'border-radius: 3px; font-size: 11px;">{}</span>',
                "✓",
            )
        return format_html(
            '<span style="background: #6b7280; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            "○",
        )

    processed_badge.short_description = "Done"


@admin.register(QlikEntry)
class QlikEntryAdmin(admin.ModelAdmin):
    """Admin interface for staged Qlik entries."""

    list_display = [
        "id",
        "material_id",
        "batch_link",
        "filename_short",
        "status",
        "processed_badge",
        "row_number",
    ]
    list_filter = [
        "processed",
        "status",
        "filetype",
    ]
    search_fields = [
        "material_id",
        "filename",
        "title",
        "author",
    ]
    readonly_fields = [
        "batch",
        "created_at",
        "processed_at",
    ]

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "batch",
                    "material_id",
                    "row_number",
                )
            },
        ),
        (
            "File Metadata",
            {
                "fields": (
                    "filename",
                    "filehash",
                    "filetype",
                    "url",
                    "status",
                )
            },
        ),
        (
            "Content",
            {
                "fields": (
                    "title",
                    "author",
                    "publisher",
                    "isbn",
                    "doi",
                )
            },
        ),
        (
            "Course Info",
            {
                "fields": (
                    "period",
                    "department",
                    "course_code",
                    "course_name",
                    "canvas_course_id",
                )
            },
        ),
        (
            "Metrics",
            {
                "fields": (
                    "count_students_registered",
                    "pagecount",
                    "wordcount",
                    "picturecount",
                    "pages_x_students",
                    "reliability",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Infringement",
            {
                "fields": (
                    "infringement",
                    "possible_fine",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Processing",
            {
                "fields": (
                    "processed",
                    "processed_at",
                    "created_at",
                )
            },
        ),
    )

    def batch_link(self, obj):
        url = reverse("admin:ingest_ingestionbatch_change", args=[obj.batch.id])
        return format_html('<a href="{}">{}</a>', url, obj.batch)

    batch_link.short_description = "Batch"

    def filename_short(self, obj):
        if obj.filename and len(obj.filename) > 50:
            return obj.filename[:50] + "..."
        return obj.filename or "—"

    filename_short.short_description = "Filename"

    def processed_badge(self, obj):
        if obj.processed:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 2px 6px; '
                'border-radius: 3px; font-size: 11px;">{}</span>',
                "✓",
            )
        return format_html(
            '<span style="background: #6b7280; color: white; padding: 2px 6px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            "○",
        )

    processed_badge.short_description = "Done"


@admin.register(ProcessingFailure)
class ProcessingFailureAdmin(admin.ModelAdmin):
    """Admin interface for processing failures."""

    list_display = [
        "id",
        "batch_link",
        "material_id",
        "row_number",
        "error_type",
        "created_at",
    ]
    list_filter = [
        "error_type",
        "created_at",
    ]
    search_fields = [
        "material_id",
        "error_message",
        "error_type",
    ]
    readonly_fields = [
        "batch",
        "created_at",
        "row_data_display",
    ]

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "batch",
                    "material_id",
                    "row_number",
                )
            },
        ),
        (
            "Error Details",
            {
                "fields": (
                    "error_type",
                    "error_message",
                )
            },
        ),
        (
            "Raw Data",
            {
                "fields": ("row_data_display",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_at",),
            },
        ),
    )

    def batch_link(self, obj):
        url = reverse("admin:ingest_ingestionbatch_change", args=[obj.batch.id])
        return format_html('<a href="{}">{}</a>', url, obj.batch)

    batch_link.short_description = "Batch"

    def row_data_display(self, obj):
        import json

        data_json = json.dumps(obj.row_data, indent=2)
        return format_html(
            '<pre style="background: #f3f4f6; padding: 10px; border-radius: 4px;">{}</pre>',
            data_json,
        )

    row_data_display.short_description = "Row Data"
