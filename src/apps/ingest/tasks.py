"""
Async tasks for ingestion pipeline.

Tasks can be triggered by Django views or management commands.
"""

from typing import Any

import polars as pl
from django.tasks import task
from loguru import logger

from .models import FacultyEntry, IngestionBatch, QlikEntry
from .services import (
    BatchProcessor,
    safe_bool,
    safe_float,
    safe_int,
    standardize_dataframe,
    validate_faculty_data,
    validate_qlik_data,
)


@task
def stage_batch(batch_id: int) -> dict[str, Any]:
    """
    Stage a batch: Read Excel file and create staging entries.

    This is the first phase of ingestion: File → Standardized DataFrame → Staging tables

    Args:
        batch_id: ID of the IngestionBatch to process

    Returns:
        Dictionary with staging results
    """
    try:
        # Get batch
        batch = IngestionBatch.objects.get(id=batch_id)
        batch.status = IngestionBatch.Status.STAGING
        batch.save(update_fields=["status"])

        logger.info(f"Staging batch {batch_id} ({batch.source_type})")

        # Read Excel file
        file_path = batch.source_file.path
        if batch.source_type == IngestionBatch.SourceType.FACULTY:
            # Faculty workbooks have two sheets: "Complete data" + "Data entry".
            # We ingest from the Data entry sheet.
            try:
                result = pl.read_excel(file_path, sheet_name="Data entry")
                df = (
                    result if isinstance(result, pl.DataFrame) else result["Data entry"]
                )
            except Exception:
                # Fallback to second sheet by index
                result = pl.read_excel(file_path, sheet_id=1)
                df = (
                    result
                    if isinstance(result, pl.DataFrame)
                    else list(result.values())[1]
                )
        else:
            result = pl.read_excel(
                file_path, sheet_id=0
            )  # Read first sheet (zero-indexed)
        df = result if isinstance(result, pl.DataFrame) else next(iter(result.values()))

        batch.total_rows = len(df)
        batch.save(update_fields=["total_rows"])

        logger.info(f"Read {len(df)} rows from {file_path}")

        # Standardize data
        df = standardize_dataframe(df, batch.source_type)

        logger.info(f"Standardized data: {len(df)} rows remaining after filtering")

        # Validate data
        if batch.source_type == IngestionBatch.SourceType.QLIK:
            is_valid, errors = validate_qlik_data(df)
        else:
            is_valid, errors = validate_faculty_data(df)

        if not is_valid:
            error_msg = "; ".join(errors)
            logger.error(f"Validation failed for batch {batch_id}: {error_msg}")
            batch.status = IngestionBatch.Status.FAILED
            batch.error_message = f"Validation errors: {error_msg}"
            batch.save(update_fields=["status", "error_message"])
            return {"success": False, "errors": errors}

        # Create staging entries
        if batch.source_type == IngestionBatch.SourceType.QLIK:
            rows_staged = _stage_qlik_entries(batch, df)
        else:
            rows_staged = _stage_faculty_entries(batch, df)

        batch.rows_staged = rows_staged
        batch.status = IngestionBatch.Status.STAGED
        batch.save(update_fields=["rows_staged", "status"])

        logger.info(f"Staged {rows_staged} entries for batch {batch_id}")

        return {
            "success": True,
            "batch_id": batch_id,
            "rows_staged": rows_staged,
        }

    except Exception as e:
        logger.error(f"Staging failed for batch {batch_id}: {e}")
        batch = IngestionBatch.objects.get(id=batch_id)
        batch.status = IngestionBatch.Status.FAILED
        batch.error_message = str(e)
        batch.save(update_fields=["status", "error_message"])
        raise


@task
def process_batch(batch_id: int) -> dict[str, Any]:
    """
    Process a batch: Apply staged entries to CopyrightItems.

    This is the second phase of ingestion: Staging tables → CopyrightItem updates

    Args:
        batch_id: ID of the IngestionBatch to process

    Returns:
        Dictionary with processing results
    """
    try:
        # Get batch
        batch = IngestionBatch.objects.get(id=batch_id)

        logger.info(f"Processing batch {batch_id} ({batch.source_type})")

        # Run processor
        processor = BatchProcessor(batch)
        processor.process()

        logger.info(
            f"Batch {batch_id} complete: "
            f"{batch.items_created} created, "
            f"{batch.items_updated} updated, "
            f"{batch.items_skipped} skipped, "
            f"{batch.items_failed} failed"
        )

        # Trigger Phase B Enrichment
        from apps.enrichment.tasks import trigger_batch_enrichment

        trigger_batch_enrichment(batch_id)

        return {
            "success": True,
            "batch_id": batch_id,
            "created": batch.items_created,
            "updated": batch.items_updated,
            "skipped": batch.items_skipped,
            "failed": batch.items_failed,
        }

    except Exception as e:
        logger.error(f"Processing failed for batch {batch_id}: {e}")
        raise


def _stage_qlik_entries(batch: IngestionBatch, df: pl.DataFrame) -> int:
    """Create QlikEntry records from DataFrame."""
    entries = []

    for row in df.iter_rows(named=True):
        entry = QlikEntry(
            batch=batch,
            material_id=int(row["material_id"]),
            row_number=row["row_number"],
            # File metadata
            filename=row.get("filename"),
            filehash=row.get("filehash"),
            filetype=row.get("filetype", "").lower() if row.get("filetype") else None,
            url=row.get("url"),
            status=row.get("status"),
            # Content
            title=row.get("title"),
            author=row.get("author"),
            publisher=row.get("publisher"),
            # Course info
            period=row.get("period"),
            department=row.get("department"),
            course_code=row.get("course_code"),
            course_name=row.get("course_name"),
            canvas_course_id=int(row["canvas_course_id"])
            if row.get("canvas_course_id")
            else None,
            # Identifiers
            isbn=row.get("isbn"),
            doi=row.get("doi"),
            owner=row.get("owner"),
            in_collection=safe_bool(row.get("in_collection")),
            # Metrics
            picturecount=safe_int(row.get("picturecount")) or 0,
            reliability=safe_int(row.get("reliability")) or 0,
            pages_x_students=safe_int(row.get("pages_x_students")) or 0,
            count_students_registered=safe_int(row.get("count_students_registered"))
            or 0,
            pagecount=safe_int(row.get("pagecount")) or 0,
            wordcount=safe_int(row.get("wordcount")) or 0,
            # Infringement
            infringement=row.get("infringement"),
            possible_fine=safe_float(row.get("possible_fine")),
        )
        entries.append(entry)

    # Bulk create
    QlikEntry.objects.bulk_create(entries, batch_size=1000)

    return len(entries)


def _stage_faculty_entries(batch: IngestionBatch, df: pl.DataFrame) -> int:
    """Create FacultyEntry records from DataFrame."""
    entries = []

    for row in df.iter_rows(named=True):
        entry = FacultyEntry(
            batch=batch,
            material_id=int(row["material_id"]),
            row_number=row["row_number"],
            # Human-managed fields
            workflow_status=row.get("workflow_status"),
            classification=row.get("classification"),
            manual_classification=row.get("manual_classification"),
            v2_manual_classification=row.get("v2_manual_classification"),
            v2_overnamestatus=row.get("v2_overnamestatus"),
            v2_lengte=row.get("v2_lengte"),
            remarks=row.get("remarks"),
            scope=row.get("scope"),
            manual_identifier=row.get("manual_identifier"),
        )
        entries.append(entry)

    # Bulk create
    FacultyEntry.objects.bulk_create(entries, batch_size=1000)

    return len(entries)
