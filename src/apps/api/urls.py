from django.urls import path

from . import views

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
]

# OpenAPI documentation URLs (added to main URL config in src/config/urls.py)
# Use ninja's OpenAPI integration for schema documentation
from ninja.main import API

# Create API instance for documentation
api = API()


# Add health check endpoint to schema
@api.get("/health/", tags=["Health"])
def health_check_schema(request):
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": "ea-platform",
        "version": "1.0.0",
    }


@api.get("/readiness/", tags=["Health"])
def readiness_check_schema(request):
    """Readiness check endpoint for container orchestration."""
    return {"status": "ready", "checks": {"database": "healthy", "cache": "healthy"}}
