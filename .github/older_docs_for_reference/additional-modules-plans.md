
Below you can find the implementation plans for additional modules to expand the ea-cli-django project: adding a machine learning classification system, and an interactive classification widget for marimo (or jupyter) notebooks; along with a revised master dev plan.

---

Here is the implementation plan for the **Intelligence Layer (Classification System)**. This document assumes the Platform v2.0 (Polars, Django 6, Docker) is active.

This system is designed as an add-on layer that listens to data changes and asynchronously updates classifications using a **Hybrid Funnel (Rules + ML)** approach.

---

# Classification & Intelligence Module - Implementation Plan
**Date:** December 13, 2025
**Dependencies:** Requires `copyright-platform` (v2.0 base).

## 1. Architecture & Strategy

We will encapsulate all intelligence logic into a new dedicated Django app: **`apps.classification`**.

### 1.1 The "Hybrid Funnel" Concept
To maximize accuracy and automation, every `CopyrightItem` flows through this decision pipeline:

1.  **Gate 1: The Judge (Hard Rules)**
    *   *Input:* structured data (ISBN, Publisher, matched Teacher names).
    *   *Logic:* Boolean logic (Python Classes).
    *   *Outcome:* If matched, apply classification **deterministically** and **stop**.
2.  **Gate 2: The Analyzer (Feature Extraction)**
    *   *Input:* Metadata, PDF text, "Heuristic" scores (e.g., fuzzy string matching).
    *   *Outcome:* A rich feature vector (dictionary).
3.  **Gate 3: The Predictor (CatBoost Model)**
    *   *Input:* Feature vector.
    *   *Logic:* Gradient boosted decision trees trained on historical data.
    *   *Outcome:* A **suggested** classification and a **confidence score** (0.0 - 1.0).

---

## 2. Integration with Base Platform

### 2.1 File Structure
Add the following folder structure to the existing `src/apps/` directory.

```text
src/apps/classification/
├── __init__.py
├── models.py             # Empty (Using core models, maybe ModelArtifacts)
├── services.py           # The public API for other apps (Entry Point)
├── pipeline/
│   ├── __init__.py
│   ├── rules.py          # Hard Logic (The Judge)
│   ├── heuristics.py     # Fuzzy matching & calculation logic
│   └── features.py       # Prepares data for CatBoost
├── ml/
│   ├── __init__.py
│   ├── training.py       # Logic to train/retrain model
│   ├── inference.py      # Logic to load model & predict
│   └── registry.py       # Manage model files (v1, v2)
├── management/
│   └── commands/
│       └── train_model.py
└── tasks.py              # Background worker wrappers
```

### 2.2 Data Model Updates
We need to modify the **Source of Truth** (`apps.core.models`) to accommodate predictions.

**Modify:** `src/apps/core/models.py`

```python
# Add fields to CopyrightItem
class CopyrightItem(TimestampedModel):
    # ... existing fields ...

    # Prediction Result
    v2_predicted_classification = models.CharField(
        max_length=100,
        choices=ClassificationV2.choices,
        null=True, blank=True
    )
    v2_prediction_confidence = models.FloatField(
        default=0.0,
        help_text="Confidence score (0.0 - 1.0) of the ML model."
    )

    # Audit Trail
    auto_classified_by_rule = models.CharField(
        max_length=255,
        null=True, blank=True,
        help_text="Name of the Hard Rule that applied the classification."
    )
    classification_metadata = models.JSONField(
        default=dict,
        help_text="Debug data: SHAP values, specific feature inputs used."
    )
```

---

## 3. Implementation Details

### 3.1 Phase 1: The Rule Engine (Gate 1)

**File:** `src/apps/classification/pipeline/rules.py`

We use the **Policy Pattern** to make rules testable and isolated.

```python
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from apps.core.models import CopyrightItem, ClassificationV2, Person

class ClassificationRule(ABC):
    name: str = "BaseRule"

    @abstractmethod
    def evaluate(self, item: CopyrightItem) -> Optional[str]:
        """Return a classification choice if the rule applies, else None."""
        pass

class OwnWorkRule(ClassificationRule):
    name = "Direct Author Match"

    def evaluate(self, item: CopyrightItem) -> Optional[str]:
        # Logic: Check if Author string matches any Course Teacher
        if not item.author: return None

        # We need efficient lookup here (optimize via heuristics later)
        course_ids = item.courses.values_list('pk', flat=True)
        # Pseudocode for check
        is_author_in_course = Person.objects.filter(
            courses__in=course_ids,
            input_name__iexact=item.author # Strict match for Hard Rule
        ).exists()

        return ClassificationV2.JA_EIGEN_WERK if is_author_in_course else None

class OpenAccessPublisherRule(ClassificationRule):
    name = "Allowlisted Publisher"

    ALLOWLIST = ["BioMed Central", "Springer Open", "PLoS"]

    def evaluate(self, item: CopyrightItem) -> Optional[str]:
        if item.publisher in self.ALLOWLIST:
            return ClassificationV2.JA_OPEN_LICENTIE
        return None

# Registry of active rules
ACTIVE_RULES = [OwnWorkRule(), OpenAccessPublisherRule()]
```

### 3.2 Phase 2: Feature Engineering (Gate 2)

**File:** `src/apps/classification/pipeline/features.py`

CatBoost works best when given a flat list of inputs. This module flattens the Relational DB + Document Text into a simple Dict/DataFrame.

```python
import Levenshtein  # pypi: Levenshtein
from apps.core.models import CopyrightItem

def calculate_heuristic_scores(item: CopyrightItem) -> dict:
    """Calculates fuzzy matching scores and weak signals."""
    best_match_score = 0.0

    if item.author:
        teachers = item.teachers.all() # Optimization: use select_related in query
        for t in teachers:
            # Fuzzy match author vs teacher name
            score = Levenshtein.ratio(item.author.lower(), t.main_name.lower())
            best_match_score = max(best_match_score, score)

    return {
        "author_teacher_fuzzy_score": best_match_score,
        "filename_has_ppt": "ppt" in (item.filename or "").lower(),
    }

def extract_features(item: CopyrightItem) -> dict:
    """Combines metadata, text, and heuristics."""
    heuristics = calculate_heuristic_scores(item)

    # Combine everything for CatBoost
    return {
        # -- Categorical Features --
        "filetype": item.filetype,
        "faculty_abbrev": item.faculty.abbreviation if item.faculty else "UNKNOWN",
        "has_publisher": bool(item.publisher),

        # -- Numerical Features --
        "page_count": item.page_count,
        "word_count": item.word_count,
        "file_size": item.document.file_size_bytes if hasattr(item, 'document') else 0,
        "author_fuzzy_score": heuristics['author_teacher_fuzzy_score'],

        # -- Text Features (CatBoost creates embeddings internally) --
        "clean_title": item.title or "",
        "clean_author": item.author or "",
        # Critical: The actual content (truncated)
        "content_snippet": (item.document.extracted_text[:1000]
                          if hasattr(item, 'document') and item.document.extracted_text
                          else "")
    }
```

### 3.3 Phase 3: Machine Learning Core (Gate 3)

**File:** `src/apps/classification/ml/training.py`

This handles the "Nightly Training". It fetches valid human-labeled data and updates the model file.

```python
import polars as pl
from catboost import CatBoostClassifier
from apps.core.models import CopyrightItem, ClassificationV2
from .features import extract_features

MODEL_PATH = "/app/models/catboost_v1.cbm"

def train_model():
    # 1. Fetch Verified Data (Ground Truth)
    # Exclude: TODO, UNKNOWN status, and items handled by Hard Rules (optional decision)
    qs = CopyrightItem.objects.exclude(
        v2_manual_classification=ClassificationV2.ONBEKEND
    ).exclude(
        v2_manual_classification__isnull=True
    ).prefetch_related('faculty', 'document')

    if not qs.exists():
        print("No training data available.")
        return

    # 2. Build Dataset
    data = []
    labels = []
    for item in qs:
        feats = extract_features(item)
        data.append(feats)
        labels.append(item.v2_manual_classification)

    # Convert to Polars for inspection (optional) or directly to list
    # CatBoost works well with Polars dataframes
    df_X = pl.from_dicts(data)
    df_y = labels

    # 3. Train CatBoost
    model = CatBoostClassifier(
        iterations=500,
        depth=6,
        learning_rate=0.1,
        loss_function='MultiClass',
        verbose=100,
        # Define which columns are text/categorical
        cat_features=["filetype", "faculty_abbrev", "has_publisher"],
        text_features=["clean_title", "content_snippet", "clean_author"]
    )

    model.fit(df_X.to_pandas(), df_y) # CatBoost supports Pandas natively

    # 4. Save
    model.save_model(MODEL_PATH)
    return f"Model trained on {len(data)} items. Saved to {MODEL_PATH}"
```

**File:** `src/apps/classification/ml/inference.py`

```python
from catboost import CatBoostClassifier
import pandas as pd
from .training import MODEL_PATH

_loaded_model = None

def get_model():
    """Singleton pattern to keep model in memory."""
    global _loaded_model
    if _loaded_model is None:
        try:
            _loaded_model = CatBoostClassifier()
            _loaded_model.load_model(MODEL_PATH)
        except Exception:
            return None # Handle cold start case (no model trained yet)
    return _loaded_model

def predict_single_item(features_dict: dict):
    model = get_model()
    if not model:
        return None, 0.0

    # Create single-row DataFrame
    df = pd.DataFrame([features_dict])

    # Predict
    label = model.predict(df)[0][0] # [[label]] structure
    probs = model.predict_proba(df)[0]

    # Get confidence of the chosen label
    classes = model.classes_
    class_index = list(classes).index(label)
    confidence = probs[class_index]

    return label, confidence
```

---

## 4. Workflows & Trigger Points

This describes exactly how this system interacts with `core` and `ingest`.

**File:** `src/apps/classification/services.py`

This is the interface exposed to the rest of the application.

```python
from django.utils import timezone
from .pipeline.rules import ACTIVE_RULES
from .pipeline.features import extract_features
from .ml.inference import predict_single_item
from apps.core.models import CopyrightItem, WorkflowStatus

def run_classification_pipeline(item: CopyrightItem):
    """
    Main orchestration function.
    Can be called by celery tasks, signals, or ingest pipeline.
    """

    # 1. Gate 1: Hard Rules
    for rule in ACTIVE_RULES:
        result = rule.evaluate(item)
        if result:
            # Deterministic Match!
            item.auto_classified_by_rule = rule.name
            item.v2_predicted_classification = result
            item.v2_prediction_confidence = 1.0

            # Optional: If rule is strictly trusted, you could set
            # manual_classification = result and auto-archive it.
            # For now, we leave it as a perfect suggestion.

            item.save()
            return

    # 2. Gate 2: Extract Features
    features = extract_features(item)

    # 3. Gate 3: ML Prediction
    label, confidence = predict_single_item(features)

    if label:
        item.v2_predicted_classification = label
        item.v2_prediction_confidence = confidence
        item.auto_classified_by_rule = None # Clear old rules if they fail now
        item.save()

```

### Triggering the Pipeline

We hook into **Tasks**.

1.  **On Ingest:** After `ingest_excel_task` creates items, chain a call to `run_classification_pipeline` for each item.
2.  **On PDF Process:** When `pdf_extraction_task` (in `apps.documents`) finishes and writes `extracted_text` to the DB, it must trigger the pipeline again to improve prediction (since we now have text content).

```python
# In src/apps/documents/tasks.py (Existing file)
@task
def pdf_extraction_task(item_id):
    # ... logic to extract PDF text ...
    document.extracted_text = text_content
    document.save()

    # NEW: Retrigger classification now that we have text
    from apps.classification.services import run_classification_pipeline
    item = CopyrightItem.objects.get(pk=item_id)
    run_classification_pipeline(item)
```

---

## 5. Development Roadmap (Checklist)

1.  **Dependency Setup:**
    *   Add `catboost`, `levenshtein`, `scikit-learn` to `pyproject.toml`.
    *   Rebuild Docker image (CatBoost has binary dependencies).
2.  **Rule Implementation:**
    *   Port known business logic (Author match, Publisher lists) into `rules.py`.
    *   Unit test these rules rigorously with mock items.
3.  **Data Harvesting:**
    *   Manually classify ~100 items of various types in the UI (to create a training seed).
4.  **Initial Training:**
    *   Run `python manage.py train_model` (create this management command based on section 3.3).
5.  **Dashboard Integration:**
    *   Update `dashboard/_grid_row.html`:
        *   If `confidence > 0.9` -> Show Prediction in Green.
        *   If `confidence < 0.6` -> Highlight Row as "Hard/Uncertain".
6.  **Verify Loop:**
    *   As users work, the DB fills with verified data.
    *   Schedule `train_model` to run weekly via cron/beat.

---

Here is the implementation plan for the **Interactive Classification Widget**.

This component bridges the gap between heavy database logic (Django) and the need for a responsive, interactive verification tool. It utilizes **AnyWidget** to embed a full-stack application (Python backend + React frontend) directly into Jupyter or Marimo notebooks.


# Interactive Classification Widget - Implementation Plan
**Date:** December 13, 2025
**Dependencies:** Requires `copyright-platform` (Core) and `apps.classification` (The Model logic).

## 1. Overview & Strategy

The widget replaces standard Django Forms/Admin with a "Data Science Native" interface. It bypasses the need for a running HTTP Web Server.

*   **Runtime:** Marimo Notebook (running inside the Docker container).
*   **Backend:** Direct Django ORM calls from the Notebook kernel.
*   **Frontend:** React 19 + TanStack Table + Tailwind CSS (via AnyWidget).
*   **Workflow:**
    1.  User opens notebook: `marimo edit notebooks/labeler.py`.
    2.  Widget loads the **Top 50** items requiring attention (lowest confidence predictions).
    3.  User clicks an item → Split screen (PDF + Actions).
    4.  User clicks "Approve/Classify" → Writes to DB → Loads next item.

---

## 2. Directory Structure

Create this module inside the classification app.

```text
src/apps/classification/widget/
├── __init__.py           # Exports the Python class
├── backend.py            # Django Interface (ORM Logic)
├── bundle.js             # Compiled JS (Generated, .gitignore this)
├── widget.css            # Styles
├── js/                   # Source Frontend
│   ├── index.jsx         # Entry point
│   ├── components/
│   │   ├── Grid.jsx      # The List View
│   │   ├── Detail.jsx    # The PDF/Action View
│   │   └── Badge.jsx     # Visual indicator for confidence
│   └── styles.css
└── package.json          # JS Dependencies (React, TanStack)
```

---

## 3. The Backend (Python)

**File:** `src/apps/classification/widget/backend.py`

This code initializes Django in the notebook context and handles the data synchronization.

```python
import anywidget
import traitlets
import django
import os
import base64
from pathlib import Path

# 1. Boot Django (Critical for Notebook context)
# This assumes the script runs inside the container with environment vars set.
if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true" # Allow ORM in Jupyter
    django.setup()

from apps.core.models import CopyrightItem, ClassificationV2, WorkflowStatus

class CopyrightLabeler(anywidget.AnyWidget):
    # Standard boilerplate to link JS
    _esm = Path(__file__).parent / "bundle.js"
    _css = Path(__file__).parent / "widget.css"

    # 2. State Syncing (Python <-> JS)
    # The queue of items (Summary only)
    queue = traitlets.List([]).tag(sync=True)
    # The active view: "grid" or "detail"
    view_mode = traitlets.Unicode("grid").tag(sync=True)
    # Active Item Details
    active_item = traitlets.Dict({}).tag(sync=True)
    # PDF Binary Data (Base64)
    active_pdf_data = traitlets.Unicode("").tag(sync=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.refresh_queue()
        self.on_msg(self._handle_msg)

    def refresh_queue(self):
        """
        Loads the 'Work Queue': The 50 items with the lowest classification
        confidence that are still TODO.
        """
        qs = CopyrightItem.objects.filter(
            workflow_status=WorkflowStatus.TODO
        ).order_by('v2_prediction_confidence')[:50]

        data = []
        for item in qs:
            data.append({
                "id": item.material_id,
                "title": item.title,
                "author": item.author,
                "confidence": item.v2_prediction_confidence,
                "prediction": item.v2_predicted_classification
            })
        self.queue = data

    def _handle_msg(self, widget, content, buffers):
        """Dispatch actions from React"""
        action = content.get("type")
        payload = content.get("payload")

        if action == "LOAD_DETAIL":
            self._load_item_detail(payload["id"])

        elif action == "SAVE_DECISION":
            self._save_decision(payload)
            # Return to grid after save
            self.view_mode = "grid"
            self.refresh_queue()

    def _load_item_detail(self, item_id):
        try:
            item = CopyrightItem.objects.get(pk=item_id)

            # 1. Send Metadata
            self.active_item = {
                "id": item.material_id,
                "title": item.title,
                "author": item.author,
                "page_count": item.page_count,
                "prediction": item.v2_predicted_classification,
                "confidence": item.v2_prediction_confidence,
                "faculty": str(item.faculty)
            }

            # 2. Load PDF from Disk (Volume)
            pdf_path = f"/app/documents/downloads/{item.filename}"
            # Check exist and load
            if item.filename and os.path.exists(pdf_path):
                with Path.open(pdf_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode('utf-8')
                    self.active_pdf_data = f"data:application/pdf;base64,{b64}"
            else:
                self.active_pdf_data = "" # Frontend handles "File Missing"

            self.view_mode = "detail"

        except CopyrightItem.DoesNotExist:
            pass

    def _save_decision(self, payload):
        item_id = payload["id"]
        decision = payload["label"]

        item = CopyrightItem.objects.get(pk=item_id)
        item.v2_manual_classification = decision
        item.workflow_status = WorkflowStatus.DONE
        item.save()
```

---

## 4. The Frontend (React/JS)

**Setup:**
You will need to install the dependencies in `src/apps/classification/widget/package.json`.
```json
{
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "@tanstack/react-table": "^8.0.0",
    "clsx": "^2.0.0",
    "tailwind-merge": "^2.0.0"
  },
  "devDependencies": {
    "esbuild": "^0.19.0"
  }
}
```

**File:** `src/apps/classification/widget/js/index.jsx`
The Entry Point utilizing AnyWidget's React bridge.

```javascript
import React, { useState, useEffect } from "react";
import { createRender, useModelState } from "@anywidget/react";
import GridView from "./components/Grid";
import DetailView from "./components/Detail";

// Simple Tailwind injection for the notebook environment
import "./styles.css";

function WidgetApp({ model }) {
  const [viewMode] = useModelState(model, "view_mode");

  return (
    <div className="h-[600px] w-full bg-base-100 border border-base-300 rounded-lg flex flex-col overflow-hidden font-sans">
      <div className="bg-primary text-primary-content p-3 font-bold flex justify-between">
         <span>Copyright Classification Assistant</span>
         <span className="text-xs opacity-70">Model: Active Learning Mode</span>
      </div>

      {viewMode === "grid" ? (
        <GridView model={model} />
      ) : (
        <DetailView model={model} />
      )}
    </div>
  );
}

export default {
  render: createRender(WidgetApp),
};
```

**File:** `src/apps/classification/widget/js/components/Grid.jsx` (Concept)

```javascript
import { useModelState } from "@anywidget/react";

export default function GridView({ model }) {
  const [queue] = useModelState(model, "queue");

  return (
    <div className="overflow-auto p-4">
      <table className="table table-sm table-pin-rows">
        <thead>
          <tr>
            <th>Prediction (Conf)</th>
            <th>Title</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {queue.map((row) => (
            <tr key={row.id} className="hover">
              <td>
                <div className="flex flex-col">
                  <span className="font-bold">{row.prediction}</span>
                  <progress
                    className={`progress w-20 ${row.confidence < 0.6 ? 'progress-error' : 'progress-success'}`}
                    value={row.confidence * 100}
                    max="100">
                  </progress>
                </div>
              </td>
              <td className="truncate max-w-md">{row.title}</td>
              <td>
                <button
                  className="btn btn-sm btn-outline"
                  onClick={() => model.send({ type: "LOAD_DETAIL", payload: { id: row.id } })}
                >
                  Inspect
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

**File:** `src/apps/classification/widget/js/components/Detail.jsx` (Concept)

```javascript
import { useModelState } from "@anywidget/react";

export default function DetailView({ model }) {
  const [item] = useModelState(model, "active_item");
  const [pdfData] = useModelState(model, "active_pdf_data");

  const save = (label) => {
    model.send({ type: "SAVE_DECISION", payload: { id: item.id, label } });
  };

  return (
    <div className="flex flex-1 h-full">
      {/* PDF Viewer (Left) */}
      <div className="w-7/12 bg-base-200 p-2 h-full">
        {pdfData ? (
            <object
              data={pdfData}
              type="application/pdf"
              className="w-full h-full rounded shadow"
            >
              <p>PDF cannot be displayed.</p>
            </object>
        ) : (
            <div className="grid place-items-center h-full">PDF Not Found</div>
        )}
      </div>

      {/* Controls (Right) */}
      <div className="w-5/12 p-6 flex flex-col gap-4 overflow-y-auto">
         <div>
            <h2 className="text-xl font-bold">{item.title}</h2>
            <p className="text-sm opacity-70">Author: {item.author} | Pages: {item.page_count}</p>
         </div>

         <div className="alert alert-info shadow-sm">
            <span>
              <strong>AI Suggestion:</strong> {item.prediction}
              <br/>
              (Confidence: {(item.confidence * 100).toFixed(1)}%)
            </span>
         </div>

         <div className="divider">Actions</div>

         <div className="flex flex-col gap-2">
            <button className="btn btn-success" onClick={() => save('Ja (eigen werk)')}>
              Confirm: Eigen Werk
            </button>
            <button className="btn btn-info" onClick={() => save('Ja (open licentie)')}>
              Confirm: Open Licentie
            </button>
            <div className="divider"></div>
            <button className="btn btn-error btn-outline" onClick={() => save('Nee')}>
              Mark: Overname / Needs Payment
            </button>
         </div>

         <button
           className="btn btn-ghost mt-auto"
           onClick={() => model.set("view_mode", "grid") && model.save_changes()}
         >
           Cancel / Back
         </button>
      </div>
    </div>
  );
}
```

---

## 5. Development & Running

### 5.1 Compilation
Before running the Python widget, the JS must be bundled. We create a script in `docker-compose` or `entrypoint` (dev only).

```bash
# In the container:
cd src/apps/classification/widget
npm install
npm run build
# (Where build command is: "esbuild js/index.jsx --bundle --outdir=.")
```

### 5.2 How to Run (The UX)

1.  **Launch Marimo:**
    User opens the browser to the Marimo interface (e.g., `localhost:8080`).

2.  **Create Notebook:**
    Create a new file `classification_workbench.py`.

3.  **Code Cell:**
    ```python
    import marimo as mo
    from apps.classification.widget.backend import CopyrightLabeler

    # Instantiate
    widget = CopyrightLabeler()

    # Display
    widget
    ```

4.  **Result:**
    The output cell instantly renders the React application. The user sees the table of Todo items. They can classify continuously without leaving the notebook or waiting for server reloads.

### 5.3 Advanced Notebook Interaction
Since this is python, the user can also **export** data immediately:

```python
# New Cell
# Check how many are done
count = CopyrightItem.objects.filter(workflow_status="Done").count()
mo.md(f"**Progress:** {count} items completed!")
```

This mix of interactive widget UI and programmatic access via Django ORM offers the most flexible workflow for data management.
---

Below is a combined **Master Development Guide** for the Easy Access Platform. It integrates the architectural decisions, specific data models from legacy code, and implementation steps for the intelligence and widget layers.

# Easy Access Platform additions - Master Development Guide
**Date:** December 14, 2025
**Target Stack:** Django 6.0, Python 3.12+, PostgreSQL 17, Polars, Docker, CatBoost.
**Status:** Implementation Ready

## 📋 Executive Summary
We are refactoring the `ea-cli` tool (Tortoise ORM/Pandas) into a robust **Django 6.0** platform.
*   **Legacy Code:** The original `ea-cli` is included as a submodule for direct field/logic reference.
*   **Database Strategy:** We are replicating the V1 schema strictness (fields, types) but porting relations to Django's ORM standards.
*   **Migration:** Data will be exported from V1 to CSV/JSON, then ingested via Polars into the V2 `StagedItem` table.

---

## 🛠 Phase 1: Infrastructure & Project Structure

### 1.1 File Structure
Initialize the repository. **Action:** Run `git submodule add <ea-cli-repo-url> ea-cli` to mount the legacy code.

```text
copyright-platform/
├── .devcontainer/devcontainer.json
├── ea-cli/                              # [SUBMODULE] Reference Code
├── docker/
│   ├── Dockerfile
│   ├── entrypoint.sh
├── documents/                           # [VOLUME] Mapped to local storage (NAS/Disk)
├── raw_data/                            # [VOLUME] Watch folder for Excel
├── src/
│   ├── apps/
│   │   ├── api/
│   │   ├── classification/              # Rule Engine & ML
│   │   │   ├── widget/                  # AnyWidget (Notebook)
│   │   │   └── pipeline/                # Heuristics
│   │   ├── core/                        # Organization, Person, Users
│   │   ├── dashboard/                   # HTMX Views
│   │   ├── documents/                   # PDF & Canvas Metadata models
│   │   ├── enrichment/                  # External APIs
│   │   └── ingest/                      # Polars Tasks
│   ├── config/
│   └── manage.py
├── .env.example
├── docker-compose.yml
└── pyproject.toml
```

### 1.2 Configuration
**`pyproject.toml`** (Combined Dependencies)
```toml
[project]
name = "copyright-platform"
version = "2.0.0"
requires-python = ">=3.12"
dependencies = [
    "django>=6.0",
    "django-shinobi",
    "django-htmx",
    "django-environ",
    "django-redis-tasks",
    "psycopg[binary]",
    "redis",
    "polars[xlsx,pyarrow]",
    "catboost",
    "scikit-learn",
    "watchfiles",
    "anywidget",
    "pypdf",
    "Levenshtein",
    "loguru"
]
```

---

## 💾 Phase 2: Core Data Modeling
**Objective:** Port the exact schema from `ea-cli/easy_access/db/models.py`.

### 2.1 Enums (`apps.core.choices`)
Map `ea-cli/easy_access/db/enums.py` to Django `TextChoices`.

```python
# src/apps/core/choices.py
from django.db import models

class ClassificationV2(models.TextChoices):
    # Match strings exactly from legacy enums.py
    JA_OPEN_LICENTIE = "Ja (open licentie)", "Ja (Open Licentie)"
    JA_EIGEN_WERK = "Ja (eigen werk)", "Ja (Eigen Werk)"
    JA_EASY_ACCESS = "Ja (easy access)", "Ja (Easy Access)"
    JA_ANDERS = "Ja (anders)", "Ja (anders)"
    NEE_LINK = "Nee (Link beschikbaar)", "Nee (Link beschikbaar)"
    NEE = "Nee", "Nee"
    ONBEKEND = "Onbekend", "Onbekend"
    # ... include all TIJDELIJK variants ...

class WorkflowStatus(models.TextChoices):
    TODO = "ToDo", "ToDo"
    DONE = "Done", "Done"
    IN_PROGRESS = "InProgress", "In Progress"

class Filetype(models.TextChoices):
    PDF = "pdf", "PDF"
    PPT = "ppt", "PowerPoint"
    DOC = "doc", "Word"
    UNKNOWN = "unknown", "Unknown"
    # ... map remaining from Legacy Filetype ...
```

### 2.2 Domain Models (`apps.core.models`)
Refactor `Organization`, `Faculty`, `Person`.

```python
from django.db import models
from .choices import *

class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class Organization(TimestampedModel):
    """
    Consolidates Legacy 'Organization' and 'Faculty' and 'Programme'
    Legacy: Organization (db table 'organization_data')
    """
    class Type(models.TextChoices):
        UNI = "UNI", "University"
        FACULTY = "FAC", "Faculty"
        DEPT = "DEP", "Department"
        PROG = "PROG", "Programme"

    name = models.CharField(max_length=2048, db_index=True)
    abbreviation = models.CharField(max_length=255, db_index=True)
    full_abbreviation = models.CharField(max_length=2048, unique=True, null=True)
    org_type = models.CharField(choices=Type.choices, default=Type.FACULTY)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = ('name', 'abbreviation')

class Person(TimestampedModel):
    # Match legacy table 'person_data'
    input_name = models.CharField(max_length=2048, unique=True, db_index=True)
    main_name = models.CharField(max_length=2048, null=True, blank=True)
    first_name = models.CharField(max_length=2048, null=True, blank=True)
    email = models.CharField(max_length=2048, null=True, blank=True)
    people_page_url = models.URLField(max_length=2048, null=True, blank=True)
    match_confidence = models.FloatField(null=True)

    orgs = models.ManyToManyField(Organization, related_name='employees')
```

### 2.3 Copyright Models (`apps.core.models`)
The core `CopyrightItem` must contain every field from `v1` and `v2`.

```python
class CopyrightItem(TimestampedModel):
    # Primary Key
    material_id = models.BigIntegerField(primary_key=True)

    # Identifiers & Status
    filename = models.CharField(max_length=2048, null=True, blank=True)
    filehash = models.CharField(max_length=255, db_index=True, null=True)
    url = models.URLField(max_length=2048, null=True, unique=True) # Check Legacy uniqueness
    workflow_status = models.CharField(choices=WorkflowStatus.choices, default=WorkflowStatus.TODO, db_index=True)

    # Classification Fields
    v2_manual_classification = models.CharField(choices=ClassificationV2.choices, default=ClassificationV2.ONBEKEND)
    # Legacy field retention
    manual_classification = models.CharField(max_length=2048, null=True, blank=True)

    # Metadata (From legacy)
    title = models.CharField(max_length=2048, null=True)
    author = models.CharField(max_length=2048, null=True)
    publisher = models.CharField(max_length=2048, null=True)
    isbn = models.CharField(max_length=255, null=True)
    doi = models.CharField(max_length=255, null=True)

    # Statistics (Legacy: pagecount, pages_x_students, etc)
    pagecount = models.IntegerField(default=0)
    wordcount = models.IntegerField(default=0)
    count_students_registered = models.IntegerField(default=0)

    # Relations
    faculty = models.ForeignKey(Organization, null=True, on_delete=models.SET_NULL)
    courses = models.ManyToManyField('Course', related_name='items')

    # Workflow Extras (Legacy: last_canvas_check, file_exists)
    file_exists = models.BooleanField(null=True, default=None)
    last_canvas_check = models.DateTimeField(null=True)
    canvas_course_id = models.BigIntegerField(null=True, db_index=True)

    # ML V2 Fields (New)
    v2_predicted_classification = models.CharField(choices=ClassificationV2.choices, null=True)
    v2_prediction_confidence = models.FloatField(default=0.0)

    class Meta:
        indexes = [
            models.Index(fields=['workflow_status']),
            models.Index(fields=['filehash']),
        ]
```

### 2.4 Document Models (`apps.documents.models`)
We must port `PDFCanvasMetadata` faithfully, as it determines lock/unlock logic.

```python
class PDF(TimestampedModel):
    # Links to Copyright Item
    item = models.OneToOneField('core.CopyrightItem', related_name='pdf', on_delete=models.CASCADE)

    filename = models.CharField(max_length=2048, null=True)
    current_file_name = models.CharField(max_length=2048) # Disk location

    # Extraction status
    extraction_successful = models.BooleanField(default=False)
    extracted_text_content = models.TextField(null=True) # Flattening PDFText relation for simplicity

    def get_absolute_path(self):
        return f"/app/documents/downloads/{self.current_file_name}"

class PDFCanvasMetadata(TimestampedModel):
    pdf = models.OneToOneField(PDF, related_name='canvas_meta', on_delete=models.CASCADE)
    uuid = models.CharField(max_length=255)
    size = models.BigIntegerField()
    locked = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)
    unlock_at = models.DateTimeField(null=True)
```

---

## ⚡ Phase 3: Data Ingestion Pipeline

### 3.1 Task (`apps.ingest.tasks`)
We use Polars to read raw Excel. Reference `ea-cli/easy_access/sheets/sheet.py` to see how columns were renamed in the legacy system.

```python
from django.tasks import task
from apps.core.models import StagedItem

@task
def ingest_task(file_path):
    import polars as pl
    # Read
    df = pl.read_excel(file_path)
    # Convert dates/ints (Polars is strict, check types)
    # Bulk insert
    dicts = df.to_dicts()
    StagedItem.objects.bulk_create(
        [StagedItem(source_file=file_path, payload=d) for d in dicts]
    )
    # Trigger Enrichment
```

### 3.2 Legacy Migration
1.  **Export V1:** Use legacy codebase to dump `copyright_data` table to `migration_dump.csv`.
2.  **Import V2:** The Watchdog picks up the file.
3.  **Migration Script:** Write a Django Command that reads `StagedItem`, validates against `CopyrightItem` fields (mapping `classification` -> `v1_manual_classification`), and inserts.

---

## 🖥️ Phase 4: HTMX Dashboard
**Reference:** `ea-cli/dashboard/dash.py` (Visuals) and `data.py` (Filtering).

### 4.1 Filter Implementation (`apps.dashboard.views`)
Reimplement filters for `Faculty`, `Status` (Workflow), and `Year` (Period).

```python
def grid_partial(request):
    items = CopyrightItem.objects.select_related('pdf').all()

    # Status Filter
    if status := request.GET.get('status'):
        items = items.filter(workflow_status=status)

    # Full Text Search (Postgres)
    if q := request.GET.get('q'):
        items = items.filter(title__icontains=q)

    return render(request, "_grid.html", {"items": items[:100]})
```

---

## 🧠 Phase 5: Intelligence & Automation
**Goal:** Automate V2 Classification.

### 5.1 Hard Rules (`apps.classification.pipeline.rules`)
Reference `ea-cli/easy_access/merge_rules.py`. Convert hardcoded logic into Policy Classes.

```python
class OwnWorkRule:
    """Checks fuzzy match between Author and Course Teacher"""
    def check(self, item):
        # Implementation of Levenshtein logic from ea-cli/easy_access/utils.py
        pass
```

### 5.2 CatBoost Integration (`apps.classification.ml`)
Create the training/inference loop using the fields identified in the Models phase (e.g., `pagecount`, `filetype`).

---

## 🔬 Phase 6: The "AnyWidget" Notebook Tool
**Goal:** Advanced verification tool replacing the legacy "Dashboard Edit Mode".

### 6.1 Logic (`apps.classification.widget.backend`)
Use `anywidget` to provide a split-pane view in Marimo/Jupyter.
**Feature:** Ensure the widget can update `workflow_status` from 'ToDo' to 'Done'.

### 6.2 Visualization
In the legacy tool, PDFs were served via static files. In the widget, use `active_pdf_data = traitlets.Unicode()` to stream base64 content so it works in remote notebooks (Hubs/Docker).

---

## ✅ Implementation Checklist

1.  **Repo Setup:** Git Submodule for `ea-cli`. Docker compose up.
2.  **Schema Check:** Compare `src/apps/core/models.py` line-by-line with `ea-cli/easy_access/db/models.py`.
3.  **Migrate:** `manage.py makemigrations` -> `manage.py migrate`.
4.  **Ingest Test:** Drop a sample excel file. Verify `StagedItem` has JSON data.
5.  **View Construction:** Build the HTMX grid. Ensure PDF icons link to valid routes.
6.  **Notebook Test:** Launch Marimo (`marimo edit`), import `CopyrightLabeler`, and verify 2-way sync with Database.
