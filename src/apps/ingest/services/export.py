"""Excel export service for copyright items.

Phase A requirement:
- Create a folder per faculty
- Within each faculty folder create workflow-bucket workbooks:
  inbox.xlsx / in_progress.xlsx / done.xlsx / overview.xlsx
- Each workbook contains two sheets:
  "Complete data" (full raw export) + "Data entry" (editable fields + dropdowns)
- Create update_overview.csv at the root and update_info_*.txt per faculty

This is a Django-native implementation inspired by the legacy ea-cli exporter.
"""

from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import polars as pl
from django.conf import settings

from apps.core.models import CopyrightItem, Faculty, WorkflowStatus

from .excel_builder import ExcelBuilder

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BucketStats:
    old: int
    new: int

    @property
    def delta(self) -> int:
        return self.new - self.old


class ExportAbortedError(Exception):
    """Custom exception for when an export is aborted, e.g., due to file locks."""

    pass


class ExportService:
    """Exports copyright items into the legacy workflow folder structure."""

    BUCKETS: dict[str, set[str]] = {
        "inbox": {WorkflowStatus.TODO, "todo", "ToDo"},
        "in_progress": {
            WorkflowStatus.IN_PROGRESS,
            "InProgress",
            "in_progress",
            "inprogress",
        },
        "done": {WorkflowStatus.DONE, "Done", "done"},
    }

    def __init__(self, faculty_abbr: Optional[str] = None):
        self.faculty_abbr = faculty_abbr

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def export_workflow_tree(self, output_dir: Optional[Path] = None) -> dict[str, Any]:
        """Create the full faculty_sheets directory tree on disk."""
        output_dir = Path(
            output_dir
            or getattr(
                settings,
                "EXPORT_FACULTY_SHEETS_DIR",
                settings.PROJECT_ROOT / "exports" / "faculty_sheets",
            )
        )

        # New backup strategy: move the entire directory
        self._backup_entire_export_dir(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)


        faculties = self._get_faculty_codes()
        if self.faculty_abbr:
            faculties = [self.faculty_abbr]
        print(f"Exporting faculties: {', '.join(faculties)}")
        builder = ExcelBuilder()
        exported_files: list[Path] = []
        summary_rows: list[tuple[str, str, BucketStats]] = []
        style_iter = 9

        for faculty in faculties:
            faculty_df = self._fetch_faculty_dataframe(faculty)
            print(f"  - {faculty}: {faculty_df.height} items")
            if faculty_df.is_empty():
                logger.info("No items for faculty %s; skipping", faculty)
                continue

            faculty_dir = output_dir / faculty
            faculty_dir.mkdir(parents=True, exist_ok=True)

            buckets = self._bucketize(faculty_df)
            # overview is always all items
            buckets["overview"] = faculty_df

            stats_by_bucket: dict[str, BucketStats] = {}
            for bucket_name, bucket_df in buckets.items():
                if bucket_df.is_empty():
                    print(f"    - {bucket_name}: 0 items; skipping")
                    stats_by_bucket[bucket_name] = BucketStats(old=0, new=0)
                    continue

                target_path = faculty_dir / f"{bucket_name}.xlsx"

                # Since we start with a fresh directory, old_count is always 0
                old_count = 0

                print(
                    f"Now exporting {faculty} -> {bucket_name}: {bucket_df.height} items to {target_path}"
                )
                wb = builder.build_workbook_for_dataframe(
                    bucket_df, style_iter=style_iter
                )
                style_iter += 1
                self._atomic_save_workbook(wb, target_path)

                exported_files.append(target_path)
                stats_by_bucket[bucket_name] = BucketStats(
                    old=old_count, new=bucket_df.height
                )
                summary_rows.append(
                    (faculty, bucket_name, stats_by_bucket[bucket_name])
                )
            print(f"    - Completed export for faculty {faculty}, writing update info.")
            self._write_update_info(faculty_dir, faculty, stats_by_bucket)
        print(
            f"Export completed, writing summary CSV to {output_dir} with {len(summary_rows)} rows."
        )
        self._append_update_overview_csv(output_dir, summary_rows)

        return {
            "output_dir": str(output_dir),
            "files": [str(p) for p in exported_files],
            "faculties": faculties,
        }

    def _backup_entire_export_dir(self, output_dir: Path):
        """Move the entire export directory to a timestamped backup location."""
        if not output_dir.exists() or not any(output_dir.iterdir()):
            logger.info("Export directory is empty or does not exist. No backup needed.")
            return

        backup_root = output_dir.parent / "backups"
        backup_root.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dest = backup_root / f"{output_dir.name}_{ts}"

        try:
            os.rename(output_dir, backup_dest)
            logger.info(f"Successfully backed up '{output_dir}' to '{backup_dest}'")
        except PermissionError as e:
            raise ExportAbortedError(
                "Could not back up the existing export directory. "
                "Please ensure no files inside it are open in another program."
            ) from e

    # ---------------------------------------------------------------------
    # Data retrieval
    # ---------------------------------------------------------------------

    def _get_faculty_codes(self) -> list[str]:
        qs = Faculty.objects.all().values_list("abbreviation", flat=True)
        codes = sorted({c for c in qs if c})
        print(f"Found faculties: {', '.join(codes)}")
        # Include UNM as a fallback bucket if present?
        return codes

    def _fetch_faculty_dataframe(self, faculty: str) -> pl.DataFrame:
        """Fetch all items for a faculty as a Polars DataFrame in legacy column order."""
        from . import export_config

        # 1. Get the list of all columns required for the export
        all_export_cols = export_config.COMPLETE_DATA_COLUMN_ORDER

        # 2. Get the list of actual fields on the CopyrightItem model
        model_fields = {f.name for f in CopyrightItem._meta.get_fields()}

        # 3. Determine which columns can be fetched directly from the DB
        # Note: ml_prediction (legacy) == ml_classification (Django)
        db_cols = [col for col in all_export_cols if col in model_fields and col != "faculty"]
        if "ml_prediction" in all_export_cols and "ml_classification" in model_fields:
            db_cols.append("ml_classification")

        # We also need internal fields for computation
        fetch_cols = list(set(db_cols) | {"canvas_course_id"})

        # 4. Fetch the items from the database with related data
        items = CopyrightItem.objects.filter(faculty__abbreviation=faculty).prefetch_related(
            "courses__courseemployee_set__person__faculty",
            "courses__courseemployee_set__person__orgs",
        )

        values = []
        for item in items:
            # Initialize ALL export columns to None to ensure consistency for Polars
            item_data = {col: None for col in all_export_cols}

            # Fill in fields from fetched data
            for col in fetch_cols:
                val = getattr(item, col, None)
                target_col = col
                if col == "ml_classification":
                    target_col = "ml_prediction"

                # Strip timezone from datetime objects for Excel (openpyxl) compatibility
                if isinstance(val, datetime) and getattr(val, "tzinfo", None) is not None:
                    val = val.replace(tzinfo=None)
                # Legacy Parity: file_exists should be Yes/No
                elif col == "file_exists":
                    val = "Yes" if val else "No"
                # Legacy Parity: in_collection False should be NULL (None)
                elif col == "in_collection" and val is False:
                    val = None
                # Legacy Parity: map 'onbekend' back to None if it was NULL in legacy
                elif col == "manual_classification" and val == "onbekend":
                    val = None

                # We put it in item_data anyway (internal ones will be dropped from DF)
                item_data[target_col] = val

            item_data["faculty"] = item.faculty.abbreviation if item.faculty else None

            # Enrichment data aggregation
            courses = item.courses.all()
            if courses:
                # Legacy Parity: use sorted() for consistency
                # In legacy, order was often non-deterministic but sorted usually matches best.
                item_data["cursuscodes"] = " | ".join(sorted({str(c.cursuscode) for c in courses}))
                item_data["course_names"] = " | ".join(sorted({c.name.replace(",", " | ") for c in courses if c.name}))
                item_data["programmes"] = " | ".join(sorted({c.programme_text.replace(",", " | ") for c in courses if c.programme_text}))

                # Contacts (teachers with role 'contacts')
                contacts = set()
                for course in courses:
                    # Filter from prefetched set
                    for emp in course.courseemployee_set.all():
                        if emp.role == "contacts":
                            contacts.add(emp.person)

                if contacts:
                    # Sort to be deterministic
                    sorted_contacts = sorted(list(contacts), key=lambda p: p.main_name if p.main_name else "")
                    item_data["course_contacts_names"] = " | ".join(sorted({p.main_name for p in sorted_contacts if p.main_name}))
                    item_data["course_contacts_emails"] = " | ".join(sorted({p.email for p in sorted_contacts if p.email}))
                    item_data["course_contacts_faculties"] = " | ".join(sorted({p.faculty.abbreviation for p in sorted_contacts if p.faculty}))

                    orgs = set()
                    for p in contacts:
                        for org in p.orgs.all():
                            if org.full_abbreviation:
                                orgs.add(org.full_abbreviation.replace(",", " | "))
                    item_data["course_contacts_organizations"] = " | ".join(sorted(orgs))

            values.append(item_data)

        if not values:
            return pl.DataFrame()

        df = pl.DataFrame(values, infer_schema_length=None)

        # 5. Dynamically create computed columns like `course_link`
        if "canvas_course_id" in df.columns and "filename" in df.columns:
            base_url = getattr(settings, "CANVAS_BASE_URL", "https://canvas.utwente.nl")
            df = df.with_columns(
                pl.when(pl.col("canvas_course_id").is_not_null())
                .then(
                    pl.concat_str(
                        [
                            pl.lit(f"{base_url}/courses/"),
                            pl.col("canvas_course_id").cast(pl.Utf8),
                            pl.lit("/files/search?search_term="),
                            pl.col("filename").map_elements(lambda x: str(x).replace(" ", "%20") if x else "", return_dtype=pl.Utf8),
                        ],
                        separator="",
                    )
                )
                .otherwise(pl.lit(""))
                .alias("course_link")
            )

        # Drop internal columns not meant for export (like canvas_course_id which we only used for course_link)
        # and re-order to match COMPLETE_DATA_COLUMN_ORDER
        all_export_cols = export_config.COMPLETE_DATA_COLUMN_ORDER
        # Ensure only columns in all_export_cols are kept and in that order
        df = df.select([col for col in all_export_cols if col in df.columns])

        # 6. Ensure all columns from the config exist, adding nulls for any missing ones
        for col in all_export_cols:
            if col not in df.columns:
                df = df.with_columns(pl.lit(None).alias(col))

        # 7. Normalize workflow_status to canonical values
        df = df.with_columns(
            pl.col("workflow_status").fill_null(WorkflowStatus.TODO).cast(pl.Utf8)
        )

        # 8. Return dataframe with columns in the correct, final order
        return df.select(all_export_cols)

    # ---------------------------------------------------------------------
    # Bucketing & file I/O
    # ---------------------------------------------------------------------

    def _bucketize(self, df: pl.DataFrame) -> dict[str, pl.DataFrame]:
        wf = pl.col("workflow_status").fill_null(WorkflowStatus.TODO).cast(pl.Utf8)

        inbox_df = df.filter(
            wf.is_in(["ToDo", "todo", "TODO"])
            | (
                ~wf.is_in(
                    [
                        "ToDo",
                        "InProgress",
                        "Done",
                        "todo",
                        "done",
                        "inprogress",
                        "in_progress",
                    ]
                )
            )
        )
        in_progress_df = df.filter(
            wf.is_in(["InProgress", "inprogress", "in_progress"])
        )
        done_df = df.filter(wf.is_in(["Done", "done"]))

        return {
            "inbox": inbox_df,
            "in_progress": in_progress_df,
            "done": done_df,
        }
    def _atomic_save_workbook(self, wb, target_path: Path):
        """Save a workbook to a temporary file then rename it to target_path."""
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_suffix(".tmp")
        try:
            wb.save(temp_path)
            if target_path.exists():
                target_path.unlink()
            temp_path.rename(target_path)
        except Exception as e:
            print(f"\nERROR SAVING WORKBOOK TO {target_path}: {type(e).__name__}: {e}")
            if temp_path.exists():
                temp_path.unlink()
            raise e

    def _append_update_overview_csv(
        self, output_dir: Path, rows: list[tuple[str, str, BucketStats]]
    ) -> None:
        if not rows:
            return

        summary_file = output_dir / "update_overview.csv"
        mode = "a" if summary_file.exists() else "w"
        with summary_file.open(mode, newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if mode == "w":
                writer.writerow(
                    ["timestamp", "faculty", "bucket", "old", "new", "delta"]
                )

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for faculty, bucket, stats in rows:
                if stats.delta == 0:
                    continue
                writer.writerow(
                    [now, faculty, bucket, stats.old, stats.new, stats.delta]
                )

    def _write_update_info(
        self, faculty_dir: Path, faculty: str, stats_by_bucket: dict[str, BucketStats]
    ) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = faculty_dir / f"update_info_{ts}.txt"

        # Remove previous update_info files (keep only newest info, like the legacy does)
        for p in faculty_dir.glob("update_info_*.txt"):
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass

        def _line(text: str = "") -> str:
            return text + "\n"

        with path.open("w", encoding="utf-8") as fh:
            fh.write(_line("Update information for".center(40)))
            fh.write(_line(faculty.center(40)))
            fh.write(_line(""))
            fh.write(_line("Last sync with main database:".center(40)))
            fh.write(_line(datetime.now().strftime("%Y-%m-%d -- %H:%M:%S").center(40)))
            fh.write(_line(""))

            # Table
            fh.write(_line(("-" * 12 + "-" * 5 + "-" * 5 + "-" * 5).center(40)))
            fh.write(
                _line((f"{'Sheet':<12}|{'Old':^5}|{'New':^5}|{'Δ':^5}").center(40))
            )
            fh.write(
                _line(
                    ("-" * 12 + "+" + "-" * 5 + "+" + "-" * 5 + "+" + "-" * 5).center(
                        40
                    )
                )
            )
            for bucket_name in ["inbox", "in_progress", "done", "overview"]:
                stats = stats_by_bucket.get(bucket_name, BucketStats(old=0, new=0))
                fh.write(
                    _line(
                        (
                            f"{bucket_name:<12}|{stats.old:^5}|{stats.new:^5}|{stats.delta:^+5}"
                        ).center(40)
                    )
                )
            fh.write(_line(("-" * 12 + "-" * 5 + "-" * 5 + "-" * 5).center(40)))
