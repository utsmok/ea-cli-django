from pathlib import Path

import polars as pl


def compare_excels(django_path, legacy_path, report_path, sheet_name="Complete data"):
    with Path.open(report_path, "w", encoding="utf-8") as f:

        def log(msg):
            f.write(msg + "\n")

        log(f"Comparing\n  Django: {django_path}\n  Legacy: {legacy_path}")

        if not Path.exists(django_path):
            log(f"ERROR: Django file not found: {django_path}")
            return
        if not Path.exists(legacy_path):
            log(f"ERROR: Legacy file not found: {legacy_path}")
            return

        df_django = pl.read_excel(django_path, sheet_name=sheet_name)
        df_legacy = pl.read_excel(legacy_path, sheet_name=sheet_name)

        log(f"Django shape: {df_django.shape}")
        log(f"Legacy shape: {df_legacy.shape}")

        # Compare columns
        django_cols = df_django.columns
        legacy_cols = df_legacy.columns

        if django_cols == legacy_cols:
            log("✓ Column names and order match perfectly.")
        else:
            log("✗ Column names or order mismatch!")
            missing_in_django = [c for c in legacy_cols if c not in django_cols]
            extra_in_django = [c for c in django_cols if c not in legacy_cols]
            if missing_in_django:
                log(f"  Missing in Django: {missing_in_django}")
            if extra_in_django:
                log(f"  Extra in Django: {extra_in_django}")

            # Check order
            max_len = max(len(legacy_cols), len(django_cols))
            for i in range(max_len):
                l = legacy_cols[i] if i < len(legacy_cols) else "MISSING"
                d = django_cols[i] if i < len(django_cols) else "MISSING"
                if l != d:
                    log(f"  Mismatch at index {i}: Legacy='{l}', Django='{d}'")

        # Sort
        # First ensure material_id is string for consistent sorting/comparison if needed
        # but usually it's already string or int
        df_django = df_django.sort("material_id")
        df_legacy = df_legacy.sort("material_id")

        IGNORE_COLS = [
            "course_link",  # Ignored as per legacy reasons or phase A
            # Add any other columns to ignore here
        ]

        common_cols = [
            c for c in legacy_cols if c in django_cols and c not in IGNORE_COLS
        ]

        # Data differences
        diffs = {}
        for col in common_cols:
            v_django = df_django[col].fill_null("NULL").cast(pl.String).to_list()
            v_legacy = df_legacy[col].fill_null("NULL").cast(pl.String).to_list()

            col_diffs = []
            for i, (d, l) in enumerate(zip(v_django, v_legacy, strict=False)):
                if d != l:
                    col_diffs.append((i, d, l))

            if col_diffs:
                diffs[col] = col_diffs

        if not diffs:
            log("✓ All data values match in common columns.")
        else:
            log(f"✗ Found value differences in {len(diffs)} columns:")
            for col, d_list in diffs.items():
                log(
                    f"  Column '{col}': {len(d_list)} differences. Sample: row {d_list[0][0]}, Django='{d_list[0][1]}', Legacy='{d_list[0][2]}'"
                )


if __name__ == "__main__":
    faculties_dir = Path("exports/faculty_sheets")
    if not faculties_dir.exists():
        pass
    else:
        # Loop through all faculty directories
        for faculty_path in faculties_dir.iterdir():
            if faculty_path.is_dir():
                faculty_name = faculty_path.name
                if faculty_name == "backups":
                    continue

                # Compare inbox
                compare_excels(
                    str(faculty_path / "inbox.xlsx"),
                    f"ea-cli/faculty_sheets/{faculty_name}/inbox.xlsx",
                    f"comparison_report_{faculty_name}_inbox.txt",
                )

                # Compare overview
                compare_excels(
                    str(faculty_path / "overview.xlsx"),
                    f"ea-cli/faculty_sheets/{faculty_name}/overview.xlsx",
                    f"comparison_report_{faculty_name}_overview.txt",
                )
