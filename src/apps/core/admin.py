from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    ChangeLog,
    CopyrightItem,
    Course,
    CourseEmployee,
    Faculty,
    LegacyCopyrightItem,
    MissingCourse,
    Organization,
    Person,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["abbreviation", "name", "hierarchy_level", "parent"]
    list_filter = ["hierarchy_level"]
    search_fields = ["name", "abbreviation", "full_abbreviation"]
    ordering = ["hierarchy_level", "name"]


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ["abbreviation", "name", "parent"]
    search_fields = ["name", "abbreviation"]
    ordering = ["name"]


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ["input_name", "main_name", "faculty", "email"]
    list_filter = ["faculty"]
    search_fields = ["input_name", "main_name", "email"]
    filter_horizontal = ["orgs"]


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["cursuscode", "short_name", "year", "faculty"]
    list_filter = ["year", "faculty"]
    search_fields = ["cursuscode", "name", "short_name"]


@admin.register(CourseEmployee)
class CourseEmployeeAdmin(admin.ModelAdmin):
    list_display = ["course", "person", "role"]
    list_filter = ["role"]
    search_fields = ["course__name", "person__input_name"]


@admin.register(CopyrightItem)
class CopyrightItemAdmin(admin.ModelAdmin):
    """Admin interface for CopyrightItem with inline editing capabilities."""

    list_display = [
        "material_id",
        "url",
        "filename_short",
        "workflow_status",
        "status",
        "faculty",
        "classification",
        "modified_at",
    ]
    list_filter = [
        "workflow_status",
        "status",
        "faculty",
        "filetype",
        "classification",
        "file_exists",
    ]
    search_fields = [
        "material_id",
        "filename",
        "title",
        "author",
        "course_code",
        "course_name",
        "remarks",
    ]
    readonly_fields = [
        "created_at",
        "modified_at",
        "material_id",
        "filename",
        "filehash",
        "filetype",
        "url",
        "title",
        "author",
        "publisher",
        "period",
        "department",
        "course_code",
        "course_name",
        "status",
        "ml_classification",
        "isbn",
        "doi",
        "owner",
        "in_collection",
        "picturecount",
        "reliability",
        "pages_x_students",
        "count_students_registered",
        "pagecount",
        "wordcount",
        "faculty",
        "file_exists",
        "last_canvas_check",
        "courses",
        "canvas_course_id",
        # NOTE: Human-annotated fields are NOT in readonly_fields:
        # workflow_status, classification, manual_classification,
        # v2_manual_classification, v2_overnamestatus, v2_lengte,
        # remarks, scope, manual_identifier, auditor
    ]
    date_hierarchy = "modified_at"
    filter_horizontal = ["courses"]
    actions = ["mark_as_todo", "mark_as_done", "set_file_exists_flag"]

    # Enable pagination for large datasets
    list_per_page = 50
    list_max_show_all = 200

    fieldsets = (
        (
            "Identity",
            {
                "fields": ("material_id", "filehash", "faculty"),
                "classes": ("collapse",),
            },
        ),
        (
            "File Info",
            {"fields": ("filename", "filetype", "url", "status", "file_exists")},
        ),
        (
            "Classification (Editable)",
            {
                "fields": (
                    "remarks",
                    "workflow_status",
                    "scope",
                    "manual_identifier",
                    "manual_classification",
                    "v2_manual_classification",
                    "v2_overnamestatus",
                    "v2_lengte",
                    "classification",
                )
            },
        ),
        (
            "CRC classification",
            {"fields": ("ml_classification",), "classes": ("collapse",)},
        ),
        (
            "Content (System)",
            {
                "fields": (
                    "title",
                    "author",
                    "publisher",
                    "isbn",
                    "doi",
                    "owner",
                    "in_collection",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Course Info (System)",
            {
                "fields": (
                    "period",
                    "department",
                    "course_code",
                    "course_name",
                    "canvas_course_id",
                    "courses",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metrics (System)",
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
            "Timestamps",
            {
                "fields": ("created_at", "modified_at", "last_canvas_check"),
                "classes": ("collapse",),
            },
        ),
    )

    def filename_short(self, obj):
        if obj.filename and len(obj.filename) > 60:
            return obj.filename[:60] + "..."
        return obj.filename or "—"

    filename_short.short_description = "Filename"

    def mark_as_todo(self, request, queryset):
        """Admin action: Mark selected items as ToDo."""
        updated = queryset.update(workflow_status="ToDo")
        self.message_user(request, f"{updated} items marked as ToDo.")

    mark_as_todo.short_description = "Mark as ToDo"

    def mark_as_done(self, request, queryset):
        """Admin action: Mark selected items as Done."""
        updated = queryset.update(workflow_status="Done")
        self.message_user(request, f"{updated} items marked as Done.")

    mark_as_done.short_description = "Mark as Done"

    def set_file_exists_flag(self, request, queryset):
        """Admin action: Update file_exists flag for selected items."""
        # Check if documents exist for each item
        from apps.documents.models import Document

        updated = 0
        for item in queryset:
            item.file_exists = Document.objects.filter(items=item).exists()
            item.save(update_fields=["file_exists"])
            updated += 1
        self.message_user(request, f"{updated} items had file_exists flag updated.")

    set_file_exists_flag.short_description = "Update file_exists flag"

    def get_search_results(self, request, keyword, queryset):
        """Override search to use PostgreSQL full-text search if available."""
        # Use Django's search backend, which can be PostgreSQL full-text search
        return super().get_search_results(request, keyword, queryset)


@admin.register(ChangeLog)
class ChangeLogAdmin(admin.ModelAdmin):
    """Admin interface for change logs."""

    list_display = [
        "id",
        "item_link",
        "change_source_badge",
        "changed_by",
        "changed_at",
        "changes_summary",
    ]
    list_filter = [
        "change_source",
        "changed_at",
        "changed_by",
    ]
    search_fields = [
        "item__material_id",
        "item__filename",
    ]
    readonly_fields = [
        "item",
        "changes",
        "changed_at",
        "changed_by",
        "change_source",
        "batch",
        "changes_display",
    ]
    date_hierarchy = "changed_at"

    fieldsets = (
        (
            "What Changed",
            {
                "fields": (
                    "item",
                    "changes_display",
                )
            },
        ),
        (
            "When & Who",
            {
                "fields": (
                    "changed_at",
                    "changed_by",
                    "change_source",
                    "batch",
                )
            },
        ),
    )

    def item_link(self, obj):
        url = reverse("admin:core_copyrightitem_change", args=[obj.item.material_id])
        return format_html('<a href="{}">{}</a>', url, obj.item.material_id)

    item_link.short_description = "Item"

    def change_source_badge(self, obj):
        colors = {
            "QLIK": "#3b82f6",  # blue
            "FACULTY": "#10b981",  # green
            "MANUAL": "#8b5cf6",  # purple
            "ENRICHMENT": "#f59e0b",  # amber
            "MIGRATION": "#6b7280",  # gray
            "SYSTEM": "#ec4899",  # pink
        }
        color = colors.get(obj.change_source, "#6b7280")
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.get_change_source_display(),
        )

    change_source_badge.short_description = "Source"

    def changes_summary(self, obj):
        changes = obj.changes
        if not changes:
            return "No changes"

        field_count = len(changes)
        field_names = ", ".join(list(changes.keys())[:3])
        if field_count > 3:
            field_names += f" +{field_count - 3} more"

        return format_html(
            '<span style="color: #6b7280; font-size: 11px;">{} field(s): {}</span>',
            field_count,
            field_names,
        )

    changes_summary.short_description = "Changes"

    def changes_display(self, obj):
        import json

        changes_json = json.dumps(obj.changes, indent=2)
        return format_html(
            '<pre style="background: #f3f4f6; padding: 10px; border-radius: 4px; '
            'font-family: monospace; font-size: 12px;">{}</pre>',
            changes_json,
        )

    changes_display.short_description = "Change Details"


@admin.register(LegacyCopyrightItem)
class LegacyCopyrightItemAdmin(admin.ModelAdmin):
    list_display = ["material_id", "filehash", "filename", "matched_item"]
    search_fields = ["material_id", "filename", "filehash"]


@admin.register(MissingCourse)
class MissingCourseAdmin(admin.ModelAdmin):
    list_display = ["cursuscode"]
    search_fields = ["cursuscode"]
