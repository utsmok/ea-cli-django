from django.core.paginator import Paginator
from django.template.response import TemplateResponse

from apps.core.models import CopyrightItem


def dashboard_index(request):
    return TemplateResponse(request, "dashboard/dashboard.html", {})


def grid_partial(request):
    items_list = CopyrightItem.objects.all().order_by("-created_at")

    paginator = Paginator(items_list, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "items": page_obj,
        "page_obj": page_obj,
        "only_items": request.GET.get("page", "1") != "1",
    }

    if request.headers.get("HX-Request"):
        return TemplateResponse(request, "dashboard/_grid.html", context)
    return TemplateResponse(request, "dashboard/dashboard.html", context)
