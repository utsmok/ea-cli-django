"""
Views for the steps app.

Each processing step has its own view with:
- Input selection interface
- Settings configuration
- Progress monitoring
- Results display

This module re-exports all views from submodules for backwards compatibility.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .enrich import (
    enrich_osiris_status,
    enrich_osiris_step,
    enrich_people_status,
    enrich_people_step,
    run_enrich_osiris,
    run_enrich_people,
)
from .export import (
    download_export_file,
    export_faculty_step,
    run_export_faculty,
)

# Re-export helper functions
from .helpers import _parse_item_ids

# Re-export all views from submodules
from .ingest import (
    ingest_faculty_step,
    ingest_qlik_step,
)
from .pdf import (
    pdf_canvas_status_status,
    pdf_canvas_status_step,
    pdf_extract_status,
    pdf_extract_step,
    run_pdf_canvas_status,
    run_pdf_extract,
)

# Public API - all views that can be imported from this package
__all__ = [
    # Helper functions
    "_parse_item_ids",
    # Main index
    "steps_index",
    # Step 1 & 2: Ingest
    "ingest_qlik_step",
    "ingest_faculty_step",
    # Step 3 & 4: Enrich
    "enrich_osiris_step",
    "run_enrich_osiris",
    "enrich_osiris_status",
    "enrich_people_step",
    "run_enrich_people",
    "enrich_people_status",
    # Step 5 & 6: PDF
    "pdf_canvas_status_step",
    "run_pdf_canvas_status",
    "pdf_canvas_status_status",
    "pdf_extract_step",
    "run_pdf_extract",
    "pdf_extract_status",
    # Step 7: Export
    "export_faculty_step",
    "run_export_faculty",
    "download_export_file",
]


@login_required
@require_GET
def steps_index(request):
    """Main steps dashboard showing all available processing steps."""
    return render(request, "steps/index.html")
