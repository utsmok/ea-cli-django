# Task 6: Main Table View Enhancements

## Overview

Enhance the main table view with column sorting, full-width layout, slide-out detail panel (hidden by default), row selection highlighting, and improved responsive design.

**Current Status:** ⚠️ **PARTIALLY IMPLEMENTED (30%)**

**What's Already Done:**
- ✅ Detail modal exists
- ✅ Row click functionality implemented
- ✅ Basic table structure with HTMX

**What's Missing:**
- ❌ Column sorting (asc/desc/unsort)
- ❌ Full-width layout
- ❌ Slide-out panel (hidden by default)
- ❌ Row selection with highlight
- ❌ Sort indicators

## Current Implementation Analysis

From the exploration, the dashboard has:
- Table with HTMX-based row interactions
- Detail modal that shows on row click
- Basic filtering (workflow tabs, faculty dropdown, search)
- Pagination

## Implementation Steps

### Step 1: Add Column Sorting to Query Service

**File:** `src/apps/dashboard/services/query_service.py`

```python
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"
    NONE = "unsort"

@dataclass
class ItemQueryFilter:
    """Filter parameters for item queries."""
    status: str | None = None
    faculty_id: int | None = None
    search_query: str | None = None
    period: str | None = None
    sort_field: str | None = None
    sort_direction: SortDirection = SortDirection.DESC

# Allowed sortable columns
SORTABLE_COLUMNS = {
    "material_id": "material_id",
    "filename": "material_id__filename",  # Will be QlikItem field after Task 2
    "title": "material_id__title",
    "faculty": "faculty__abbreviation",
    "workflow_status": "workflow_status",
    "modified_at": "modified_at",
    "last_change": "last_change",
}


class ItemQueryService:
    def __init__(self):
        self.base_qs = CopyrightItem.objects.select_related(
            "faculty",
            "document",
            "material_id",
        )

    def get_filtered_queryset(self, filters: ItemQueryFilter):
        """Get filtered and sorted queryset."""
        qs = self.base_qs.all()

        # ... existing filters ...

        # Sorting
        if filters.sort_field and filters.sort_field in SORTABLE_COLUMNS:
            if filters.sort_direction == SortDirection.ASC:
                qs = qs.order_by(SORTABLE_COLUMNS[filters.sort_field])
            elif filters.sort_direction == SortDirection.DESC:
                qs = qs.order_by(f"-{SORTABLE_COLUMNS[filters.sort_field]}")
            else:  # NONE - unsorted
                qs = qs.order_by("-modified_at", "-material_id")
        else:
            qs = qs.order_by("-modified_at", "-material_id")

        return qs
```

### Step 2: Update Views for Sorting

**File:** `src/apps/dashboard/views.py`

```python
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .services.query_service import ItemQueryService, ItemQueryFilter, SortDirection

@login_required
def index(request):
    """Dashboard view with filtering and sorting."""
    # Get filter parameters
    current_sort = request.GET.get('sort', 'modified_at')
    current_direction = request.GET.get('direction', 'desc')

    # Create filter
    query_filter = ItemQueryFilter(
        status=request.GET.get('status'),
        faculty_id=request.GET.get('faculty'),
        search_query=request.GET.get('search'),
        period=request.GET.get('period'),
        sort_field=current_sort,
        sort_direction=SortDirection(current_direction) if current_direction != 'unsort' else SortDirection.NONE,
    )

    # Get items
    service = ItemQueryService()
    items = service.get_filtered_queryset(query_filter)

    context = {
        'items': items,
        'current_filters': query_filter,
        'current_sort': {'field': current_sort, 'direction': current_direction},
    }

    return render(request, 'dashboard/index.html', context)
```

### Step 3: Add Sortable Table Headers

**File:** `src/templates/dashboard/_table_rows.html`

```django
<table class="table table-zebra w-full">
  <thead class="bg-base-200 sticky top-0 z-10 shadow-sm">
    <tr>
      {% for column in sortable_columns %}
      <th class="cursor-pointer hover:bg-base-300 transition-colors text-left p-3"
          hx-get="{% url 'dashboard:index' %}?{{ request.GET.urlencode }}&sort={{ column.field }}&direction={% if current_sort.field == column.field %}{% if current_sort.direction == 'desc' %}asc{% elif current_sort.direction == 'asc' %}unsort{% endif %}{% else %}desc{% endif %}"
          hx-target="#table-container"
          hx-push-url="true">
        <div class="flex items-center gap-1">
          {{ column.label }}
          {% if current_sort.field == column.field %}
            {% if current_sort.direction == 'asc' %}
              <span class="text-xs">↑</span>
            {% elif current_sort.direction == 'desc' %}
              <span class="text-xs">↓</span>
            {% endif %}
          {% endif %}
        </div>
      </th>
      {% endfor %}
    </tr>
  </thead>
  <tbody class="divide-y divide-base-200">
    {% for item in items %}
      {% include 'dashboard/_table_row.html' %}
    {% endfor %}
  </tbody>
</table>
```

### Step 4: Full-Width Layout

**File:** `src/templates/dashboard/dashboard.html`

```django
{% extends "base.html" %}

{% block content %}
<div class="h-screen flex flex-col overflow-hidden bg-base-100">
  <!-- Navbar (fixed height) -->
  <nav class="navbar ut-navbar h-16 flex-shrink-0 bg-base-100 border-b">
    <div class="flex-1">
      <a href="{% url 'dashboard:index' %}" class="btn btn-ghost normal-case text-xl">
        Easy Access Platform
      </a>
    </div>
    <!-- User menu, etc. -->
  </nav>

  <!-- Main content (flexible, scrollable) -->
  <main class="flex-1 overflow-hidden flex flex-col">
    <!-- Filter bar -->
    <div class="p-4 border-b bg-base-100 flex-shrink-0">
      <div class="flex gap-4 items-center">
        {% include 'components/_workflow_tabs.html' with current_status=current_filters.status %}
        {% include 'components/_filter_dropdown.html' %}
        {% include 'components/_filter_search.html' %}
      </div>
    </div>

    <!-- Table container (scrollable) -->
    <div class="flex-1 overflow-auto p-4" id="table-container">
      {% include 'dashboard/_table_rows.html' %}
    </div>
  </main>
</div>

<!-- Detail Panel (Slide-out) -->
<div id="detail-panel"
     class="fixed top-0 right-0 h-full w-[600px] bg-base-100 shadow-2xl transform transition-transform duration-300 translate-x-full z-50"
     x-data="{ open: false }"
     :class="{ 'translate-x-0': open }">
  <div class="flex items-center justify-between p-4 border-b">
    <h2 class="text-xl font-bold">Item Details</h2>
    <button @click="open = false"
            class="btn btn-sm btn-circle btn-ghost">
      ✕
    </button>
  </div>
  <div class="overflow-auto h-[calc(100%-4rem)] p-4">
    <div id="detail-panel-content"></div>
  </div>
</div>

<script>
document.addEventListener('htmx:afterRequest', function(evt) {
  // Auto-open detail panel when content is loaded
  if (evt.detail.xhr.responseURL.includes('detail_panel')) {
    Alpine.store('detailPanel', { open: true });
  }
});
</script>
{% endblock %}
```

### Step 5: Update Table Row for Selection

**File:** `src/templates/dashboard/_table_row.html`

```django
<tr id="row-{{ item.material_id_id }}"
    class="hover:bg-primary/5 transition-colors cursor-pointer"
    x-data="{ selected: false }"
    :class="{ 'bg-primary/10 ring-2 ring-primary': selected }"
    @click="selected = !selected; $dispatch('row-selected', { id: {{ item.material_id_id }}, selected })"
    hx-get="{% url 'dashboard:detail_panel' item.material_id_id %}"
    hx-target="#detail-panel-content"
    hx-swap="innerHTML">
  <td class="p-3">{{ item.material_id_id }}</td>
  <td class="p-3">{{ item.material_id.filename }}</td>
  <td class="p-3">{{ item.material_id.title }}</td>
  <td class="p-3">{% include 'components/_status_badge.html' with status_type=item.workflow_status status_text=item.workflow_status %}</td>
  <td class="p-3">{{ item.faculty }}</td>
</tr>
```

### Step 6: Add Detail Panel View

**File:** `src/apps/dashboard/views.py`

```python
@login_required
@require_GET
def detail_panel(request, material_id: int):
    """Render detail panel for an item."""
    item = get_object_or_404(
        CopyrightItem.objects.select_related(
            "faculty",
            "document",
            "material_id"
        ),
        material_id=material_id
    )

    context = {
        'item': item,
        'source_data': item.material_id,  # QlikItem
    }

    return TemplateResponse(
        request,
        "dashboard/_detail_panel_content.html",
        context
    )
```

**File:** `src/templates/dashboard/_detail_panel_content.html`

```django
<div class="space-y-6">
  <!-- Header -->
  <div>
    <h3 class="text-lg font-bold">{{ item.material_id.title }}</h3>
    <p class="text-sm text-base-content/60">ID: {{ item.material_id_id }}</p>
  </div>

  <!-- Workflow Status -->
  <div class="card bg-base-200">
    <div class="card-body p-4">
      <h4 class="font-bold mb-2">Workflow</h4>
      <div class="flex gap-2">
        {% include 'components/_status_badge.html' with status_type=item.workflow_status status_text=item.get_workflow_status_display %}
      </div>
    </div>
  </div>

  <!-- Source Data (Qlik) -->
  <div class="card bg-base-200">
    <div class="card-body p-4">
      <h4 class="font-bold mb-2">Source Data (Qlik)</h4>
      <dl class="grid grid-cols-2 gap-2 text-sm">
        <dt class="font-medium">Filename:</dt>
        <dd>{{ item.material_id.filename }}</dd>

        <dt class="font-medium">Author:</dt>
        <dd>{{ item.material_id.author }}</dd>

        <dt class="font-medium">Course:</dt>
        <dd>{{ item.material_id.course_name }}</dd>
      </dl>
    </div>
  </div>

  <!-- Classification -->
  <div class="card bg-base-200">
    <div class="card-body p-4">
      <h4 class="font-bold mb-2">Classification</h4>
      <p class="text-sm">{{ item.v2_manual_classification|default:"Unspecified" }}</p>
    </div>
  </div>

  <!-- Remarks -->
  {% if item.remarks %}
  <div class="card bg-base-200">
    <div class="card-body p-4">
      <h4 class="font-bold mb-2">Remarks</h4>
      <p class="text-sm whitespace-pre-wrap">{{ item.remarks }}</p>
    </div>
  </div>
  {% endif %}
</div>
```

### Step 7: Responsive Design

Add to CSS or Tailwind config:

```css
/* Hide less important columns on smaller screens */
@media (max-width: 1024px) {
  .col-v1-class { display: none; }
  .col-ml-pred { display: none; }
}

@media (max-width: 768px) {
  .col-department { display: none; }
  .col-remarks { display: none; }

  /* Full-width detail panel on mobile */
  #detail-panel {
    width: 100% !important;
  }
}
```

## Testing

### Manual Testing Checklist
- [ ] Click column headers - verify sorting changes
- [ ] Click same header 3 times - verify asc → desc → unsort cycle
- [ ] Click row - verify detail panel slides in
- [ ] Click close button - verify detail panel slides out
- [ ] Click multiple rows - verify selection highlight works
- [ ] Test on mobile - verify responsive behavior
- [ ] Test with 1000+ rows - verify performance acceptable

## Success Criteria

- [ ] Column sorting (asc/desc/unsort cycle)
- [ ] Visual sort indicators (↑/↓)
- [ ] Full-width layout with sticky header
- [ ] Slide-out detail panel (hidden by default)
- [ ] Row selection with highlight
- [ ] Responsive design (mobile-friendly)
- [ ] Performance acceptable with 50k+ items
- [ ] All HTMX interactions work smoothly

---

**All Tasks Complete!**

Refer to [README.md](README.md) for overall project status.
