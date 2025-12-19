# Task: Fix Missing Organization Data in Excel Exports

## Issue
The field `course_contacts_organizations` is always 'NULL' in Excel exports.
Investigation reveals that while `OsirisScraperService` correctly fetches organization data from the UT People Page, the enrichment task in `src/apps/enrichment/tasks.py` does not persist this data to the database or link it to the `Person` model.

## Implementation Plan

### 1. Reproduction Test
- Add a test case to `src/apps/enrichment/tests/test_tasks.py`.
- Mock `fetch_person_data` to return:
  ```python
  {
      "main_name": "Test Person",
      "email": "test@utwente.nl",
      "orgs": [
          {"name": "University of Twente", "abbr": "UT"},
          {"name": "EEMCS", "abbr": "EEMCS"},
          {"name": "Pervasive Systems", "abbr": "EEMCS-PS"}
      ]
  }
  ```
- Assert that `Organization` and `Faculty` records are created and linked to the `Person`.

### 2. Update Enrichment Task (`src/apps/enrichment/tasks.py`)
- Import `Organization` and `Faculty` from `apps.core.models`.
- In `enrich_item`, after updating the `Person` record:
  - Iterate through `p_data.get("orgs", [])`.
  - Maintain a `parent_org` variable and a `full_abbr_parts` list.
  - For each org:
    - `level = 0` if `abbr == "UT"`, `1` if it's a faculty, `2+` otherwise.
    - `full_abbr = "-".join(full_abbr_parts + [abbr])`.
    - If `level == 1`, use `Faculty.objects.aupdate_or_create`.
    - Else, use `Organization.objects.aupdate_or_create`.
    - Link to `person.orgs`.
    - If `level == 1`, set `person.faculty = faculty_obj`.

### 3. Verification
- Run `pytest src/apps/enrichment/tests/test_tasks.py`.
- Verify that `course_contacts_organizations` in Excel exports (via `ExportService`) now contains pipe-separated abbreviations.
