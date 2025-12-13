from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_index, name="index"),
    path("grid_partial/", views.grid_partial, name="grid_partial"),
]
