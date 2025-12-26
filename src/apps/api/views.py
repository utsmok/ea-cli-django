from __future__ import annotations

import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import django.db
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from loguru import logger

from apps.ingest.models import IngestionBatch
from apps.ingest.services.export import ExportService
from apps.ingest.tasks import process_batch, stage_batch

User = get_user_model()

# File upload validation constants
MAX_UPLOAD_SIZE_MB = 100
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {".xlsx", ".xls", ".csv"}


def _validate_uploaded_file(uploaded) -> tuple[bool, str | None]:
    """
    Validate uploaded file for size and extension.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not uploaded:
        return False, "Missing 'file' upload"

    # Check file size
    if uploaded.size > MAX_UPLOAD_SIZE_BYTES:
        return False, f"File size exceeds {MAX_UPLOAD_SIZE_MB}MB limit"

    # Check file extension
    filename_lower = uploaded.name.lower() if uploaded.name else ""
    file_ext = Path(filename_lower).suffix
    if file_ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return (
            False,
            f"Invalid file type '{file_ext}'. Allowed: {', '.join(ALLOWED_UPLOAD_EXTENSIONS)}",
        )

    return True, None


def _get_uploaded_by(request: HttpRequest):
    if getattr(request, "user", None) and request.user.is_authenticated:
        return request.user

    user, _ = User.objects.get_or_create(username="system")
    if not user.has_usable_password():
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def _infer_source_type(filename: str, explicit: str | None) -> str:
    explicit_value = explicit or ""
    if explicit_value in {
        IngestionBatch.SourceType.QLIK,
        IngestionBatch.SourceType.FACULTY,
    }:
        return explicit_value

    lower = (filename or "").lower()
    if any(
        k in lower for k in ["inbox", "in_progress", "in-progress", "done", "overview"]
    ):
        return IngestionBatch.SourceType.FACULTY

    return IngestionBatch.SourceType.QLIK


@require_POST
def trigger_ingest(request: HttpRequest):
    uploaded = request.FILES.get("file")

    # Validate file size and extension
    is_valid, error_msg = _validate_uploaded_file(uploaded)
    if not is_valid:
        logger.warning(f"File upload validation failed: {error_msg}")
        return HttpResponseBadRequest(error_msg)

    source_type = _infer_source_type(uploaded.name, request.POST.get("source_type"))
    faculty_code = request.POST.get("faculty_code") or None

    if source_type == IngestionBatch.SourceType.FACULTY and not faculty_code:
        # Best-effort inference from filename prefix like BMS_inbox.xlsx
        prefix = uploaded.name.split("_")[0].upper()
        if 2 <= len(prefix) <= 10:
            faculty_code = prefix

    batch = IngestionBatch.objects.create(
        source_type=source_type,
        uploaded_by=_get_uploaded_by(request),
        faculty_code=faculty_code,
    )
    batch.source_file.save(uploaded.name, uploaded, save=True)

    batch_id = int(batch.pk)

    stage_result = stage_batch(batch_id)
    if not stage_result.get("success"):
        return JsonResponse(
            {"success": False, "batch_id": batch_id, **stage_result}, status=400
        )

    process_result = process_batch(batch_id)
    return JsonResponse({"success": True, "batch_id": batch_id, **process_result})


@require_GET
def download_faculty_sheets(request: HttpRequest):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"faculty_sheets_{ts}"

    with tempfile.TemporaryDirectory(prefix="faculty_sheets_") as tmp:
        export_dir = Path(tmp) / "faculty_sheets"
        ExportService().export_workflow_tree(output_dir=export_dir)

        buf = BytesIO()
        with ZipFile(buf, mode="w", compression=ZIP_DEFLATED) as zf:
            for path in export_dir.rglob("*"):
                if path.is_dir():
                    continue
                zf.write(path, arcname=str(path.relative_to(export_dir)))

        resp = HttpResponse(buf.getvalue(), content_type="application/zip")
        resp["Content-Disposition"] = f'attachment; filename="{zip_name}.zip"'
        return resp


# =============================================================================
# Health Check Endpoints
# =============================================================================


@require_GET
def health_check(request: HttpRequest):
    """
    Basic health check endpoint.

    Returns 200 if the service is running, regardless of backend health.
    This is for load balancers to quickly check if the service is up.

    Returns:
        JSON response with status and basic service info.
    """
    from django.conf import settings

    return JsonResponse(
        {
            "status": "healthy",
            "service": "ea-platform",
            "version": "1.0.0",
            "environment": getattr(settings, "ENV", "development"),
            "debug": getattr(settings, "DEBUG", False),
        }
    )


@require_GET
def readiness_check(request: HttpRequest):
    """
    Readiness check endpoint for Kubernetes/container orchestration.

    Verifies that the service is ready to handle requests by checking:
    - Database connectivity
    - Cache connectivity (Redis)

    Returns 200 if all checks pass, 503 if any critical service is unavailable.
    """
    checks = {"database": "unknown", "cache": "unknown"}
    all_healthy = True

    # Database check
    try:
        with django.db.connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {e!s}"
        all_healthy = False

    # Cache check (optional - service can work without cache)
    try:
        cache.set("health_check", "ok", 10)
        if cache.get("health_check") == "ok":
            checks["cache"] = "healthy"
        else:
            checks["cache"] = "degraded"
    except Exception as e:
        checks["cache"] = f"unhealthy: {e!s}"
        # Cache failure is not critical for readiness
        # but we report it

    status_code = 200 if all_healthy else 503

    return JsonResponse(
        {
            "status": "ready" if all_healthy else "not_ready",
            "checks": checks,
        },
        status=status_code,
    )
