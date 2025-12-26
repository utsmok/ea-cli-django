from django.urls import path

from . import views
from .api import api

app_name = "api"

urlpatterns = [
    # Health check endpoints (no authentication required)
    path("health/", views.health_check, name="health_check"),
    path("readiness/", views.readiness_check, name="readiness_check"),
    # Data ingestion and export endpoints
    path("trigger_ingest/", views.trigger_ingest, name="trigger_ingest"),
    path(
        "download_faculty_sheets/",
        views.download_faculty_sheets,
        name="download_faculty_sheets",
    ),
    path("api/", api.urls),
]
