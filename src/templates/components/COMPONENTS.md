# Template Components

This directory contains reusable Django template components with UT styling.

## Components

### `_toast.html`

Toast notification component for user feedback.

**Usage:**
Typically triggered via HTMX event headers rather than direct includes.

**Parameters:**
- `type`: success, error, warning, info
- `message`: The message to display
- `duration`: Auto-dismiss duration in ms (default: 3000)

**Integration:**
The dashboard uses HTMX `HX-Trigger` headers combined with Alpine.js event listeners:
```python
# In views.py
response["HX-Trigger"] = "show-success-toast:Update successful!"

# In dashboard.html
@show-success-toast.window="toast = { type: 'success', message: $event.detail }"
```

**Features:**
- Auto-dismissing after 3 seconds
- Smooth enter/leave animations
- Dismissible with click
- Fixed positioning (top-right)

---

### `_filter_dropdown.html`

Reusable dropdown filter component for HTMX-powered filtering.

**Usage:**
```django
{% include "components/_filter_dropdown.html" with name="faculty" options=faculties selected=current_filters.faculty include='[name="status"],[name="search"]' %}
```

**Parameters:**
- `name`: Field name for the form input (required)
- `label`: Display label for "All" option (default: "All")
- `options`: List of (value, label) tuples, or queryset with `.value/.label` or `.abbreviation/.name` (required)
- `selected`: Currently selected value
- `include`: Additional selectors to include in HTMX request (e.g., `'[name="status"],[name="search"]'`)

**Features:**
- Auto-detects tuple format or object format
- Includes HTMX attributes for dynamic filtering
- Automatically handles selection state

**Note:** For simple static dropdowns (like per-page options), it's fine to hardcode them directly rather than using this component.

---

### `_filter_search.html`

Search input component with debounced HTMX requests.

**Usage:**
```django
{% include "components/_filter_search.html" with value=current_filters.search include='[name="status"],[name="faculty"]' %}
```

**Parameters:**
- `value`: Current search value
- `placeholder`: Placeholder text (default: "Search...")
- `include`: Additional selectors to include in HTMX request

**Features:**
- 300ms debounce on keyup
- Search icon button
- HTMX-powered dynamic filtering

---

### `_workflow_tabs.html`

Workflow status tabs for filtering CopyrightItems.

**Usage:**
```django
{% include "components/_workflow_tabs.html" with current_status="ToDo" %}
```

**Parameters:**
- `current_status`: Selected workflow status (default: "ToDo")
- `workflow_choices`: List of (value, label) tuples for status options
- `filter_counts`: Dict of status -> count for badges
- `current_filters`: Current filter state (status, faculty, search, per_page)

---

### `_status_badge.html`

Status badge indicator with conditional styling.

**Usage:**
```django
{% include "components/_status_badge.html" with status="completed" %}
{% include "components/_status_badge.html" with status="running" text="Processing..." %}
```

**Parameters:**
- `status`: Status value (pending, running, completed, failed, partial, staging, processing)
- `text`: Custom text (optional, defaults to status title)
- `badge_class`: Additional CSS classes (optional)

---

### `_editable_cell.html`

Generic inline-edit component for table cells with HTMX.

**Usage:**
```django
{% include "components/_editable_cell.html" with item_id=item.material_id field_name="v2_manual_classification" value=item.v2_manual_classification choices=classification_choices %}
```

**Parameters:**
- `item_id`: Material ID for the item (required)
- `field_name`: Name of field to update (required)
- `value`: Current value
- `choices`: List of (value, label) tuples for select dropdowns
- `input_type`: "select" or "text" (default: "select")
- `badge`: If true, style as badge (for workflow status)
- `warning`: If true, highlight in red when value is "Onbekend"

---

### `_button.html`

UT-styled button component.

**Usage:**
```django
{% include "components/_button.html" with label="Click Me" %}
{% include "components/_button.html" with label="Submit" icon="<svg>...</svg>" %}
{% include "components/_button.html" with label="Delete" variant="error" %}
```

**Parameters:**
- `label`: Button text (required)
- `variant`: Color variant (default, primary, success, warning, error, ghost, outline)
- `size`: Button size (xs, sm, md, lg, xl)
- `icon`: SVG icon to display before label
- `type`: Button type (button, submit, reset)
- `class`: Additional CSS classes

---

### `_progress.html`

Progress bar component with optional label and status.

**Usage:**
```django
{% include "components/_progress.html" with value=45 max=100 %}
{% include "components/_progress.html" with value=75 label="Loading..." %}
```

**Parameters:**
- `value`: Current progress value (required)
- `max`: Maximum value (default: 100)
- `label`: Optional label text
- `status`: Status variant (default, success, warning, error)
- `animated`: Add shimmer animation (default: true)

---

### `_stat_card.html`

Stat card for displaying metrics.

**Usage:**
```django
{% include "components/_stat_card.html" with value="1,234" label="Total Items" %}
{% include "components/_stat_card.html" with value="456" label="Completed" color="success" %}
```

**Parameters:**
- `value`: The stat value to display (required)
- `label`: The stat label (required)
- `color`: Color variant (default, primary, success, warning, error, info)
- `icon`: SVG icon to display above the value
- `href`: Optional link to make the card clickable

---

### `_card.html`

Generic card component with optional accent border.

**Usage:**
```django
{% include "components/_card.html" with title="Card Title" %}
{% include "components/_card.html" with title="Card Title" content="Custom content" %}
{% include "components/_card.html" with title="Card Title" accent="success" %}
```

**Parameters:**
- `title`: Card title (required)
- `content`: Custom content body (optional, default uses body block)
- `accent`: Border accent color (default, primary, success, warning, error)
- `icon`: SVG icon to display next to title
- `class`: Additional CSS classes

## Notes

- All components use UT (University of Twente) styling
- HTMX is used for dynamic interactions
- Alpine.js for client-side state management
- DaisyUI (Tailwind CSS) for component styling
