This is a standalone Django 5.x/6.0 demo project structure. It is meant to replace the exported excel files from the legacy `ea-cli` implementation, but it is not meant to be fully complete -- instead this should be seen as a starting point or declaration of intent. It features a dense data grid, inline editing via HTMX, and workflow filtering (Inbox/In Progress/Done).

### Prerequisites
You need `django`, `faker`, and `htmx` (usually handled via CDN in templates, but `django-htmx` is good practice).

### Instructions to Run
1.  Create a folder `ea_dashboard_demo`.
2.  Create the files below.
3.  Run `python manage.py migrate`.
4.  Run `python manage.py seed_data`.
5.  Run `python manage.py runserver`.
6.  Visit `http://127.0.0.1:8000/`.

---

### 1. Project Configuration (`ea_dashboard_demo/settings.py`)
*Minimal settings to get running with HTMX and Templates.*

```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'django-insecure-demo-key'
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core', # Our app
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ea_dashboard_demo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ea_dashboard_demo.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
```

### 2. URL Configuration (`ea_dashboard_demo/urls.py`)

```python
from django.contrib import admin
from django.urls import path
from core.views import DashboardView, UpdateItemFieldView, ItemDetailView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', DashboardView.as_view(), name='dashboard'),
    path('item/<int:pk>/update/', UpdateItemFieldView.as_view(), name='update_item'),
    path('item/<int:pk>/detail/', ItemDetailView.as_view(), name='item_detail'),
]
```

### 3. The Core App Models (`core/models.py`)
*Adapted from your provided models, simplified for the demo but keeping the "Workflow" logic.*

```python
from django.db import models
from django.utils.translation import gettext_lazy as _

class Faculty(models.Model):
    name = models.CharField(max_length=255)
    abbreviation = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.abbreviation

class CopyrightItem(models.Model):
    class WorkflowStatus(models.TextChoices):
        TODO = 'ToDo', 'Inbox'
        IN_PROGRESS = 'InProgress', 'In Progress'
        DONE = 'Done', 'Done'

    class ClassificationV2(models.TextChoices):
        UNKNOWN = 'Onbekend', 'Unknown'
        OPEN = 'Ja (open licentie)', 'Open License'
        OWN_WORK = 'Ja (eigen werk)', 'Own Work'
        NO = 'Nee', 'No (Infringement)'
        EASY_ACCESS = 'Ja (easy access)', 'Easy Access'

    material_id = models.AutoField(primary_key=True)

    # Metadata
    title = models.CharField(max_length=2048, null=True)
    author = models.CharField(max_length=2048, null=True)
    filename = models.CharField(max_length=2048, null=True)

    # Relations
    faculty = models.ForeignKey(Faculty, on_delete=models.SET_NULL, null=True, to_field='abbreviation')
    course_code = models.CharField(max_length=50)
    course_name = models.CharField(max_length=255)

    # Workflow Data (The fields users edit)
    workflow_status = models.CharField(
        max_length=20,
        choices=WorkflowStatus.choices,
        default=WorkflowStatus.TODO,
        db_index=True
    )
    classification = models.CharField(
        max_length=50,
        choices=ClassificationV2.choices,
        default=ClassificationV2.UNKNOWN
    )
    remarks = models.TextField(blank=True, null=True)

    # Audit
    modified_at = models.DateTimeField(auto_now=True)

    def get_badge_color(self):
        """Logic moved from constants.py to model for templates"""
        if self.workflow_status == self.WorkflowStatus.DONE:
            return "bg-green-100 text-green-800 border-green-200"
        elif self.workflow_status == self.WorkflowStatus.IN_PROGRESS:
            return "bg-blue-100 text-blue-800 border-blue-200"
        return "bg-gray-100 text-gray-800 border-gray-200"

    def __str__(self):
        return self.filename or "Untitled"
```

### 4. Views & HTMX Logic (`core/views.py`)
*This replaces the Excel file handling. Note the `UpdateItemFieldView` which handles the inline editing.*

```python
from django.views.generic import ListView, DetailView, View
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse
from .models import CopyrightItem, Faculty
from django.db.models import Q

class DashboardView(ListView):
    model = CopyrightItem
    template_name = 'core/dashboard.html'
    context_object_name = 'items'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related('faculty').order_by('material_id')

        # Filtering (Replacing Excel Autofilters)
        status = self.request.GET.get('status')
        faculty = self.request.GET.get('faculty')
        search = self.request.GET.get('search')

        # Default view is Inbox if nothing selected
        if not status:
            status = 'ToDo'

        if status != 'All':
            qs = qs.filter(workflow_status=status)

        if faculty:
            qs = qs.filter(faculty__abbreviation=faculty)

        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(course_code__icontains=search) |
                Q(filename__icontains=search)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['faculties'] = Faculty.objects.all()
        # Pass current filters to context to keep UI state
        context['current_status'] = self.request.GET.get('status', 'ToDo')
        context['current_faculty'] = self.request.GET.get('faculty', '')
        context['current_search'] = self.request.GET.get('search', '')

        # Pass Enum choices for dropdowns
        context['classification_choices'] = CopyrightItem.ClassificationV2.choices
        context['workflow_choices'] = CopyrightItem.WorkflowStatus.choices
        return context

    def render_to_response(self, context, **response_kwargs):
        # HTMX Support: If request is from HTMX, return only the table rows or the table container
        if self.request.headers.get('HX-Request'):
            return render(self.request, 'core/partials/table_rows.html', context)
        return super().render_to_response(context, **response_kwargs)

class UpdateItemFieldView(View):
    """
    Handles inline editing from the table.
    Replaces: Opening Excel, finding row, clicking dropdown, saving.
    """
    def post(self, request, pk):
        item = get_object_or_404(CopyrightItem, pk=pk)

        # Determine what field is being updated
        field = request.POST.get('field')
        value = request.POST.get('value')

        if field == 'classification':
            item.classification = value
            # Automation: If classified, move to InProgress if currently ToDo
            if item.workflow_status == CopyrightItem.WorkflowStatus.TODO:
                item.workflow_status = CopyrightItem.WorkflowStatus.IN_PROGRESS

        elif field == 'workflow_status':
            item.workflow_status = value

        elif field == 'remarks':
            item.remarks = value

        item.save()

        # Return the updated row (or just the cell)
        context = {
            'item': item,
            'classification_choices': CopyrightItem.ClassificationV2.choices,
            'workflow_choices': CopyrightItem.WorkflowStatus.choices
        }
        return render(request, 'core/partials/item_row.html', context)

class ItemDetailView(DetailView):
    """
    The 'Split View' replacing opening a PDF separately.
    """
    model = CopyrightItem
    template_name = 'core/partials/item_detail.html'
```

### 5. Mock Data Seeder (`core/management/commands/seed_data.py`)

```python
from django.core.management.base import BaseCommand
from core.models import CopyrightItem, Faculty
from faker import Faker
import random

class Command(BaseCommand):
    help = 'Seeds database with mock data for demo'

    def handle(self, *args, **kwargs):
        fake = Faker()

        # Create Faculties
        faculties = ['BMS', 'EEMCS', 'ET', 'ITC', 'TNW']
        db_facs = []
        for f in faculties:
            fac, _ = Faculty.objects.get_or_create(name=f"Faculty of {f}", abbreviation=f)
            db_facs.append(fac)

        # Create Items
        self.stdout.write("Generating 100 items...")
        items = []
        for _ in range(100):
            status = random.choice(CopyrightItem.WorkflowStatus.values)

            # Logic: Most Done items should be classified
            classification = CopyrightItem.ClassificationV2.UNKNOWN
            if status == CopyrightItem.WorkflowStatus.DONE:
                classification = random.choice(CopyrightItem.ClassificationV2.values)

            items.append(CopyrightItem(
                title=fake.catch_phrase(),
                author=fake.name(),
                filename=f"{fake.word()}_{random.randint(100,999)}.pdf",
                faculty=random.choice(db_facs),
                course_code=f"202400{random.randint(100,999)}",
                course_name=fake.job(),
                workflow_status=status,
                classification=classification,
                remarks=fake.sentence() if random.random() > 0.7 else ""
            ))

        CopyrightItem.objects.bulk_create(items)
        self.stdout.write(self.style.SUCCESS('Data seeded successfully.'))
```

### 6. Templates

#### `core/templates/core/base.html`
*Includes Tailwind via CDN for immediate style.*

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Easy Access Workflow</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <!-- Add CSRF to HTMX -->
    <script>
        document.body.addEventListener('htmx:configRequest', (event) => {
            event.detail.headers['X-CSRFToken'] = '{{ csrf_token }}';
        });
    </script>
    <style>
        /* Custom scrollbar to mimic the "Dense" feel */
        .dense-table td { padding-top: 0.25rem; padding-bottom: 0.25rem; }
    </style>
</head>
<body class="bg-gray-50 h-screen flex flex-col overflow-hidden text-sm text-gray-800">
    {% block content %}{% endblock %}
</body>
</html>
```

#### `core/templates/core/dashboard.html`
*The main layout replacing the Excel Sheet.*

```html
{% extends 'core/base.html' %}

{% block content %}
<!-- Header / Toolbar -->
<header class="bg-white border-b border-gray-200 p-4 flex justify-between items-center shadow-sm z-10">
    <div class="flex items-center gap-4">
        <h1 class="text-xl font-bold text-slate-800">EA Workflow</h1>

        <!-- Workflow Tabs (Inbox Logic) -->
        <div class="flex bg-gray-100 rounded-lg p-1 gap-1">
            {% for status, label in workflow_choices %}
            <button
                hx-get="{% url 'dashboard' %}"
                hx-target="#table-container"
                hx-vals='{"status": "{{ status }}"}'
                name="status"
                value="{{ status }}"
                class="px-3 py-1.5 rounded-md transition-colors {% if current_status == status %}bg-white shadow text-blue-600 font-medium{% else %}text-gray-500 hover:text-gray-700{% endif %}"
                onclick="document.querySelectorAll('button[name=status]').forEach(b => b.classList.remove('bg-white','shadow','text-blue-600')); this.classList.add('bg-white','shadow','text-blue-600');">
                {{ label }}
            </button>
            {% endfor %}
            <button
                hx-get="{% url 'dashboard' %}"
                hx-target="#table-container"
                hx-vals='{"status": "All"}'
                class="px-3 py-1.5 rounded-md text-gray-500 hover:text-gray-700">
                All
            </button>
        </div>
    </div>

    <!-- Filters & Search -->
    <div class="flex gap-2">
        <select
            name="faculty"
            class="border border-gray-300 rounded px-2 py-1"
            hx-get="{% url 'dashboard' %}"
            hx-target="#table-container"
            hx-include="[name='status']">
            <option value="">All Faculties</option>
            {% for f in faculties %}
            <option value="{{ f.abbreviation }}">{{ f.abbreviation }}</option>
            {% endfor %}
        </select>
        <input
            type="text"
            name="search"
            placeholder="Search title/code..."
            class="border border-gray-300 rounded px-2 py-1 w-64"
            hx-get="{% url 'dashboard' %}"
            hx-trigger="keyup changed delay:500ms"
            hx-target="#table-container"
            hx-include="[name='status']">
    </div>
</header>

<!-- Main Content Area: Split View -->
<div class="flex flex-1 overflow-hidden">

    <!-- Left: Data Grid (Excel Replacement) -->
    <div class="flex-1 overflow-auto bg-white" id="table-container">
        {% include 'core/partials/table_rows.html' %}
    </div>

    <!-- Right: Context/PDF Panel (Hidden by default, shown via HTMX) -->
    <div id="detail-panel" class="w-1/3 border-l border-gray-200 bg-gray-50 overflow-y-auto hidden">
        <div class="p-8 text-center text-gray-400 mt-20">
            Select an item to view details
        </div>
    </div>
</div>
{% endblock %}
```

#### `core/templates/core/partials/table_rows.html`
*The Table component.*

```html
<table class="w-full text-left border-collapse dense-table">
    <thead class="bg-gray-50 sticky top-0 z-10 shadow-sm text-xs font-semibold text-gray-500 uppercase tracking-wider">
        <tr>
            <th class="p-3 border-b">ID</th>
            <th class="p-3 border-b">Faculty</th>
            <th class="p-3 border-b w-1/4">File Info</th>
            <th class="p-3 border-b">Classification</th>
            <th class="p-3 border-b">Workflow</th>
            <th class="p-3 border-b">Remarks</th>
            <th class="p-3 border-b">Actions</th>
        </tr>
    </thead>
    <tbody class="divide-y divide-gray-100">
        {% for item in items %}
            {% include 'core/partials/item_row.html' %}
        {% empty %}
            <tr>
                <td colspan="7" class="p-8 text-center text-gray-400">No items found in this bucket.</td>
            </tr>
        {% endfor %}
    </tbody>
</table>

<!-- Pagination (Simple implementation) -->
<div class="p-4 border-t border-gray-200 bg-gray-50 flex justify-center">
    <span class="text-xs text-gray-500">
        Page {{ page_obj.number }} of {{ page_obj.paginator.num_pages }}
    </span>
</div>
```

#### `core/templates/core/partials/item_row.html`
*The individual row logic. Crucial for the "Inline Edit" demo.*

```html
<tr class="hover:bg-blue-50 transition-colors group">
    <td class="p-3 text-gray-400 font-mono text-xs">#{{ item.material_id }}</td>

    <td class="p-3">
        <span class="px-2 py-0.5 rounded text-xs font-medium
            {% if item.faculty.abbreviation == 'BMS' %}bg-green-100 text-green-700{% endif %}
            {% if item.faculty.abbreviation == 'EEMCS' %}bg-blue-100 text-blue-700{% endif %}
            {% if item.faculty.abbreviation == 'ET' %}bg-orange-100 text-orange-700{% endif %}">
            {{ item.faculty.abbreviation }}
        </span>
    </td>

    <td class="p-3">
        <div class="font-medium text-gray-900 truncate w-48" title="{{ item.title }}">
            {{ item.filename }}
        </div>
        <div class="text-xs text-gray-500">
            {{ item.course_code }} • {{ item.author }}
        </div>
    </td>

    <!-- Inline Edit: Classification Dropdown -->
    <td class="p-3">
        <select
            name="value"
            hx-post="{% url 'update_item' pk=item.pk %}"
            hx-vals='{"field": "classification"}'
            hx-target="closest tr"
            hx-swap="outerHTML"
            class="text-xs border-0 bg-transparent hover:bg-white hover:border hover:border-gray-300 rounded px-1 py-0.5 cursor-pointer w-full focus:ring-1 focus:ring-blue-500 transition-all
            {% if item.classification == 'Onbekend' %}text-red-500 font-medium{% else %}text-gray-700{% endif %}">
            {% for val, label in classification_choices %}
            <option value="{{ val }}" {% if item.classification == val %}selected{% endif %}>
                {{ label }}
            </option>
            {% endfor %}
        </select>
    </td>

    <!-- Inline Edit: Workflow Status -->
    <td class="p-3">
        <select
            name="value"
            hx-post="{% url 'update_item' pk=item.pk %}"
            hx-vals='{"field": "workflow_status"}'
            hx-target="closest tr"
            hx-swap="outerHTML"
            class="text-xs border px-2 py-0.5 rounded-full font-medium appearance-none cursor-pointer text-center {{ item.get_badge_color }}">
            {% for val, label in workflow_choices %}
            <option value="{{ val }}" {% if item.workflow_status == val %}selected{% endif %}>
                {{ label }}
            </option>
            {% endfor %}
        </select>
    </td>

    <!-- Inline Edit: Remarks (Click to edit) -->
    <td class="p-3">
        <input
            type="text"
            name="value"
            value="{{ item.remarks|default:'' }}"
            placeholder="Add remark..."
            hx-post="{% url 'update_item' pk=item.pk %}"
            hx-vals='{"field": "remarks"}'
            hx-trigger="change"
            hx-target="closest tr"
            hx-swap="outerHTML"
            class="w-full bg-transparent border-b border-transparent hover:border-gray-300 focus:border-blue-500 focus:outline-none text-xs placeholder-gray-300">
    </td>

    <!-- Action: View Detail -->
    <td class="p-3">
        <button
            hx-get="{% url 'item_detail' pk=item.pk %}"
            hx-target="#detail-panel"
            onclick="document.getElementById('detail-panel').classList.remove('hidden')"
            class="text-gray-400 hover:text-blue-600">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
        </button>
    </td>
</tr>
```

#### `core/templates/core/partials/item_detail.html`
*The context panel showing how web UI is better than Excel (layout).*

```html
<div class="h-full flex flex-col">
    <div class="p-4 border-b bg-white flex justify-between items-start">
        <div>
            <h2 class="font-bold text-lg text-gray-800">{{ object.filename }}</h2>
            <p class="text-xs text-gray-500">{{ object.course_code }} - {{ object.course_name }}</p>
        </div>
        <button onclick="document.getElementById('detail-panel').classList.add('hidden')" class="text-gray-400 hover:text-gray-600">×</button>
    </div>

    <!-- Mock PDF Preview -->
    <div class="flex-1 bg-gray-200 p-4 flex items-center justify-center">
        <div class="bg-white shadow-lg w-full h-full flex items-center justify-center text-gray-400 flex-col gap-2">
            <svg class="w-16 h-16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path></svg>
            <span>PDF Preview Mock</span>
        </div>
    </div>

    <!-- Osiris Data (Enrichment Context) -->
    <div class="p-4 bg-white border-t">
        <h3 class="font-bold text-xs uppercase text-gray-500 mb-2">Osiris Context</h3>
        <div class="grid grid-cols-2 gap-4 text-xs">
            <div>
                <span class="text-gray-400 block">Teacher</span>
                <span class="font-medium">{{ object.author }}</span>
            </div>
            <div>
                <span class="text-gray-400 block">Students</span>
                <span class="font-medium">142</span>
            </div>
            <div>
                <span class="text-gray-400 block">Last Scan</span>
                <span class="font-medium">{{ object.modified_at|date:"Y-m-d" }}</span>
            </div>
        </div>

        <div class="mt-4 pt-4 border-t">
            <button class="w-full bg-blue-600 text-white py-2 rounded text-xs font-bold hover:bg-blue-700">
                Rescan in Osiris
            </button>
        </div>
    </div>
</div>
```
