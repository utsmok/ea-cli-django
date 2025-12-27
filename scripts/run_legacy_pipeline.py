#!/usr/bin/env python
"""
Helper script to run the legacy ea-cli pipeline in isolation.

This script:
1. Sets up a temporary legacy environment
2. Configures settings.yaml for test isolation
3. Runs the legacy pipeline
4. Returns the output directory path

Usage:
    python scripts/run_legacy_pipeline.py <input_file.xlsx> <output_dir>
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


def setup_legacy_environment(input_file: Path, output_dir: Path) -> Path:
    """
    Set up isolated legacy environment.

    Creates a temporary directory with:
    - Custom settings.yaml pointing to temp directories
    - Input file in raw_copyright_data/
    - Empty database

    Returns: Path to legacy environment directory
    """
    legacy_env = Path(tempfile.mkdtemp(prefix="legacy_env_"))

    # Create directory structure
    dirs = [
        legacy_env / "raw_copyright_data",
        legacy_env / "faculty_sheets",
        legacy_env / "overviews_backup",
        legacy_env / "script_data",
        legacy_env / "pdf_downloads",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Copy input file
    shutil.copy(input_file, legacy_env / "raw_copyright_data" / input_file.name)

    # Create custom settings.yaml
    settings_path = Path("ea-cli/settings.yaml")
    with open(settings_path) as f:
        settings = yaml.safe_load(f)

    # Override directories for test isolation
    settings["directories"] = {
        "raw_copyright_data": "raw_copyright_data",
        "faculties_dir": str(output_dir),  # Use specified output dir
        "overviews_backup": "overviews_backup",
        "script_data": "script_data",
        "pdf_downloads": "pdf_downloads",
    }

    # Save custom settings
    custom_settings = legacy_env / "settings.yaml"
    with open(custom_settings, "w") as f:
        yaml.dump(settings, f)

    print(f"Legacy environment set up at: {legacy_env}", file=sys.stderr)
    return legacy_env


def run_legacy_pipeline(input_file: Path, output_dir: Path) -> dict:
    """
    Run the legacy pipeline in isolation.

    Args:
        input_file: Path to Qlik export Excel file
        output_dir: Path where faculty sheets should be written

    Returns:
        dict with results:
            - success: bool
            - output_dir: Path
            - database_path: Path
            - duration_seconds: float
            - error: str (if failed)
    """
    import time

    start_time = time.time()

    try:
        # Set up legacy environment
        legacy_env = setup_legacy_environment(input_file, output_dir)

        # Change to legacy directory
        original_dir = os.getcwd()
        os.chdir("ea-cli")

        try:
            # Run legacy pipeline
            # Using subprocess to isolate environment
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "run.py",
                    "process",
                    "--file",
                    f"../{legacy_env}/raw_copyright_data/{input_file.name}",
                ],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes
                env={**os.environ, "SETTINGS_PATH": f"../{legacy_env}/settings.yaml"},
            )

            duration = time.time() - start_time

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": result.stderr or result.stdout,
                    "duration_seconds": duration,
                }

            # Find database file (should be in script_data/)
            db_path = None
            for db_file in (legacy_env / "script_data").glob("*.db"):
                db_path = db_file
                break

            return {
                "success": True,
                "output_dir": output_dir,
                "database_path": db_path,
                "duration_seconds": duration,
                "legacy_env": legacy_env,
            }

        finally:
            # Change back to original directory
            os.chdir(original_dir)

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Legacy pipeline timed out after 10 minutes",
            "duration_seconds": time.time() - start_time,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "duration_seconds": time.time() - start_time,
        }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python run_legacy_pipeline.py <input_file.xlsx> <output_dir>")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    result = run_legacy_pipeline(input_file, output_dir)

    # Output results as JSON for test to consume
    import json

    # Convert Path objects to strings for JSON serialization
    serializable_result = {}
    for k, v in result.items():
        if isinstance(v, Path):
            serializable_result[k] = str(v)
        else:
            serializable_result[k] = v

    print(json.dumps(serializable_result))

    sys.exit(0 if result["success"] else 1)
