from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("trigger_ingest/", views.trigger_ingest, name="trigger_ingest"),
    path(
        "download_faculty_sheets/",
        views.download_faculty_sheets,
        name="download_faculty_sheets",
    ),
]
