# Task 4: Django 6.0 Template Partials

## Overview

Evaluate Django 6.0's `{% partialdef %}` / `{% partial %}` syntax for template components.

**Current Status:** ✅ **COMPLETED (Decision: Keep Using `{% include %}`)**

**Decision:** After testing, determined that the existing `{% include %}` approach is more appropriate for this project. Django 6.0's `{% partial %}` syntax has limitations (cannot pass parameters like `{% partial name param=value %}`).

## What Was Done

### Investigation ✅

1. Created `partials.html` reference file documenting Django 6.0 partial syntax
2. Attempted to migrate from `{% include %}` to `{% partial %}`
3. Discovered syntax limitations
4. Reverted to `{% include %}` approach
5. Fixed a bug where invalid partial syntax had been introduced

### The Bug We Found and Fixed

**Problem:** Commit c0bd5aa introduced invalid syntax:
```django
{% partial workflow_tabs param=value %}  {# INVALID! #}
```

**Why It's Invalid:** Django 6.0's `{% partial %}` tag only accepts the partial name, not parameters. Parameters must be defined in the template context, not passed in the tag.

**Fix Applied:** Reverted to using `{% include %}` with `with` keyword:
```django
{% include "components/_workflow_tabs.html" with current_status=status_var %}
```

### Files Involved

**Template Components** (all using `{% include %}`):
- `src/templates/components/_workflow_tabs.html` - Workflow status filter tabs
- `src/templates/components/_filter_dropdown.html` - Faculty filter dropdown
- `src/templates/components/_filter_search.html` - Search input
- `src/templates/components/_editable_cell.html` - Inline editing cells
- `src/templates/components/_status_badge.html` - Status badges

**Reference File:**
- `src/templates/partials.html` - Kept for reference, shows Django 6.0 partial syntax

## Django 6.0 Partial Syntax Limitations

### What DOESN'T Work

```django
{# ❌ This is INVALID in Django 6.0 #}
{% partial workflow_tabs current_status="ToDo" %}
```

**Error:** `partial` tag only takes the partial name as argument, not keyword arguments.

### What DOES Work

```django
{# ✅ Define partial with defaults #}
{% partialdef workflow_tabs current_status="all" %}
  <div class="tabs">
    <button class="tab {% if current_status == 'all' %}tab-active{% endif %}">All</button>
    <button class="tab {% if current_status == 'ToDo' %}tab-active{% endif %}">To Do</button>
  </div>
{% endpartialdef %}

{# ✅ Then render it #}
{% partial workflow_tabs %}
```

**But wait!** The partial uses `current_status` from the **parent context**, not from parameters. This means:
- You can't pass different values easily
- Partial relies on context variable names
- No encapsulation benefit

### Our Current Approach: `{% include %}`

```django
{# Define component #}
{# src/templates/components/_workflow_tabs.html #}
<div class="tabs">
  <button class="tab {% if current_status == 'all' %}tab-active{% endif %}">All</button>
  <button class="tab {% if current_status == 'ToDo' %}tab-active{% endif %}">To Do</button>
</div>

{# Use component #}
{% include "components/_workflow_tabs.html" with current_status="ToDo" %}
```

**Benefits:**
- ✅ Explicit parameter passing via `with`
- ✅ Clear component boundaries
- ✅ Familiar to Django developers
- ✅ Works reliably

## Why We Kept `{% include %}`

### Reason 1: Parameter Passing

**With partials:**
```django
{# Can't do this: #}
{% partial status_badge status_type="success" %}

{# Must do this: #}
{% with status_type="success" %}
  {% partial status_badge %}
{% endwith %}
```

**With includes:**
```django
{% include "components/_status_badge.html" with status_type="success" %}
```

### Reason 2: Context Isolation

Includes with `with` keyword provide clean context isolation:
```django
{% include "components/_editable_cell.html" with item_id=item.id field_name="title" value=item.title %}
```

Only `item_id`, `field_name`, and `value` are available in the component.

### Reason 3: HTMX Compatibility

Our HTMX patterns work seamlessly with includes:
```django
<div hx-get="{% url 'dashboard:update_row' item.id %}"
     hx-target="#row-{{ item.id }}"
     hx-swap="outerHTML">
  {% include "components/_editable_cell.html" with item=item %}
</div>
```

## Testing Results

### Manual Testing ✅

- ✅ Dashboard loads without errors
- ✅ All workflow tabs render correctly
- ✅ Filter dropdown works
- ✅ Search input functions
- ✅ Editable cells update via HTMX
- ✅ Status badges display
- ✅ No template syntax errors
- ✅ No console errors

### Automated Tests ✅

```
src/apps/dashboard/tests/test_views.py::TestDashboardRendering::test_dashboard_renders PASSED
src/apps/dashboard/tests/test_views.py::TestDashboardRendering::test_workflow_tabs_render PASSED
```

## Current Template Structure

```
src/templates/
├── components/
│   ├── _workflow_tabs.html       # ✅ Using include
│   ├── _filter_dropdown.html     # ✅ Using include
│   ├── _filter_search.html       # ✅ Using include
│   ├── _editable_cell.html       # ✅ Using include
│   └── _status_badge.html        # ✅ Using include
├── partials.html                 # Reference only (kept for documentation)
└── dashboard/
    ├── dashboard.html
    ├── _table.html
    ├── _table_rows.html
    └── _detail_panel.html
```

## Usage Examples

### Workflow Tabs Component

**Component:** `src/templates/components/_workflow_tabs.html`
```django
<div class="tabs tabs-boxed bg-base-200 p-2" role="tablist">
  <button role="tab"
          class="tab {% if current_status == 'all' %}tab-active{% endif %}"
          hx-get="{% url 'dashboard:index' %}?status=all"
          hx-target="#table-container"
          hx-push-url="true">
    All
  </button>
  {# ... more tabs ... #}
</div>
```

**Usage:**
```django
{% include "components/_workflow_tabs.html" with current_status=current_filters.status %}
```

### Editable Cell Component

**Component:** `src/templates/components/_editable_cell.html`
```django
<div class="editable-cell" data-field="{{ field_name }}" data-item-id="{{ item_id }}">
  {% if choices %}
    <select name="{{ field_name }}"
            class="select select-bordered select-xs"
            hx-post="{% url 'dashboard:update_inline' item_id %}"
            hx-trigger="change"
            hx-swap="outerHTML">
      {% for choice_value, choice_label in choices %}
        <option value="{{ choice_value }}" {% if choice_value == value %}selected{% endif %}>
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
</div>
```

**Usage:**
```django
{% include "components/_editable_cell.html" with item_id=item.material_id field_name="title" value=item.title %}
```

## Success Criteria

- ✅ All template components render without errors
- ✅ HTMX interactions work correctly
- ✅ No template syntax errors
- ✅ All dashboard tests pass
- ✅ Invalid partial syntax removed
- ✅ Documentation updated (partials.html kept as reference)

## Files Modified

- `src/templates/partials.html` - Created as reference (not actually used)
- All component templates verified to use correct `{% include %}` syntax

## Lessons Learned

1. **Django 6.0 partials have parameter passing limitations** - The `{% partial %}` tag doesn't accept keyword arguments like `{% partial name param=value %}`

2. **The `{% include %}` with `with` keyword is superior for our use case** - Provides explicit parameter passing and clear context isolation

3. **Test before committing** - The invalid partial syntax was caught during testing, not during development

4. **Keep reference documentation** - The `partials.html` file is useful for understanding Django 6.0's capabilities, even if we don't use them

## Future Considerations

If Django's partial syntax evolves to support parameter passing better, we could reconsider:
- Currently: `{% include "component.html" with param=value %}`
- Future: `{% partial component param=value %}` (if/when supported)

For now, `{% include %}` with `with` is the right choice.

---

**Next Task:** [Task 5: Error Handling](05-error-handling.md) (Completed - retry logic implemented)
