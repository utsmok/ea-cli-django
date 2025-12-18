from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.api.urls")),
    path("ingest/", include("apps.ingest.urls")),
    path("", include("apps.dashboard.urls")),
]
