import contextlib
import logging
import os
import warnings
import math
from pathlib import Path
from typing import Any

import polars as pl
from config.university import DEPARTMENT_MAPPING

logger = logging.getLogger(__name__)


def _read_excel_quiet(file_path: str | Path, **kwargs) -> pl.DataFrame:
    """
    Reads an Excel file quietly, suppressing dtype inference messages.
    """
    noisy_loggers = ["polars", "openpyxl", "pyxlsb", "lxml"]
    prev_levels = {}
    for name in noisy_loggers:
        lg = logging.getLogger(name)
        prev_levels[name] = lg.level
        lg.setLevel(logging.ERROR)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with open(os.devnull, "w") as devnull, \
                 contextlib.redirect_stdout(devnull), \
                 contextlib.redirect_stderr(devnull):
                return pl.read_excel(file_path, **kwargs)
    finally:
        for name, level in prev_levels.items():
            logging.getLogger(name).setLevel(level)


def standardize_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    """
    Rename cols to standard format, cast all cols to str,
    replace '-' with None, filter missing material_ids.
    """
    df = (
        df.with_columns(pl.exclude(pl.String).cast(str))
        .rename(
            lambda col: col.replace(" ", "_")
            .replace("#", "count_")
            .replace("*", "x")
            .lower()
        )
        .with_columns(
            pl.when(pl.col(pl.String) != "-").then(pl.col(pl.String)).name.keep()
        )
        .filter(pl.col("material_id").is_not_null())
    )

    if "filetype" in df.columns:
        df = df.filter(
            (pl.col("filetype").is_in(["pdf", "ppt", "doc", "-"]))
            | (pl.col("filetype").is_null())
        )

    # Drop useless cols
    for col in ["type", "google_search_file"]:
        if col in df.columns:
            df = df.drop(col)

    return df


def read_raw_copyright_file(file_path: Path) -> tuple[str, pl.DataFrame]:
    """
    Reads raw copyright export file.
    Returns (file_date_string, standardized_dataframe).
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    logger.info(f"Reading data from: {file_path.name}")
    # Infer date from file creation stat (or name if robust, but stat is safer for now)
    # The legacy code used `file.created`.
    file_date = file_path.stat().st_ctime
    # Format date as YYYY-MM-DD
    # On Windows st_ctime is creation, on Unix it's change. strict correctness: use st_mtime?
    # Legacy used creation.
    from datetime import datetime
    file_date_dt = datetime.fromtimestamp(file_date)
    latest_file_date = file_date_dt.strftime("%Y-%m-%d")

    raw_data = _read_excel_quiet(file_path, sheet_name=None)
    data = standardize_dataframe(raw_data)

    # Add default fields
    columns_to_add = {
        "retrieved_from_copyright_on": [latest_file_date] * len(data),
    }

    if (
        "workflow_status" not in data.columns
        or data["workflow_status"].is_null().all()
        or (data["workflow_status"].str.strip_chars().eq("").all())
    ):
        columns_to_add["workflow_status"] = ["ToDo"] * len(data)

    data = data.with_columns(
        **{k: pl.Series(k, v) for k, v in columns_to_add.items()},
    ).with_columns(
        pl.col("last_change")
        .str.replace(r"^-", "")
        .str.strip_chars()
        .str.strptime(pl.Date, "%Y-%m-%d", strict=False)
        .dt.strftime("%Y-%m-%d"),
        pl.col("classification").str.to_lowercase(),
        faculty=pl.col("department").replace_strict(
            DEPARTMENT_MAPPING, default="Unmapped"
        ),
    )

    return latest_file_date, data


def sanitize_payload(d: Any) -> Any:
    """Recursively replace NaN floats with None for JSON compatibility."""
    if isinstance(d, dict):
        return {k: sanitize_payload(v) for k, v in d.items()}
    if isinstance(d, list):
        return [sanitize_payload(v) for v in d]
    if isinstance(d, float) and math.isnan(d):
        return None
    return d


def read_faculty_sheets(faculties_dir: Path, data_entry_name: str = "Data entry") -> pl.DataFrame:
    """
    Reads all faculty sheets and returns a single DataFrame.
    """
    all_dfs = []
    select_cols = [
        "material_id",
        "workflow_status",
        "remarks",
        "manual_classification",
    ]

    if not faculties_dir.exists():
        logger.warning(f"Faculties directory {faculties_dir} does not exist.")
        return pl.DataFrame()

    # Iterate over faculty directories (first level subdirectories)
    for faculty_dir in [d for d in faculties_dir.iterdir() if d.is_dir()]:
        # Recursively find all xlsx files
        for file in faculty_dir.rglob("*"):
            if file.is_file() and file.suffix.lower() == ".xlsx" and \
               "overview" not in file.name.lower() and \
               "llm" not in file.name.lower():

                try:
                    df = _read_excel_quiet(file, sheet_name=data_entry_name)

                    # Ensure columns exist/cast type
                    for col_name in select_cols:
                        if col_name not in df.columns:
                            df = df.with_columns(
                                pl.lit(None).alias(col_name).cast(pl.String)
                            )
                        else:
                            df = df.with_columns(pl.col(col_name).cast(pl.String))

                    df = df.select(select_cols)
                    all_dfs.append(df)
                except Exception as e:
                    logger.warning(f"Error reading {file}: {e}")
                    continue

    if not all_dfs:
        return pl.DataFrame()

    return pl.concat(all_dfs)
