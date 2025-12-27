#!/usr/bin/env python
"""
Script to generate legacy baseline outputs for parity testing.

This script sets up and runs the legacy code with the test data file
to produce baseline outputs that can be compared against the new code.

PREREQUISITES:
1. Python 3.12.2 installed
2. uv installed
3. Network access for Osiris/Canvas APIs
4. Test data file: test_data/e2e/base_case_5.xlsx

USAGE:
    cd /home/sam/dev/ea-cli-django
    python scripts/generate_legacy_baseline.py

OUTPUT:
    test_data/legacy_baseline/
    ├── faculty_sheets/       # Legacy output Excel files
    ├── script_data/           # Legacy database
    └── baseline_info.json     # Metadata about the baseline
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def main():
    """Generate legacy baseline outputs."""

    # Paths
    repo_root = Path("/home/sam/dev/ea-cli-django")
    test_file = repo_root / "test_data/e2e/base_case_5.xlsx"
    baseline_dir = repo_root / "test_data/legacy_baseline"
    legacy_dir = repo_root / "ea-cli"

    if not test_file.exists():
        print(f"Error: Test file not found: {test_file}")
        sys.exit(1)

    print("=" * 70)
    print("LEGACY BASELINE GENERATION")
    print("=" * 70)
    print()
    print(f"Test file: {test_file}")
    print(f"Baseline output: {baseline_dir}")
    print(f"Legacy code: {legacy_dir}")
    print()

    # Clean baseline directory
    if baseline_dir.exists():
        response = input(f"Delete existing baseline at {baseline_dir}? (y/N): ")
        if response.lower() == 'y':
            shutil.rmtree(baseline_dir)
            print("✓ Cleaned existing baseline")
        else:
            print("Aborted.")
            sys.exit(1)

    # Set up legacy environment
    print("\n[1/5] Setting up legacy environment...")
    baseline_dir.mkdir(parents=True, exist_ok=True)

    # Create directory structure in baseline
    dirs = [
        baseline_dir / "raw_copyright_data",
        baseline_dir / "faculty_sheets",
        baseline_dir / "script_data",
        baseline_dir / "pdf_downloads",
        baseline_dir / "overviews_backup",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Copy test file
    shutil.copy(test_file, baseline_dir / "raw_copyright_data" / test_file.name)
    print(f"✓ Copied test file to {baseline_dir / 'raw_copyright_data'}")

    # Create custom settings.yaml for baseline
    print("\n[2/5] Creating custom settings.yaml...")
    settings_template = legacy_dir / "settings.yaml"
    custom_settings = baseline_dir / "settings.yaml"

    # Read template
    import yaml
    with open(settings_template) as f:
        settings = yaml.safe_load(f)

    # Update directories
    settings["directories"] = {
        "raw_copyright_data": "raw_copyright_data",
        "faculties_dir": "faculty_sheets",
        "overviews_backup": "overviews_backup",
        "script_data": "script_data",
        "pdf_downloads": "pdf_downloads",
    }

    # Save custom settings
    with open(custom_settings, "w") as f:
        yaml.dump(settings, f)
    print(f"✓ Created {custom_settings}")

    # Run legacy pipeline
    print("\n[3/5] Running legacy pipeline...")
    print("This will make REAL API calls to Osiris and Canvas.")
    print("Expected duration: 2-5 minutes")
    print()

    response = input("Proceed? (y/N): ")
    if response.lower() != 'y':
        print("Aborted.")
        sys.exit(1)

    os.chdir(legacy_dir)

    try:
        start_time = datetime.now()

        result = subprocess.run(
            [
                "uv",
                "run",
                "run.py",
                "process",
            ],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes
            env={**os.environ, "SETTINGS_PATH": "../test_data/legacy_baseline/settings.yaml"},
        )

        duration = (datetime.now() - start_time).total_seconds()
        # write stdout and stderr to files for debugging
        with open(baseline_dir / "legacy_stdout.log", "w") as f:
            f.write(result.stdout)
        with open(baseline_dir / "legacy_stderr.log", "w") as f:
            f.write(result.stderr)
        if result.returncode != 0:
            print("\n❌ Legacy pipeline failed!")
            print("\nSTDOUT:")
            print(result.stdout)
            print("\nSTDERR:")
            print(result.stderr)
            sys.exit(1)

        print(f"✓ Legacy pipeline completed in {duration:.1f} seconds")

    except subprocess.TimeoutExpired:
        print("\n❌ Legacy pipeline timed out after 10 minutes")
        sys.exit(1)
    finally:
        os.chdir(repo_root)

    # Check outputs
    print("\n[4/5] Checking outputs...")

    faculty_sheets = list((legacy_dir / "faculty_sheets").glob("*/*.xlsx"))
    if not faculty_sheets:
        print("❌ No faculty sheets generated!")
        sys.exit(1)

    print(f"✓ Found {len(faculty_sheets)} faculty sheet files")

    # Find database
    db_files = list((legacy_dir).glob("*.sqlite3"))
    if not db_files:
        print("❌ No database file created!")
        sys.exit(1)

    db_path = db_files[0]
    print(f"✓ Database: {db_path.name}")

    # Create baseline info
    print("\n[5/5] Creating baseline metadata...")
    baseline_info = {
        "generated_at": datetime.now().isoformat(),
        "test_file": str(test_file),
        "test_file_md5": subprocess.check_output(
            ["md5sum", str(test_file)], text=True
        ).split()[0],
        "duration_seconds": duration,
        "faculty_sheets": [str(f.relative_to(legacy_dir / "faculty_sheets")) for f in faculty_sheets],
        "database": str(db_path.relative_to(legacy_dir)),
        "python_version": "3.12.2",
    }

    with open(baseline_dir / "baseline_info.json", "w") as f:
        json.dump(baseline_info, f, indent=2)

    print(f"✓ Created {baseline_dir / 'baseline_info.json'}")

    # Summary
    print("\n" + "=" * 70)
    print("BASELINE GENERATION COMPLETE")
    print("=" * 70)
    print(f"\nBaseline location: {baseline_dir}")
    print(f"Duration: {duration:.1f} seconds")
    print(f"\nNext steps:")
    print("1. Review the generated faculty sheets")
    print("2. Run the parity test:")
    print("   uv run pytest src/apps/core/tests/test_legacy_parity.py -v -m 'external_api'")
    print()


if __name__ == "__main__":
    main()
