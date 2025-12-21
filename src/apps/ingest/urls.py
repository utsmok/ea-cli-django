"""URL configuration for ingestion dashboard."""

from django.urls import path

from . import views

app_name = "ingest"

urlpatterns = [
    # Dashboard
    path("", views.dashboard, name="dashboard"),
    # Upload
    path("upload/", views.upload, name="upload"),
    # Batch management
    path("batches/", views.batch_list, name="batch_list"),
    path("batches/<int:batch_id>/", views.batch_detail, name="batch_detail"),
    path("batches/<int:batch_id>/process/", views.batch_process, name="batch_process"),
    # API endpoints
    path(
        "api/batches/<int:batch_id>/status/",
        views.batch_status_api,
        name="batch_status_api",
    ),
    path(
        "batches/<int:batch_id>/status-partial/",
        views.batch_status_partial,
        name="batch_status_partial",
    ),
    # Export
    path("export/", views.export_faculty_sheets, name="export_faculty_sheets"),
    path(
        "export/<str:faculty>/<str:filename>/",
        views.download_export,
        name="download_export",
    ),
]
