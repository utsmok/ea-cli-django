"""
File operation utilities with retry logic for Windows file locking.

Windows can fail with PermissionError when files are open in other programs
(like Excel). This module provides retry logic for common file operations.
"""

import functools
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path

from loguru import logger


class FileOperationError(Exception):
    """Base exception for file operation errors."""

    pass


class RetriesExhaustedError(FileOperationError):
    """Raised when all retry attempts are exhausted."""

    pass


def retry_on_permission_error(
    func: Callable | None = None,
    *,
    max_retries: int = 5,
    base_delay: float = 0.5,
    backoff_factor: float = 2.0,
    error_types: tuple = (PermissionError, OSError),
) -> Callable:
    """
    Decorator to retry file operations on Windows permission errors.

    On Windows, file operations can fail with PermissionError if:
    - A file is open in another program (Excel, Explorer, etc.)
    - Antivirus is scanning the file
    - The file system is temporarily locked

    Can be used with or without arguments:
        @retry_on_permission_error()
        def save_workbook(workbook, path):
            workbook.save(path)

        @retry_on_permission_error(max_retries=3)
        def rename_file(src, dst):
            os.rename(src, dst)

    Args:
        func: The function to retry (when used without arguments)
        max_retries: Maximum number of retry attempts (default: 5)
        base_delay: Initial delay in seconds (default: 0.5)
        backoff_factor: Multiplier for delay after each retry (default: 2.0)
        error_types: Tuple of exception types to catch (default: PermissionError, OSError)

    Returns:
        Wrapped function with retry logic
    """

    def decorator(f: Callable) -> Callable:
        """Inner decorator that wraps the function."""

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            last_error = None
            delay = base_delay

            for attempt in range(max_retries):
                try:
                    return f(*args, **kwargs)
                except error_types as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"File operation failed (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"File operation failed after {max_retries} attempts: {e}"
                        )

            raise RetriesExhaustedError(
                f"Operation failed after {max_retries} retries"
            ) from last_error

        return wrapper

    # Support both @decorator and @decorator() usage
    if func is None:
        # Called with arguments: @retry_on_permission_error(max_retries=3)
        return decorator
    else:
        # Called without arguments: @retry_on_permission_error
        return decorator(func)


@retry_on_permission_error(max_retries=5)
def rename_with_retry(src: Path, dst: Path) -> None:
    """
    Rename/move a file or directory with retry logic.

    Useful for backup operations where the target directory might be locked.

    Args:
        src: Source path
        dst: Destination path

    Raises:
        RetriesExhaustedError: If all retry attempts fail
    """
    os.rename(src, dst)


@retry_on_permission_error(max_retries=3)
def save_workbook_with_retry(workbook, path: Path | str) -> None:
    """
    Save an openpyxl Workbook with retry logic.

    Useful when Excel might have the file open.

    Args:
        workbook: openpyxl Workbook object
        path: Destination path

    Raises:
        RetriesExhaustedError: If all retry attempts fail
    """
    workbook.save(path)


@retry_on_permission_error(max_retries=3)
def rmtree_with_retry(path: Path) -> None:
    """
    Remove a directory tree with retry logic.

    Args:
        path: Directory path to remove

    Raises:
        RetriesExhaustedError: If all retry attempts fail
    """
    shutil.rmtree(path)


@retry_on_permission_error(max_retries=3)
def atomic_file_write(path: Path, content: bytes) -> None:
    """
    Write to a file atomically using temp file + rename pattern.

    This is the safest pattern for writing files:
    1. Write to a temporary file in the same directory
    2. Rename temp file to target name (atomic on POSIX, near-atomic on Windows)

    Args:
        path: Target file path
        content: Bytes to write

    Raises:
        RetriesExhaustedError: If all retry attempts fail
    """
    # Create temp file in same directory (ensures same filesystem)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")

    # Write to temp file
    temp_path.write_bytes(content)

    # Atomic rename to final location
    temp_path.replace(path)


def check_file_in_use(path: Path) -> bool:
    """
    Check if a file is currently in use (locked) on Windows.

    This is a best-effort check and may not catch all cases.

    Args:
        path: File path to check

    Returns:
        True if file appears to be in use, False otherwise
    """
    if not path.exists():
        return False

    # Try to open the file exclusively
    try:
        # On Windows, opening with exclusive mode will fail if file is in use
        if os.name == "nt":  # Windows
            import msvcrt

            try:
                with path.open("rb") as f:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                return False
            except OSError:
                return True
        else:
            # On Unix, try to rename to same name (will fail if locked)
            temp_name = path.with_suffix(f"{path.suffix}.check")
            try:
                path.rename(temp_name)
                temp_name.rename(path)
                return False
            except OSError:
                return True
    except Exception:
        # If check fails, assume not in use
        return False

    return False
