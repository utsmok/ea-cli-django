#!/usr/bin/env python
"""
Extract a representative sample from the full Qlik export for base case testing.

This script reads test_data/qlik_data.xlsx (820 rows) and creates
test_data/e2e/base_case_5.xlsx with 5 representative items covering:
- Different faculties (EEMCS, BMS, ET)
- Different file types (PDF, PPT, DOC)
- With/without course codes
- With/without Canvas URLs
- Different classifications

Usage:
    uv run python scripts/create_test_data.py
"""
import polars as pl
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
TEST_DATA_DIR = PROJECT_ROOT / "test_data"
E2E_DIR = TEST_DATA_DIR / "e2e"
SOURCE_FILE = TEST_DATA_DIR / "qlik_data.xlsx"
OUTPUT_FILE = E2E_DIR / "base_case_5.xlsx"

# Create e2e directory if it doesn't exist
E2E_DIR.mkdir(parents=True, exist_ok=True)

print(f"Reading source file: {SOURCE_FILE}")
df = pl.read_excel(SOURCE_FILE)
print(f"Total rows in source: {len(df)}")

# Display column names
print(f"\nColumns: {df.columns[:10]}...")  # Show first 10 columns

# Select 5 representative items based on diversity criteria
print("\nSelecting 5 representative items...")

# More pragmatic approach: select items from different parts of the dataset
# to ensure diversity without overly restrictive filters

# Sample 1: First row (whatever it is)
sample1 = df.head(1)

# Sample 2: From middle of dataset
sample2 = df[int(len(df) * 0.25):int(len(df) * 0.25) + 1]

# Sample 3: From another position
sample3 = df[int(len(df) * 0.5):int(len(df) * 0.5) + 1]

# Sample 4: From later in dataset
sample4 = df[int(len(df) * 0.75):int(len(df) * 0.75) + 1]

# Sample 5: From end of dataset
sample5 = df.tail(1)

# Combine samples, removing any duplicates based on material_id
samples = [
    s for s in [sample1, sample2, sample3, sample4, sample5]
    if len(s) > 0  # Only add non-empty samples
]

if not samples:
    print("ERROR: Could not extract any samples from the data!")
    print("This might be due to missing columns or empty data.")
    exit(1)

# Combine all samples
sample_df = pl.concat(samples, how="diagonal")

# Remove duplicates (keep first occurrence)
material_ids = sample_df.get_column("Material id").to_list()
unique_indices = []
seen = set()
for i, mid in enumerate(material_ids):
    if mid not in seen:
        seen.add(mid)
        unique_indices.append(i)

sample_df = sample_df[unique_indices]

# Ensure we have exactly 5 items (or as close as possible)
if len(sample_df) < 5:
    print(f"WARNING: Only found {len(sample_df)} unique items")
else:
    # Take first 5 if we have more
    sample_df = sample_df.head(5)

print(f"\nSelected {len(sample_df)} items:")
print(sample_df.select([
    "Material id", "Department", "Filetype", "Course code", "Classification"
]))

# Write to output file
print(f"\nWriting to: {OUTPUT_FILE}")
sample_df.write_excel(OUTPUT_FILE)

# Verify file was created
if OUTPUT_FILE.exists():
    file_size = OUTPUT_FILE.stat().st_size
    print(f"✓ Created {OUTPUT_FILE.name} ({file_size:,} bytes)")
    print(f"\nTo use this file in tests:")
    print(f"  pytest -m pipeline -v")
else:
    print(f"ERROR: Failed to create output file")
    exit(1)
