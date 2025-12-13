\*\*\*



\# Easy Access Platform (v2.0) - Master Development Guide

\*\*Date:\*\* December 8, 2025

\*\*Status:\*\* Ready for Implementation

\*\*Target Stack:\*\* Django 6.0, Python 3.12+, PostgreSQL 17, Docker, HTMX, Alpine.js, DaisyUI.



---



\## 1. Introduction \& Architecture



\### 1.1 Overview

This project refactors the legacy `ea-cli` tool into a robust, web-based platform. The original codebase can be found as git submodule `\ea-cli` in the root of this repo. In short, the new system ingests copyright data from Excel sheets, enriches it via external APIs (OSIRIS, Canvas), and provides a reactive dashboard for data entry and classification.



\*\*Key Constraints:\*\*

\*   \*\*Scale:\*\* 50k - 400k items.

\*   \*\*Environment:\*\* Internal University Network (VPN/Intranet).

\*   \*\*Storage:\*\* Local disk storage (NAS/Volume mapped) for PDFs.

\*   \*\*Auth:\*\* Standard Django Admin/Staff authentication.



\### 1.2 Tech Stack

\*   \*\*Backend:\*\* \[Django 6.0](https://docs.djangoproject.com/en/6.0/) (Native Tasks, Async).

\*   \*\*API:\*\* \[Django Shinobi](https://github.com/django-shinobi/django-shinobi) (Pydantic-based API schemas).

\*   \*\*Data Processing:\*\* \[Polars](https://pola.rs/) (High-performance Excel/CSV processing).

\*   \*\*Frontend:\*\* \[HTMX](https://htmx.org/) (Server interaction) + \[Alpine.js](https://alpinejs.dev/) (Client state) + \[DaisyUI](https://daisyui.com/) (Tailwind CSS Components).

\*   \*\*Infrastructure:\*\* Docker Compose, VS Code Dev Containers.



---



\## 2. Infrastructure \& Environment Setup



\### 2.1 File Structure

Initialize your repository with this exact structure.



```text

copyright-platform/

├── .devcontainer/

│   └── devcontainer.json        # VS Code Remote Config

├── docker/

│   ├── Dockerfile               # Python + Node (for Tailwind)

│   ├── entrypoint.sh            # Startup script

│   └── redis.conf               # Redis config

├── raw\_data/                    # Watch folder for Excel drops

│   └── .gitkeep

├── documents/                   # PDF Storage (Volume Mapped)

│   ├── downloads/

│   └── processed/

├── src/

│   ├── apps/

│   │   ├── api/                 # Shinobi Endpoints

│   │   ├── core/                # Models \& Shared Logic

│   │   ├── dashboard/           # UI Views (HTMX)

│   │   ├── documents/           # PDF Logic

│   │   ├── enrichment/          # External Integrations

│   │   └── ingest/              # Polars Logic \& Watchdog

│   ├── config/                  # Settings

│   │   ├── settings.py

│   │   ├── tasks.py             # Task Backend Config

│   │   └── urls.py

│   ├── static/                  # CSS/JS Assets

│   ├── templates/               # HTML Templates

│   └── manage.py

├── .env.example

├── docker-compose.yml

└── pyproject.toml

```



\### 2.2 Container Configuration



\*\*`pyproject.toml`\*\*

```toml

\[project]

name = "copyright-platform"

version = "2.0.0"

requires-python = ">=3.12"

dependencies = \[

&nbsp;   "django>=6.0",

&nbsp;   "django-shinobi",

&nbsp;   "django-htmx",

&nbsp;   "django-environ",

&nbsp;   "psycopg\[binary]",

&nbsp;   "redis",

&nbsp;   "django-redis-tasks", # Assumption: Community backend for Django 6 Tasks

&nbsp;   "polars\[xlsx,pyarrow]",

&nbsp;   "watchfiles",

&nbsp;   "uvicorn\[standard]",

&nbsp;   "httpx",

&nbsp;   "loguru",

&nbsp;   "pypdf"

]

```



\*\*`docker-compose.yml`\*\*

```yaml

services:

&nbsp; db:

&nbsp;   image: postgres:17-alpine

&nbsp;   environment:

&nbsp;     POSTGRES\_DB: copyright\_db

&nbsp;     POSTGRES\_USER: admin

&nbsp;     POSTGRES\_PASSWORD: dev\_password

&nbsp;   volumes:

&nbsp;     - postgres\_data:/var/lib/postgresql/data

&nbsp;   healthcheck:

&nbsp;     test: \["CMD-SHELL", "pg\_isready -U admin"]

&nbsp;     interval: 5s



&nbsp; redis:

&nbsp;   image: redis:7-alpine

&nbsp;   volumes:

&nbsp;     - redis\_data:/data

&nbsp;   healthcheck:

&nbsp;     test: \["CMD", "redis-cli", "ping"]

&nbsp;     interval: 5s



&nbsp; web:

&nbsp;   build: .

&nbsp;   command: python src/manage.py runserver 0.0.0.0:8000

&nbsp;   volumes:

&nbsp;     - .:/app

&nbsp;     - ./documents:/app/documents

&nbsp;   ports:

&nbsp;     - "8000:8000"

&nbsp;   depends\_on:

&nbsp;     db: {condition: service\_healthy}

&nbsp;     redis: {condition: service\_healthy}

&nbsp;   environment:

&nbsp;     - DATABASE\_URL=postgres://admin:dev\_password@db:5432/copyright\_db

&nbsp;     - REDIS\_URL=redis://redis:6379/0

&nbsp;     - DEBUG=True



&nbsp; # Django 6 Task Worker

&nbsp; worker:

&nbsp;   build: .

&nbsp;   # Assuming 'runworker' comes from the backend package or custom command

&nbsp;   command: python src/manage.py runworker

&nbsp;   volumes:

&nbsp;     - .:/app

&nbsp;     - ./documents:/app/documents

&nbsp;   depends\_on:

&nbsp;     - db

&nbsp;     - redis

&nbsp;   environment:

&nbsp;     - DATABASE\_URL=postgres://admin:dev\_password@db:5432/copyright\_db

&nbsp;     - REDIS\_URL=redis://redis:6379/0



&nbsp; # File Watcher for Excel Ingestion

&nbsp; watcher:

&nbsp;   build: .

&nbsp;   command: python src/manage.py watch

&nbsp;   volumes:

&nbsp;     - .:/app

&nbsp;     - ./raw\_data:/app/raw\_data

&nbsp;   depends\_on:

&nbsp;     - web

&nbsp;     - redis



volumes:

&nbsp; postgres\_data:

&nbsp; redis\_data:

```



\### 2.3 Django 6 Task Configuration (`src/config/settings.py`)

Django 6 separates the definition of tasks from the execution backend. We will use Redis.



```python

\# src/config/settings.py



TASKS = {

&nbsp;   "default": {

&nbsp;       "BACKEND": "django\_redis\_tasks.backend.RedisBackend",

&nbsp;       "OPTIONS": {

&nbsp;           "connection\_string": env("REDIS\_URL"),

&nbsp;           "queue\_name": "default",

&nbsp;       }

&nbsp;   }

}

```



---



\## 3. Data Modeling (Refined)



We have simplified the organization hierarchy based on review feedback. We use `models.JSONField` for flexible staging.



\*\*File:\*\* `src/apps/core/models.py`



```python

from django.db import models

from django.utils.translation import gettext\_lazy as \_



class TimestampedModel(models.Model):

&nbsp;   created\_at = models.DateTimeField(auto\_now\_add=True)

&nbsp;   modified\_at = models.DateTimeField(auto\_now=True)

&nbsp;   class Meta:

&nbsp;       abstract = True



\# -----------------------------------------------------------------------------

\# Organizations (Simplified)

\# -----------------------------------------------------------------------------



class OrganizationType(models.TextChoices):

&nbsp;   UNIVERSITY = "UNI", "University"

&nbsp;   FACULTY = "FAC", "Faculty"

&nbsp;   DEPARTMENT = "DEP", "Department"



class Organization(TimestampedModel):

&nbsp;   name = models.CharField(max\_length=2048, db\_index=True)

&nbsp;   abbreviation = models.CharField(max\_length=255, db\_index=True)

&nbsp;   org\_type = models.CharField(

&nbsp;       max\_length=10,

&nbsp;       choices=OrganizationType.choices,

&nbsp;       default=OrganizationType.FACULTY

&nbsp;   )

&nbsp;   parent = models.ForeignKey(

&nbsp;       'self', on\_delete=models.SET\_NULL, null=True, blank=True, related\_name='children'

&nbsp;   )



&nbsp;   class Meta:

&nbsp;       unique\_together = ('name', 'abbreviation')



&nbsp;   def \_\_str\_\_(self):

&nbsp;       return f"{self.abbreviation} ({self.get\_org\_type\_display()})"



\# -----------------------------------------------------------------------------

\# Copyright Data

\# -----------------------------------------------------------------------------



class CopyrightItem(TimestampedModel):

&nbsp;   material\_id = models.BigIntegerField(primary\_key=True)

&nbsp;   filename = models.CharField(max\_length=2048, null=True, blank=True)

&nbsp;   filehash = models.CharField(max\_length=255, null=True, blank=True)

&nbsp;

&nbsp;   # ... (Other fields as per original plan: Status, Author, Title, etc.) ...

&nbsp;

&nbsp;   canvas\_course\_id = models.BigIntegerField(null=True, blank=True)

&nbsp;

&nbsp;   class Meta:

&nbsp;       ordering = \['-modified\_at']

&nbsp;       indexes = \[

&nbsp;           models.Index(fields=\['workflow\_status', 'faculty']),

&nbsp;           models.Index(fields=\['filehash']),        # Duplicate detection

&nbsp;           models.Index(fields=\['canvas\_course\_id']), # API lookups

&nbsp;       ]



class StagedItem(TimestampedModel):

&nbsp;   """

&nbsp;   Temporary holding area for Excel rows before they become CopyrightItems.

&nbsp;   """

&nbsp;   class Status(models.TextChoices):

&nbsp;       PENDING = "PENDING", "Pending"

&nbsp;       PROCESSED = "PROCESSED", "Processed"

&nbsp;       ERROR = "ERROR", "Error"



&nbsp;   source\_file = models.CharField(max\_length=1024)

&nbsp;   status = models.CharField(max\_length=20, choices=Status.choices, default=Status.PENDING)

&nbsp;   payload = models.JSONField(default=dict) # Stores the raw Polars row

&nbsp;   error\_log = models.TextField(null=True, blank=True)

```



---



\## 4. Implementation Guidelines



\### 4.1 Ingestion Pipeline (Polars + Django 6 Tasks)



We handle Excel files in a non-blocking way.



\*\*1. The Watcher Command (`src/apps/ingest/management/commands/watch.py`)\*\*

Uses `watchfiles` to monitor `raw\_data/`. When a file appears, it triggers the task.



```python

from django.core.management.base import BaseCommand

from watchfiles import watch

from apps.ingest.tasks import ingest\_excel\_task



class Command(BaseCommand):

&nbsp;   def handle(self, \*args, \*\*options):

&nbsp;       self.stdout.write("Watching /raw\_data for .xlsx files...")

&nbsp;       for changes in watch('/app/raw\_data'):

&nbsp;           for change, path in changes:

&nbsp;               if path.endswith('.xlsx'):

&nbsp;                   # Enqueue the Django 6 Task

&nbsp;                   ingest\_excel\_task.enqueue(file\_path=path)

```



\*\*2. The Task (`src/apps/ingest/tasks.py`)\*\*

Uses Django 6 native task decorator.



```python

from django.tasks import task

import polars as pl

from apps.core.models import StagedItem



@task(queue\_name="default")

def ingest\_excel\_task(file\_path: str):

&nbsp;   try:

&nbsp;       # 1. Read with Polars (Super fast)

&nbsp;       df = pl.read\_excel(file\_path)

&nbsp;

&nbsp;       # 2. Convert to list of dictionaries

&nbsp;       rows = df.to\_dicts()

&nbsp;

&nbsp;       # 3. Bulk create StagedItems

&nbsp;       batch = \[

&nbsp;           StagedItem(source\_file=file\_path, payload=row)

&nbsp;           for row in rows

&nbsp;       ]

&nbsp;       StagedItem.objects.bulk\_create(batch, batch\_size=5000)

&nbsp;

&nbsp;       return f"Successfully staged {len(batch)} rows from {file\_path}"

&nbsp;

&nbsp;   except Exception as e:

&nbsp;       # In Django 6, this error is saved to TaskResult.errors

&nbsp;       raise e

```



\### 4.2 Frontend Pattern (HTMX + Alpine + DaisyUI)



Do not write standard Django Forms. Use this pattern for the Dashboard.



\*\*Template Structure (`dashboard.html`):\*\*

```html

{% extends "base.html" %}



{% block content %}

<div class="p-4" x-data="{ showUploadModal: false }">

&nbsp;

&nbsp;   <!-- Toolbar -->

&nbsp;   <div class="flex justify-between mb-4">

&nbsp;       <h1 class="text-2xl font-bold">Copyright Dashboard</h1>

&nbsp;       <button @click="showUploadModal = true" class="btn btn-primary">

&nbsp;           Upload Excel

&nbsp;       </button>

&nbsp;   </div>



&nbsp;   <!-- The Grid (HTMX Target) -->

&nbsp;   <div id="data-grid"

&nbsp;        hx-get="{% url 'dashboard:grid\_partial' %}"

&nbsp;        hx-trigger="load">

&nbsp;        <!-- Spinner while loading -->

&nbsp;        <span class="loading loading-spinner loading-lg"></span>

&nbsp;   </div>



&nbsp;   <!-- Upload Modal (DaisyUI + Alpine) -->

&nbsp;   <dialog class="modal" :class="{ 'modal-open': showUploadModal }">

&nbsp;       <div class="modal-box">

&nbsp;           <h3 class="font-bold text-lg">Upload Data</h3>

&nbsp;           <form hx-post="{% url 'api:trigger\_ingest' %}"

&nbsp;                 hx-swap="none"

&nbsp;                 @htmx:after-request="showUploadModal = false">

&nbsp;               <input type="file" name="file" class="file-input w-full max-w-xs" />

&nbsp;               <div class="modal-action">

&nbsp;                   <button type="submit" class="btn btn-success">Upload</button>

&nbsp;                   <button type="button" class="btn" @click="showUploadModal = false">Close</button>

&nbsp;               </div>

&nbsp;           </form>

&nbsp;       </div>

&nbsp;   </dialog>



</div>

{% endblock %}

```



\*\*View Logic (`src/apps/dashboard/views.py`):\*\*

```python

from django.template.response import TemplateResponse



def dashboard\_index(request):

&nbsp;   return TemplateResponse(request, "dashboard/dashboard.html", {})



def grid\_partial(request):

&nbsp;   # Standard filtering logic here

&nbsp;   items = CopyrightItem.objects.all()\[:50]

&nbsp;

&nbsp;   if request.htmx:

&nbsp;       return TemplateResponse(request, "dashboard/\_grid.html", {"items": items})

&nbsp;   return TemplateResponse(request, "dashboard/dashboard.html", {"items": items})

```



---



\## 5. Migration Strategy (Legacy to V2)



Since we cannot connect Tortoise ORM to the Django DB easily, we use a "Dump and Load" strategy.



1\.  \*\*Export V1 Data:\*\*

&nbsp;   In the legacy project, run a script using Polars to dump the SQLite/Postgres data to CSVs.

&nbsp;   ```python

&nbsp;   # Legacy Script

&nbsp;   import polars as pl

&nbsp;   # ... connection logic ...

&nbsp;   df = pl.read\_database(query="SELECT \* FROM copyright\_item", connection=conn)

&nbsp;   df.write\_csv("legacy\_export\_v1.csv")

&nbsp;   ```



2\.  \*\*Import to V2:\*\*

&nbsp;   Place `legacy\_export\_v1.csv` into `raw\_data/`.

&nbsp;   The `watch` command will pick it up, and create `StagedItem` records.



3\.  \*\*Migration Service:\*\*

&nbsp;   Write a specific service `MigrationService` that iterates over `StagedItem` where `source\_file` contains "legacy".

&nbsp;   \*   Map legacy columns to new `CopyrightItem` fields.

&nbsp;   \*   Set `workflow\_status` to `TODO` so users can verify them in the new UI.



---



\## 6. Development Workflow



1\.  \*\*Start the environment:\*\*

&nbsp;   ```bash

&nbsp;   docker compose up --build

&nbsp;   ```

&nbsp;   \*   This starts: Web Server (8000), Worker, File Watcher, DB, Redis.



2\.  \*\*Accessing the system:\*\*

&nbsp;   \*   Frontend: `http://localhost:8000`

&nbsp;   \*   API Docs: `http://localhost:8000/api/docs` (Shinobi auto-docs)



3\.  \*\*Applying Changes:\*\*

&nbsp;   \*   If you change models:

&nbsp;       ```bash

&nbsp;       docker compose exec web python src/manage.py makemigrations

&nbsp;       docker compose exec web python src/manage.py migrate

&nbsp;       ```

&nbsp;   \*   If you add dependencies: Update `pyproject.toml` and rebuild Docker.



4\.  \*\*Debugging:\*\*

&nbsp;   \*   Logs are streamed to the terminal.

&nbsp;   \*   Use `loguru` in code: `logger.info("Processing item...")`
