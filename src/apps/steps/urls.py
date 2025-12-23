"""URL configuration for steps app."""

from django.urls import path

from . import views

app_name = "steps"

urlpatterns = [
    # Steps dashboard/index
    path("", views.steps_index, name="index"),
    # Step 1: Ingest Qlik Export
    path("ingest-qlik/", views.ingest_qlik_step, name="ingest_qlik"),
    # Step 2: Ingest Faculty Sheet
    path("ingest-faculty/", views.ingest_faculty_step, name="ingest_faculty"),
    # Step 3: Enrich from Osiris
    path("enrich-osiris/", views.enrich_osiris_step, name="enrich_osiris"),
    path("enrich-osiris/run/", views.run_enrich_osiris, name="run_enrich_osiris"),
    path(
        "enrich-osiris/status/", views.enrich_osiris_status, name="enrich_osiris_status"
    ),
    # Step 4: Enrich from People Pages
    path("enrich-people/", views.enrich_people_step, name="enrich_people"),
    path("enrich-people/run/", views.run_enrich_people, name="run_enrich_people"),
    path(
        "enrich-people/status/", views.enrich_people_status, name="enrich_people_status"
    ),
    # Step 5: Get PDF Status from Canvas
    path("pdf-canvas-status/", views.pdf_canvas_status_step, name="pdf_canvas_status"),
    path(
        "pdf-canvas-status/run/",
        views.run_pdf_canvas_status,
        name="run_pdf_canvas_status",
    ),
    path(
        "pdf-canvas-status/status/",
        views.pdf_canvas_status_status,
        name="pdf_canvas_status_status",
    ),
    # Step 6: Extract PDF Details
    path("pdf-extract/", views.pdf_extract_step, name="pdf_extract"),
    path("pdf-extract/run/", views.run_pdf_extract, name="run_pdf_extract"),
    path("pdf-extract/status/", views.pdf_extract_status, name="pdf_extract_status"),
    # Step 7: Export Faculty Sheets
    path("export-faculty/", views.export_faculty_step, name="export_faculty"),
    path("export-faculty/run/", views.run_export_faculty, name="run_export_faculty"),
    path(
        "export-faculty/download/<int:export_id>/<int:file_index>/",
        views.download_export_file,
        name="download_export_file",
    ),
]
