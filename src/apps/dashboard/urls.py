"""
URL configuration for dashboard.

Pattern: Simple, explicit routes with clear naming.
"""

from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    # Main dashboard
    path("", views.dashboard_index, name="index"),
    # Inline editing
    path("item/<int:material_id>/update/", views.update_item_field, name="update_field"),
    # Three-tier detail system
    path("item/<int:material_id>/panel/", views.item_detail_panel, name="detail_panel"),
    path("item/<int:material_id>/modal/", views.item_detail_modal, name="detail_modal"),
    path("item/<int:material_id>/enrichment-status/", views.item_enrichment_status, name="enrichment_status"),
    path("item/<int:material_id>/", views.item_detail_page, name="detail_page"),
]
