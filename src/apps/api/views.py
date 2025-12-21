from __future__ import annotations

import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

from apps.ingest.models import IngestionBatch
from apps.ingest.services.export import ExportService
from apps.ingest.tasks import process_batch, stage_batch

User = get_user_model()


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
    if not uploaded:
        return HttpResponseBadRequest("Missing 'file' upload")

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
