from django.urls import path

from . import views

app_name = "enrichment"

urlpatterns = [
    path(
        "item/<int:material_id>/trigger/",
        views.trigger_item_enrichment,
        name="trigger_item",
    ),
    path(
        "item/<int:material_id>/status/",
        views.item_enrichment_status,
        name="item_status",
    ),
    path(
        "batch/trigger/",
        views.trigger_batch_enrichment_ui,
        name="trigger_batch",
    ),
]
