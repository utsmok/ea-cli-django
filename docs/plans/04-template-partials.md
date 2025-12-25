# Task 4: Django 6.0 Template Partials

## Overview

Migrate template components from traditional `{% include %}` to Django 6.0's built-in `{% partialdef %}` / `{% partial %}` syntax for better encapsulation and maintainability.

**Current Status:** ❌ **NOT STARTED**

**Django 6.0 Feature:** Template partials are built into Django 6.0 - no additional packages needed!

## Benefits of Django 6.0 Template Partials

1. **Better encapsulation:** Component logic stays with component
2. **Default parameters:** Set sensible defaults in `partialdef`
3. **No context pollution:** Component doesn't access parent context unless passed
4. **Overridable:** Templates can override partials in inheritance chain
5. **Direct access:** Can render partials via `template.html#partial_name` syntax
6. **HTMX-friendly:** Perfect for AJAX-style updates

## Current Template Structure

```
src/templates/
├── components/
│   ├── _workflow_tabs.html       # Workflow status filter
│   ├── _filter_dropdown.html     # Faculty filter dropdown
│   ├── _filter_search.html       # Search input
│   ├── _editable_cell.html       # Inline editing cells
│   └── _status_badge.html        # Status badges
└── dashboard/
    ├── dashboard.html
    ├── _table.html
    ├── _table_rows.html
    └── _detail_panel.html
```

## Implementation Strategy

### Step 1: Create Consolidated Partials File

**File:** `src/templates/components/partials.html` (NEW)

This will house all reusable partials for the application.

```django
{% load static %}

{# ==============================================================================
   STATUS BADGES
   ============================================================================ #}

{% partialdef status_badge status_type status_text %}
<span class="badge badge-{{ status_type }}">{{ status_text }}</span>
{% endpartialdef %}

{# ==============================================================================
   WORKFLOW TABS
   ============================================================================ #}

{% partialdef workflow_tabs current_status %}
<div class="tabs tabs-boxed bg-base-200 p-2" role="tablist">
  <button role="tab"
          class="tab {% if current_status == 'all' %}tab-active{% endif %}"
          hx-get="{% url 'dashboard:index' %}?status=all"
          hx-target="#table-container"
          hx-push-url="true">
    All
  </button>
  <button role="tab"
          class="tab {% if current_status == 'ToDo' %}tab-active{% endif %}"
          hx-get="{% url 'dashboard:index' %}?status=ToDo"
          hx-target="#table-container"
          hx-push-url="true">
    To Do
  </button>
  <button role="tab"
          class="tab {% if current_status == 'InProgress' %}tab-active{% endif %}"
          hx-get="{% url 'dashboard:index' %}?status=InProgress"
          hx-target="#table-container"
          hx-push-url="true">
    In Progress
  </button>
  <button role="tab"
          class="tab {% if current_status == 'Done' %}tab-active{% endif %}"
          hx-get="{% url 'dashboard:index' %}?status=Done"
          hx-target="#table-container"
          hx-push-url="true">
    Done
  </button>
</div>
{% endpartialdef %}

{# ==============================================================================
   FILTER DROPDOWN
   ============================================================================ #}

{% partialdef filter_dropdown faculties selected_faculty %}
<div class="dropdown dropdown-end">
  <label tabindex="0" class="btn btn-ghost btn-sm">
    Faculty
    <svg class="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
    </svg>
  </label>
  <div tabindex="0" class="dropdown-content z-[1] card card-compact w-64 p-2 shadow bg-base-100 text-base-content">
    <div class="card-body">
      <h3 class="card-title text-sm">Filter by Faculty</h3>
      <ul class="menu menu-sm">
        <li><a hx-get="{% url 'dashboard:index' %}?faculty="
                hx-target="#table-container"
                hx-push-url="true">All Faculties</a></li>
        {% for faculty in faculties %}
        <li>
          <a hx-get="{% url 'dashboard:index' %}?faculty={{ faculty.id }}"
             hx-target="#table-container"
             hx-push-url="true"
             class="{% if selected_faculty == faculty.id %}active{% endif %}">
            {{ faculty.abbreviation }}
          </a>
        </li>
        {% endfor %}
      </ul>
    </div>
  </div>
</div>
{% endpartialdef %}

{# ==============================================================================
   SEARCH INPUT
   ============================================================================ #}

{% partialdef search_input current_search %}
<div class="form-control">
  <input type="search"
         name="search"
         value="{{ current_search|default:'' }}"
         placeholder="Search..."
         class="input input-bordered input-sm w-24 md:w-auto"
         hx-get="{% url 'dashboard:index' %}"
         hx-target="#table-container"
         hx-push-url="true"
         hx-trigger="keyup changed delay:500ms">
</div>
{% endpartialdef %}

{# ==============================================================================
   EDITABLE CELL
   ============================================================================ #}

{% partialdef editable_cell field_name value item_id choices=None badge=False %}
<div class="editable-cell" data-field="{{ field_name }}" data-item-id="{{ item_id }}">
  {% if choices %}
    <select name="{{ field_name }}"
            class="select select-bordered select-xs"
            hx-post="{% url 'dashboard:update_inline' item_id %}"
            hx-trigger="change"
            hx-swap="outerHTML">
      {% for choice_value, choice_label in choices %}
        <option value="{{ choice_value }}"
                {% if choice_value == value %}selected{% endif %}>
          {{ choice_label }}
        </option>
      {% endfor %}
    </select>
  {% else %}
    <input type="text"
           name="{{ field_name }}"
           value="{{ value }}"
           class="input input-bordered input-xs"
           hx-post="{% url 'dashboard:update_inline' item_id %}"
           hx-trigger="change"
           hx-swap="outerHTML">
  {% endif %}

  {% if badge %}
    {% partial status_badge status_type=value status_text=value %}
  {% endif %}
</div>
{% endpartialdef %}
```

### Step 2: Update Base Template to Load Partials

**File:** `src/templates/base.html`

Add near the top after `{% load static %}`:

```django
{% load static %}
{% load partials from components %}  {# Or include inline #}

{# Option 1: Load partials file #}
{% include "components/partials.html" %}

{# Option 2: Define partials directly in base.html #}
{% partialdef ... %}
```

**Better approach:** Since partials are defined in templates, just include the partials file where needed:

```django
{# In templates that use partials #}
{% include "components/partials.html" %}
```

### Step 3: Convert Dashboard to Use Partials

**File:** `src/templates/dashboard/dashboard.html`

**Before:**
```django
{% extends "base.html" %}

{% block content %}
<div class="container mx-auto p-6">
  {% include "components/_workflow_tabs.html" with current_status=current_filters.status %}
  {% include "components/_filter_dropdown.html" with faculties=faculties selected_faculty=current_filters.faculty_id %}
  {% include "components/_filter_search.html" with current_search=current_filters.search_query %}
</div>
{% endblock %}
```

**After:**
```django
{% extends "base.html" %}
{% include "components/partials.html" %}

{% block content %}
<div class="container mx-auto p-6">
  {% partial workflow_tabs current_status=current_filters.status %}
  {% partial filter_dropdown faculties=faculties selected_faculty=current_filters.faculty_id %}
  {% partial search_input current_search=current_filters.search_query %}
</div>
{% endblock %}
```

### Step 4: Update Table Rows to Use Partials

**File:** `src/templates/dashboard/_table_rows.html`

```django
{% include "components/partials.html" %}

<table class="table table-zebra w-full">
  <thead>
    <tr>
      <th>ID</th>
      <th>Filename</th>
      <th>Title</th>
      <th>Status</th>
      <th>Faculty</th>
    </tr>
  </thead>
  <tbody>
    {% for item in items %}
    <tr class="hover:bg-primary/5"
        hx-get="{% url 'dashboard:detail_panel' item.material_id %}"
        hx-target="#detail-panel">
      <td>{{ item.material_id }}</td>
      <td>{{ item.filename }}</td>
      <td>{{ item.title }}</td>
      <td>{% partial status_badge status_type=item.workflow_status status_text=item.get_workflow_status_display %}</td>
      <td>{{ item.faculty.abbreviation }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
```

### Step 5: Use Direct Partial Rendering for HTMX

**Django View:**

**File:** `src/apps/dashboard/views.py`

```python
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def status_badge_partial(request, status_value):
    """Render just the status badge for HTMX updates."""
    context = {
        'status_type': 'success' if status_value == 'Done' else 'info',
        'status_text': status_value,
    }
    # Render ONLY the partial
    return render(request, "components/partials.html#status_badge", context)
```

**URL config:**
```python
urlpatterns = [
    path('partial/status-badge/<str:status_value>', views.status_badge_partial, name='partial_status_badge'),
]
```

**Usage in template:**
```django
<div hx-get="{% url 'dashboard:partial_status_badge' item.workflow_status %}"
     hx-target="#status-container"
     hx-swap="innerHTML">
  {% partial status_badge status_type=item.workflow_status status_text=item.get_workflow_status_display %}
</div>
```

## Priority Order

**High Priority (Most used):**
1. `status_badge` - Used extensively throughout UI
2. `workflow_tabs` - Navigation component (dashboard)
3. `editable_cell` - Used in table rows (lots of usage)
4. `filter_dropdown` - Form component

**Medium Priority:**
5. `search_input` - Search component
6. Progress indicators
7. Stat cards

**Low Priority:**
8. Generic card containers
9. Toast notifications

## Benefits Achieved

### Before (include)
```django
{% include "components/_status_badge.html" with status_type="success" status_text="Done" %}
```
- All context variables available (pollution)
- No default parameters
- Can't define inline

### After (partial)
```django
{% partial status_badge status_type="success" status_text="Done" %}
```
- Only passed variables available
- Can define default parameters
- Can render inline
- Can access directly via `template.html#partial_name`

## Testing

### Manual Testing
1. Load dashboard - verify all partials render
2. Click workflow tabs - verify HTMX updates work
3. Filter by faculty - verify dropdown works
4. Edit inline cell - verify value saves
5. Check browser console for errors

### Integration Tests
```python
def test_partials_render(client):
    """Test that partials render correctly."""
    response = client.get('/dashboard/')
    assert response.status_code == 200
    assert b'To Do' in response.content
    assert b'In Progress' in response.content

def test_partial_direct_rendering(client):
    """Test direct partial rendering."""
    response = client.get('/dashboard/partial/status-badge/Done')
    assert response.status_code == 200
    assert b'Done' in response.content
```

## Success Criteria

- [ ] Partials file created with all high-priority components
- [ ] Dashboard converted to use partials
- [ ] Table rows converted to use partials
- [ ] HTMX interactions work correctly
- [ ] Direct partial rendering works (for AJAX updates)
- [ ] All tests pass
- [ ] No context pollution issues
- [ ] Performance is acceptable

## Estimated Time

**Total: 1 day**

- **Create partials file:** 3 hours
- **Convert dashboard components:** 2 hours
- **Convert table components:** 2 hours
- **Testing:** 1 hour

## Notes

### When to Use Partial vs Include

**Use Partials:**
- Reusable components with default parameters
- Components that need direct access (AJAX/HTMX)
- When you want context isolation

**Keep Using Includes:**
- Large template sections (layout includes)
- When you need full context access
- Template inheritance blocks

### Best Practices

1. **Organize by feature:** Keep related partials together
2. **Use descriptive names:** `status_badge` not `badge`
3. **Document parameters:** Add comments for required params
4. **Test in isolation:** Each partial should work independently

---

**Next Task:** [Task 1: Redis Caching](01-redis-caching.md) (Complete implementation)
