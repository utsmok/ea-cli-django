from django.template.response import TemplateResponse

from apps.core.models import CopyrightItem


def dashboard_index(request):
    return TemplateResponse(request, "dashboard/dashboard.html", {})


def grid_partial(request):
    # Standard filtering logic here
    items = CopyrightItem.objects.all()[:50]

    if request.headers.get("HX-Request"):
        return TemplateResponse(request, "dashboard/_grid.html", {"items": items})
    return TemplateResponse(request, "dashboard/dashboard.html", {"items": items})
