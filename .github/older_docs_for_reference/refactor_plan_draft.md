# Phase A Refactor Plan: Core Ingestion & Processing Pipeline
**Date:** December 16, 2025
**Status:** Draft for Implementation
**Phase:** A (Core Functionality)
**Target:** Replace legacy ingestion/processing logic with Django models and services

---

## Executive Summary

Phase A restructures the ingestion pipeline around clean data modeling and processing logic. The goal is to replace ~1,800 lines of legacy tortoise code ([ea-cli/easy_access/db/update.py](../ea-cli/easy_access/db/update.py)) with modular Django services while maintaining backward compatibility with existing Excel export workflows.

### Key Design Decisions

1. **Raw Data Storage:** Ingestion models store raw data as-is from Excel/CSV. Cleaning happens in a separate transformation step (raw → clean → process).
2. **User Tracking:** Editor information stored as string in `ChangeLog` model (defer custom User model to Phase C).
3. **Configuration:** Keep legacy `settings.yaml` for Phase A. Database-backed config models deferred to Phase B/C. Current Django porting started in [src/config/university.py](../src/config/university.py).

---

## Phase A Scope: Core Functionality

Phase A consists of 10 major steps, each with detailed sub-tasks and code references:

### Step 1: Create Ingestion & Tracking Models

**Objective:** Build data models to track raw ingestion data and changes with full audit trail.

**Models to Create:** (in [src/apps/ingest/models.py](../src/apps/ingest/models.py))

1. **`FacultyEntry`** — Raw faculty sheet row
   - Fields:
     - `id` (BigAutoField, PK)
     - `ingestion` (FK to `FacultyIngestion`)
     - `material_id` (CharField, nullable, indexed) — unique ID from faculty sheet
     - `ingestion_timestamp` (DateTimeField, auto_now_add) — when this entry was ingested
     - `raw_data` (JSONField) — raw row from Excel as-is, no cleaning
     - `status` (CharField, choices: PENDING, PROCESSED, ERROR, SKIPPED)
     - `processing_error` (TextField, nullable) — error details if status=ERROR
   - Unique constraint: `(ingestion, material_id)`
   - Reference legacy: [ea-cli/easy_access/db/models.py](../ea-cli/easy_access/db/models.py) `StagedFacultyUpdate`

2. **`QlikEntry`** — Raw Qlik export row
   - Fields:
     - `id` (BigAutoField, PK)
     - `ingestion` (FK to `QlikIngestion`)
     - `material_id` (CharField, nullable, indexed)
     - `ingestion_timestamp` (DateTimeField, auto_now_add)
     - `raw_data` (JSONField) — raw row from Qlik export as-is
     - `status` (CharField, choices: PENDING, PROCESSED, ERROR, SKIPPED)
     - `processing_error` (TextField, nullable)
   - Unique constraint: `(ingestion, material_id)`

3. **`FacultyIngestion`** — Batch grouping for faculty sheet ingestion
   - Fields:
     - `id` (BigAutoField, PK)
     - `source_file` (CharField) — filename/path of source Excel
     - `ingestion_timestamp` (DateTimeField, auto_now_add)
     - `status` (CharField, choices: PENDING, PROCESSING, COMPLETE, ERROR)
     - `entries_count` (IntegerField) — total entries in batch
     - `processed_count` (IntegerField, default=0) — entries successfully processed
     - `error_count` (IntegerField, default=0) — entries with errors
     - `summary` (JSONField, nullable) — { "items_created": N, "items_updated": N, "errors": [...] }
   - Reference legacy: [ea-cli/easy_access/db/models.py](../ea-cli/easy_access/db/models.py) implicit grouping

4. **`QlikIngestion`** — Batch grouping for Qlik export ingestion
   - Fields: identical structure to `FacultyIngestion`

5. **`ChangeLog`** — Audit trail for all item changes
   - Fields:
     - `id` (BigAutoField, PK)
     - `item` (FK to `CopyrightItem`)
     - `ingestion_batch` (FK to `FacultyIngestion` or `QlikIngestion`, nullable) — which ingestion triggered this
     - `change_type` (CharField, choices: CREATE, UPDATE, OVERRIDE) — what kind of change
     - `fields_changed` (JSONField) — { "field_name": { "old": old_value, "new": new_value }, ... }
     - `change_reason` (TextField, nullable) — why this change was made
     - `editor` (CharField) — user/system that made the change (default: "system" or editor string from override)
     - `timestamp` (DateTimeField, auto_now_add)
   - Reference legacy: [ea-cli/easy_access/db/models.py](../ea-cli/easy_access/db/models.py) `ChangeLog`

6. **`ProcessingFailure`** — Track processing errors for inspection and retry
   - Fields:
     - `id` (BigAutoField, PK)
     - `ingestion_batch` (FK to `FacultyIngestion` or `QlikIngestion`)
     - `entry_data` (JSONField) — the problematic raw entry
     - `error_type` (CharField) — e.g., "VALIDATION_ERROR", "MERGE_ERROR", "DATABASE_ERROR"
     - `error_message` (TextField)
     - `stack_trace` (TextField, nullable)
     - `resolved` (BooleanField, default=False)
     - `resolved_by` (CharField, nullable) — admin user who resolved
     - `resolution_notes` (TextField, nullable)
     - `timestamp` (DateTimeField, auto_now_add)
   - Reference legacy: [ea-cli/easy_access/db/models.py](../ea-cli/easy_access/db/models.py) `ProcessingError`

**Django Admin Registration:** (in [src/apps/ingest/admin.py](../src/apps/ingest/admin.py))
- Register all 6 models
- `FacultyEntryInline` and `QlikEntryInline` as inline admins within `FacultyIngestionAdmin` / `QlikIngestionAdmin`
- `ProcessingFailureAdmin` with custom action buttons for "Retry" and "Mark Resolved"
- `ChangeLogAdmin` with read-only fields and filtering by `item`, `change_type`, `timestamp`

**Database Migrations:**
- Create migration: `0007_faculty_entry_qlik_entry_models.py`
- Create migration: `0008_ingestion_models.py`
- Create migration: `0009_changelog_and_failure_models.py`

---

### Step 2: Port Data Standardization Logic

**Objective:** Build reusable service to normalize raw Excel/CSV data to clean form (enum parsing, field type casting, org mapping).

**Files to Create:**
- [src/apps/ingest/services/standardizer.py](../src/apps/ingest/services/standardizer.py)
- [src/apps/ingest/services/validators.py](../src/apps/ingest/services/validators.py)

**Service: `DataFrameStandardizer`** (in standardizer.py)

Purpose: Convert raw Polars DataFrame from Excel to standardized/cleaned data.

Architecture:

```python
class DataFrameStandardizer:
    def __init__(self, ingestion_type: str):  # "faculty" or "qlik"
        self.ingestion_type = ingestion_type
        self.column_mapping = load_column_mapping()  # from settings.yaml / [university.py](http://_vscodecontentref_/0)

    def standardize(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        1. Normalize column names (legacy → standard)
        2. Validate/parse enums
        3. Cast data types
        4. Map faculties/departments
        5. Add defaults (e.g., workflow_status="ToDo")
        6. Return cleaned DataFrame
        """
        df = self._rename_columns(df)
        df = self._parse_enums(df)
        df = self._cast_types(df)
        df = self._map_faculties(df)
        df = self._add_defaults(df)
        return df

    def _rename_columns(self, df) -> pl.DataFrame:
        # Map legacy column names from [settings.py](http://_vscodecontentref_/1) column_mapping to standard names
        # Reference: [ingest.py](http://_vscodecontentref_/2) standardize_dataframe()
        mapping = self.column_mapping.get(self.ingestion_type, {})
        return df.rename(mapping)

    def _parse_enums(self, df) -> pl.DataFrame:
        # Validate and convert string values to enum choices
        # Enums reference: [models.py](http://_vscodecontentref_/3) choices
        enum_fields = {
            'workflow_status': WorkflowStatus.choices,
            'filetype': Filetype.choices,
            'classification': Classification.choices,
            'v2_classification': ClassificationV2.choices,
            'overnamestatus': OvernameStatus.choices,
            'infringement': Infringement.choices,
            'lengte': Lengte.choices,
        }
        for field, choices in enum_fields.items():
            if field in df.columns:
                df = self._validate_enum_column(df, field, choices)
        return df

    def _cast_types(self, df) -> pl.DataFrame:
        # Cast columns to correct types (dates, ints, booleans)
        # Reference: [ingest.py](http://_vscodecontentref_/4) parse_dates, parse_ints
        casts = {
            'material_id': pl.Int64 or pl.Utf8,  # nullable int or string ID
            'file_size': pl.Int64,
            'count_students_registered': pl.Int64,
            'created_at': pl.Date,
            'modified_at': pl.Date,
            'file_exists': pl.Boolean,
        }
        for col, dtype in casts.items():
            if col in df.columns:
                df = df.with_columns(pl.col(col).cast(dtype, strict=False))
        return df

    def _map_faculties(self, df) -> pl.DataFrame:
        # Map department/programme name to faculty abbreviation
        # Reference: [university.py](http://_vscodecontentref_/5) DEPARTMENT_MAPPING
        if 'department' in df.columns:
            df = df.with_columns(
                pl.col('department')
                  .map_elements(lambda x: DEPARTMENT_MAPPING.get(x, 'UNM'))
                  .alias('faculty_abbr')
            )
        return df

    def _add_defaults(self, df) -> pl.DataFrame:
        # Add default values for missing fields
        defaults = {
            'workflow_status': WorkflowStatus.TODO,
            'status': Status.NOT_STARTED,
            'filetype': Filetype.UNKNOWN,
        }
        for col, default in defaults.items():
            if col not in df.columns:
                df = df.with_columns(pl.lit(default).alias(col))
        return df
```

Service: FieldValidator (in validators.py)

Purpose: Validate individual fields for data quality before merge.

class FieldValidator:
    @staticmethod
    def validate_material_id(value) -> bool:
        """Material ID must be non-empty string/int"""
        return value is not None and str(value).strip() != ""

    @staticmethod
    def validate_enum_field(value, enum_choices) -> bool:
        """Enum value must be in valid choices"""
        return value in [choice[0] for choice in enum_choices]

    @staticmethod
    def validate_url(value) -> bool:
        """URL must be valid if present"""
        if not value:
            return True
        return value.startswith(('http://', 'https://'))

    @staticmethod
    def validate_date(value) -> bool:
        """Date must be valid if present"""
        if not value:
            return True
        # Try parsing various date formats
        ...


Tests to Write: (in src/apps/ingest/tests/test_standardizer.py)

    Test column renaming with legacy → standard mappings
    Test enum parsing with valid/invalid values
    Test type casting (dates, ints)
    Test faculty mapping (department name → abbreviation)
    Test default values added
    Test with real data  ea-cli/
    Reference: ea-cli/tests/

### Step 3: Implement Ranked Field Comparison Strategy
**Objective:** Translate legacy merge rules from ea-cli/easy_access/db/update.py into reusable Django service.

**Files to Create:**
    src/apps/ingest/services/comparison.py
    src/apps/ingest/services/merge_rules.py

Service: FieldComparisonStrategy (in comparison.py)
Purpose: Determine which value should win when comparing old vs. new data.

```python
from enum import Enum
from typing import Any

class ComparisonStrategy(Enum):
    PRIORITY_LIST = "priority_list"  # Use ranked priority list
    LONGER_STRING = "longer_string"  # Longer string wins
    NEWER_TIMESTAMP = "newer_timestamp"  # Newer timestamp wins
    ALWAYS_NEW = "always_new"  # New value always wins
    MANUAL_ONLY = "manual_only"  # Only update if value is manual/not-null

class FieldComparisonRule:
    """Rule for comparing a single field between old and new values"""

    def __init__(self, field_name: str, strategy: ComparisonStrategy,
                 priority_list: list = None):
        self.field_name = field_name
        self.strategy = strategy
        self.priority_list = priority_list  # [best, good, acceptable, worst]

    def compare(self, old_value: Any, new_value: Any) -> Any:
        """
        Compare old vs new value and return winner.
        Returns: (winner, should_update: bool)
        """
        if self.strategy == ComparisonStrategy.PRIORITY_LIST:
            old_rank = self.priority_list.index(old_value) if old_value in self.priority_list else len(self.priority_list)
            new_rank = self.priority_list.index(new_value) if new_value in self.priority_list else len(self.priority_list)
            # Lower rank index = higher priority
            if new_rank < old_rank:
                return (new_value, True)
            return (old_value, False)

        elif self.strategy == ComparisonStrategy.LONGER_STRING:
            if new_value and old_value:
                if len(str(new_value)) > len(str(old_value)):
                    return (new_value, True)
            elif new_value and not old_value:
                return (new_value, True)
            return (old_value, False)

        elif self.strategy == ComparisonStrategy.NEWER_TIMESTAMP:
            # Assume new_value is always newer (ingestion order)
            return (new_value, True) if new_value else (old_value, False)

        elif self.strategy == ComparisonStrategy.ALWAYS_NEW:
            return (new_value, True)

        elif self.strategy == ComparisonStrategy.MANUAL_ONLY:
            # Only update if new_value is explicitly set (not null)
            if new_value is not None:
                return (new_value, True)
            return (old_value, False)

class MergeRuleSet:
    """Collection of field comparison rules for a specific ingestion type"""

    def __init__(self, ingestion_type: str):  # "faculty" or "qlik"
        self.ingestion_type = ingestion_type
        self.rules = self._load_rules()
        self.min_changes_threshold = 3  # Min fields changed to trigger DB update

    def _load_rules(self) -> dict:
        """Load merge rules from merge_rules.py based on ingestion_type"""
        if self.ingestion_type == "qlik":
            return QLIK_MERGE_RULES
        elif self.ingestion_type == "faculty":
            return FACULTY_MERGE_RULES
        else:
            raise ValueError(f"Unknown ingestion_type: {self.ingestion_type}")

    def compare_item(self, old_item: CopyrightItem, new_data: dict) -> dict:
        """
        Compare old item with new data, apply rules.
        Returns: {
            'should_update': bool,
            'changes': { 'field': {'old': old_val, 'new': new_val}, ... },
            'updated_fields': { 'field': new_val, ... }
        }
        """
        changes = {}
        updated_fields = {}

        for field_name, rule in self.rules.items():
            if field_name not in new_data:
                continue

            old_value = getattr(old_item, field_name, None)
            new_value = new_data[field_name]

            if old_value != new_value:
                winner, should_update = rule.compare(old_value, new_value)
                if should_update:
                    changes[field_name] = {'old': old_value, 'new': new_value}
                    updated_fields[field_name] = new_value

        should_update = len(changes) >= self.min_changes_threshold

        return {
            'should_update': should_update,
            'changes': changes,
            'updated_fields': updated_fields,
        }
```

Merge Rules Configuration (in merge_rules.py)

for field values, it's important to consider the enums defined in core/models.py for possible field values, see:

```python


class Classification(Enum):
    """
    Classification v1 system -- will be replaced by v2 system once we migrate fully.
    """

    OPEN_ACCESS = "open access"
    KORTE_OVERNAME = "korte overname"
    MIDDELLANGE_OVERNAME = "middellange overname"
    LANGE_OVERNAME = "lange overname"

    EIGEN_MATERIAAL_POWERPOINT = "eigen materiaal - powerpoint"
    EIGEN_MATERIAAL_TITELINDICATIE = "eigen materiaal - titelindicatie"
    EIGEN_MATERIAAL_OVERIG = "eigen materiaal - overig"
    EIGEN_MATERIAAL = "eigen materiaal"

    ONBEKEND = "onbekend"  # default for unclassified items
    NIET_GEANALYSEERD = "niet geanalyseerd"
    IN_ONDERZOEK = "in onderzoek"
    VERWIJDERVERZOEK_VERSTUURD = "verwijderverzoek verstuurd"
    LICENTIE_BESCHIKBAAR = "licentie beschikbaar"


# V2 classification system + mapping + notes


class ClassificationV2(Enum):
    """
    The new classification system for V2 of the copyright tool.
    """

    # Yes classifications
    JA_OPEN_LICENTIE = "Ja (open licentie)"
    JA_BIBLIOTHEEK_LICENTIE = "Ja (bibilotheek licentie)"
    JA_DIRECTE_TOESTEMMING = "Ja (directe toestemming)"
    JA_PUBLIEK_DOMEIN = "Ja (Publiek domein)"
    JA_EIGEN_WERK = "Ja (eigen werk)"
    JA_STUDENTWERK = "Ja (studentwerk)"
    JA_EASY_ACCESS = "Ja (easy access)"
    JA_ANDERS = "Ja (anders)"

    JA_DIRECTE_TOESTEMMING_TIJDELIJK = "Ja (directe toestemming) - tijdelijk"
    JA_BIBLIOTHEEK_LICENTIE_TIJDELIJK = "Ja (bibilotheek licentie)- tijdelijk"
    JA_ANDERS_TIJDELIJK = "Ja (anders) - tijdelijk"

    # No classifications
    NEE_LINK_BESCHIKBAAR = "Nee (Link beschikbaar)"
    NEE_STUDENTWERK = "Nee (studentwerk)"
    NEE = "Nee"

    # Other classifications // default to this when not classified
    ONBEKEND = "Onbekend"


class OvernameStatus(Enum):
    OVERNAME_INBREUKMAKENDE = "Overname (inbreukmakende)"
    OVERNAME_ANDERE = "Overname (andere)"
    GEEN_OVERNAME = "Geen overname"
    ONBEKEND = "Onbekend"


class Lengte(Enum):
    KORT = "Kort"
    MIDDELLANG = "Middellang"
    LANG = "Lang"
    ONBEKEND = "Onbekend"


@dataclass
class ClassificationMapping:
    classification: ClassificationV2
    overname_status: OvernameStatus
    length: Lengte


CLASSIFICATION_MAPPING_V1_TO_V2: dict[Classification, ClassificationMapping] = {
    Classification.OPEN_ACCESS: ClassificationMapping(
        classification=ClassificationV2.JA_OPEN_LICENTIE,
        overname_status=OvernameStatus.GEEN_OVERNAME,
        length=Lengte.ONBEKEND,
    ),
    Classification.EIGEN_MATERIAAL: ClassificationMapping(
        classification=ClassificationV2.JA_EIGEN_WERK,
        overname_status=OvernameStatus.GEEN_OVERNAME,
        length=Lengte.ONBEKEND,
    ),
    Classification.EIGEN_MATERIAAL_OVERIG: ClassificationMapping(
        classification=ClassificationV2.JA_EIGEN_WERK,
        overname_status=OvernameStatus.GEEN_OVERNAME,
        length=Lengte.ONBEKEND,
    ),
    Classification.EIGEN_MATERIAAL_POWERPOINT: ClassificationMapping(
        classification=ClassificationV2.JA_EIGEN_WERK,
        overname_status=OvernameStatus.GEEN_OVERNAME,
        length=Lengte.ONBEKEND,
    ),
    Classification.EIGEN_MATERIAAL_TITELINDICATIE: ClassificationMapping(
        classification=ClassificationV2.JA_EIGEN_WERK,
        overname_status=OvernameStatus.GEEN_OVERNAME,
        length=Lengte.ONBEKEND,
    ),
    Classification.KORTE_OVERNAME: ClassificationMapping(
        classification=ClassificationV2.JA_EASY_ACCESS,
        overname_status=OvernameStatus.OVERNAME_ANDERE,
        length=Lengte.KORT,
    ),
    Classification.MIDDELLANGE_OVERNAME: ClassificationMapping(
        classification=ClassificationV2.JA_EASY_ACCESS,
        overname_status=OvernameStatus.OVERNAME_ANDERE,
        length=Lengte.MIDDELLANG,
    ),
    Classification.LANGE_OVERNAME: ClassificationMapping(
        classification=ClassificationV2.NEE,
        overname_status=OvernameStatus.OVERNAME_INBREUKMAKENDE,
        length=Lengte.LANG,
    ),
    Classification.ONBEKEND: ClassificationMapping(
        classification=ClassificationV2.ONBEKEND,
        overname_status=OvernameStatus.ONBEKEND,
        length=Lengte.ONBEKEND,
    ),
    Classification.NIET_GEANALYSEERD: ClassificationMapping(
        classification=ClassificationV2.ONBEKEND,
        overname_status=OvernameStatus.ONBEKEND,
        length=Lengte.ONBEKEND,
    ),
    Classification.IN_ONDERZOEK: ClassificationMapping(
        classification=ClassificationV2.ONBEKEND,
        overname_status=OvernameStatus.ONBEKEND,
        length=Lengte.ONBEKEND,
    ),
    Classification.VERWIJDERVERZOEK_VERSTUURD: ClassificationMapping(
        classification=ClassificationV2.ONBEKEND,
        overname_status=OvernameStatus.OVERNAME_INBREUKMAKENDE,
        length=Lengte.ONBEKEND,
    ),
    Classification.LICENTIE_BESCHIKBAAR: ClassificationMapping(
        classification=ClassificationV2.NEE_LINK_BESCHIKBAAR,
        overname_status=OvernameStatus.OVERNAME_INBREUKMAKENDE,
        length=Lengte.ONBEKEND,
    ),
}


class Filetype(Enum):
    PDF = "pdf"
    PPT = "ppt"
    DOC = "doc"
    XLSX = "xlsx"
    MP4 = "mp4"
    JPG = "jpg"
    PNG = "png"
    UNKNOWN = "unknown"
    FILE = "file"


class Status(Enum):
    PUBLISHED = "Published"
    UNPUBLISHED = "Unpublished"
    DELETED = "Deleted"


class WorkflowStatus(Enum):
    ToDo = "ToDo"
    Done = "Done"
    InProgress = "InProgress"


class Infringement(Enum):
    YES = "yes"
    NO = "no"
    MAYBE = "maybe"
    UNDETERMINED = "undetermined"


"""
Programatically generate enums for years between 2020 and 2030 for valid periods using one of these formats:
YYYY-[12]{1}[AB]{1} (eg. 2022-1A or 2022-2B)
YYYY-3 (eg. 2022-3)
YYYY-SEM[12]{1} (eg. 2022-SEM1 or 2022-SEM2)
YYYY-JAAR (eg. 2022-JAAR)
"""
Period = Enum(
    "Period",
    {
        f"{year}_{period}": f"{year}-{period}"
        for year in range(2020, 2031)
        for period in ["1A", "1B", "2A", "2B", "3", "SEM1", "SEM2", "JAAR"]
    },
)


class EntityTypes(Enum):
    """
    The types of entities we might recognize in text:
    - employee: person who works for the university (e.g. author, professor, researcher, staff)
    - author: person who wrote the work
    - person: other persons mentioned in the work
    - publisher: organization that published the work
    - organization: other organizations (e.g. companies, institutions, but also universities, research groups, etc)
    ....
    """

    EMPLOYEE = "employee"
    AUTHOR = "author"
    PUBLISHER = "publisher"
    ORGANIZATION = "organization"
```

field ingestion merge rules:
```python
from apps.core.models import WorkflowStatus, Classification, OvernameStatus, Infringement, Lengte, ...
# most of these fields have a corresponding enum in core/models.py for allowable values, ensure to always parse to enum first

# QLIK INGESTION RULES
# Qlik items: NEW → add full, EXISTING → update only specific fields with priorities
# fields to update are qlik-specific core fields that can change, which are:
# ml_prediction (qlik ml prediction, should remain stable but might change)
# classification (qlik generated classification, should never change)
# last_change (internal qlik measurement, not related to ingestion dates or anything the ea-cli tracks or adds)
# status (status of file in canvas: published/unpublished/deleted)
# count_students_registered (obviously can change over time)
# pages_x_students (can change if more students register)
# last_scan_date_university (date of last scan of uni system by qlik)
# last_scan_date_course (ditto for course system)

# retrieved_from_copyright_on (date set by ea-cli when we retrieved this export from qlik; maybe not store this here as it's not raw data?)

QLIK_MERGE_RULES = {
    # to be filled
}

# FACULTY INGESTION RULES
# Faculty items: NEVER new, only update changeable fields
# Faculty data has priority for classification/workflow_status
# so don't use priority lists for these! Always overwrite with current values in the sheets basically.
# we might need other strategies later, for now this should suffice.


# fields [default value]:
# v2_manual_classification [ONBEKEND]
# v2_lengte [ONBEKEND]
# v2_overnamestatus [ONBEKEND]
# manual_classification (alt: v1_manual_classification) [ONBEKEND]
# manual_identifier [null]
# remarks ["" / null]
# scope [ALTIJD]

FACULTY_MERGE_RULES = {
    # to be filled
}

```

Tests to Write: (in src/apps/ingest/tests/test_comparison.py)

    Test PRIORITY_LIST strategy with ranked values
    Test LONGER_STRING strategy
    Test MANUAL_ONLY strategy (null handling)
    Test min_changes_threshold logic
    Test with real CopyrightItem + new_data scenarios
    Reference: ea-cli/tests/test_update_refactor.py (many test cases)

### Step 4: Create Processing Tasks & Commands
Objective: Build async tasks and management commands to read staged entries, compare, and execute DB updates.
Files to Create:
    src/apps/ingest/tasks.py (update existing)
    src/apps/ingest/management/commands/process_faculty_ingestion.py
    src/apps/ingest/management/commands/process_qlik_ingestion.py
    src/apps/ingest/services/processor.py
Async Task: process_faculty_ingestion_task() (in tasks.py)

```python
from django.db import transaction
from django.core.management import call_command
from apps.ingest.models import FacultyIngestion
from apps.ingest.services.processor import FacultyProcessor

@task(queue_name="default")
def process_faculty_ingestion_task(ingestion_id: int):
    """
    Process a FacultyIngestion batch:
    1. Load all FacultyEntry rows
    2. Find matching CopyrightItem by material_id
    3. Standardize raw data
    4. Apply merge rules
    5. Update CopyrightItem if changes exceed threshold
    6. Log all changes to ChangeLog
    7. Track errors in ProcessingFailure
    """
    ingestion = FacultyIngestion.objects.get(id=ingestion_id)
    processor = FacultyProcessor(ingestion)

    with transaction.atomic():
        processor.process()
        ingestion.status = 'COMPLETE'
        ingestion.summary = processor.summary()
        ingestion.save()
```

Async Task: process_qlik_ingestion_task() (in tasks.py)
```python
from apps.ingest.services.processor import QlikProcessor

@task(queue_name="default")
def process_qlik_ingestion_task(ingestion_id: int):
    """
    Process a QlikIngestion batch:
    1. Load all QlikEntry rows
    2. Find matching CopyrightItem by material_id
    3. If not found: create new CopyrightItem with all fields
    4. If found: apply merge rules for selective update
    5. Log all changes
    6. Track errors
    """
    ingestion = QlikIngestion.objects.get(id=ingestion_id)
    processor = QlikProcessor(ingestion)

    with transaction.atomic():
        processor.process()
        ingestion.status = 'COMPLETE'
        ingestion.summary = processor.summary()
        ingestion.save()
```

Service: FacultyProcessor (in processor.py)

```python
from apps.ingest.models import FacultyEntry, FacultyIngestion, ChangeLog, ProcessingFailure
from apps.ingest.services.standardizer import DataFrameStandardizer
from apps.ingest.services.merge_rules import FACULTY_MERGE_RULES, MergeRuleSet
from apps.core.models import CopyrightItem

class FacultyProcessor:
    def __init__(self, ingestion: FacultyIngestion):
        self.ingestion = ingestion
        self.standardizer = DataFrameStandardizer('faculty')
        self.merge_rules = MergeRuleSet('faculty')
        self._summary = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}

    def process(self):
        """Main processing loop"""
        entries = FacultyEntry.objects.filter(
            ingestion=self.ingestion,
            status='PENDING'
        )

        for entry in entries:
            try:
                self._process_entry(entry)
            except Exception as e:
                self._handle_error(entry, e)

    def _process_entry(self, entry: FacultyEntry):
        """Process single entry"""
        # 1. Parse and standardize raw data
        raw_data = entry.raw_data
        standardized_data = self.standardizer.standardize_row(raw_data)

        # 2. Find matching item by material_id
        material_id = standardized_data.get('material_id')
        if not material_id:
            entry.status = 'SKIPPED'
            entry.processing_error = 'No material_id found'
            entry.save()
            self._summary['skipped'] += 1
            return

        try:
            item = CopyrightItem.objects.get(material_id=material_id)
        except CopyrightItem.DoesNotExist:
            entry.status = 'SKIPPED'
            entry.processing_error = f'No CopyrightItem with material_id={material_id}'
            entry.save()
            self._summary['skipped'] += 1
            return

        # 3. Apply merge rules
        merge_result = self.merge_rules.compare_item(item, standardized_data)

        if not merge_result['should_update']:
            entry.status = 'PROCESSED'
            entry.save()
            self._summary['skipped'] += 1
            return

        # 4. Update item with new values
        for field, value in merge_result['updated_fields'].items():
            setattr(item, field, value)
        item.save()

        # 5. Log changes to ChangeLog
        ChangeLog.objects.create(
            item=item,
            ingestion_batch=self.ingestion,
            change_type='UPDATE',
            fields_changed=merge_result['changes'],
            change_reason=f'Faculty ingestion {self.ingestion.id}',
            editor='system'
        )

        entry.status = 'PROCESSED'
        entry.save()
        self._summary['updated'] += 1

    def _handle_error(self, entry: FacultyEntry, error: Exception):
        """Track processing error"""
        entry.status = 'ERROR'
        entry.processing_error = str(error)
        entry.save()

        ProcessingFailure.objects.create(
            ingestion_batch=self.ingestion,
            entry_data=entry.raw_data,
            error_type=error.__class__.__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc()
        )
        self._summary['errors'].append({
            'material_id': entry.raw_data.get('material_id'),
            'error': str(error)
        })

    def summary(self) -> dict:
        return self._summary
```

Service: QlikProcessor (similar structure, handles both NEW and UPDATE cases)

```python
class QlikProcessor:
    def _process_entry(self, entry: QlikEntry):
        """
        1. Standardize raw data
        2. Look up by material_id
        3. If NOT found: create new CopyrightItem with all fields
        4. If found: apply merge rules for selective update
        """
        # Similar to FacultyProcessor but:
        # - NEW items: full field insert
        # - EXISTING: selective update via merge rules
```

Management Commands

Create CLI commands for manual processing trigger:
```python
# process_faculty_ingestion.py
from django.core.management.base import BaseCommand
from apps.ingest.models import FacultyIngestion
from apps.ingest.tasks import process_faculty_ingestion_task

class Command(BaseCommand):
    help = 'Process pending faculty ingestions'

    def add_arguments(self, parser):
        parser.add_argument('--id', type=int, help='Specific ingestion ID to process')
        parser.add_argument('--all', action='store_true', help='Process all pending ingestions')

    def handle(self, *args, **options):
        if options['id']:
            ingestion = FacultyIngestion.objects.get(id=options['id'])
            process_faculty_ingestion_task(ingestion.id)
        elif options['all']:
            for ingestion in FacultyIngestion.objects.filter(status='PENDING'):
                process_faculty_ingestion_task(ingestion.id)
```
Tests to Write: (in src/apps/ingest/tests/test_processor.py)

    Test faculty entry processing with real data
    Test qlik entry creation (NEW items)
    Test qlik entry updates (EXISTING items)
    Test error handling and ProcessingFailure logging
    Test ChangeLog entries created correctly
    Reference: ea-cli/tests/test_update_refactor.py

### Step 5: Port Legacy Export Functions
Objective: Reimplement Excel export to maintain existing Excel workflow while dashboard is built.
Files to Create:
    src/apps/ingest/services/export.py
    src/apps/ingest/services/excel_builder.py
    src/apps/ingest/views.py (new export endpoints)

Service: ExportService (in export.py)
Purpose: Filter CopyrightItems by faculty and prepare data for Excel generation.

```python
from django.db.models import QuerySet
from apps.core.models import CopyrightItem, WorkflowStatus
from src.config.university import FACULTIES, DEPARTMENT_MAPPING

class ExportService:
    def __init__(self, faculty_abbr: str = None, workflow_status: str = None):
        """
        faculty_abbr: "BMS", "ET", "EEMCS", "TNW", "ITC", "UNM" (or None for all)
        workflow_status: "TODO", "IN_PROGRESS", "DONE" (or None for all)
        """
        self.faculty_abbr = faculty_abbr
        self.workflow_status = workflow_status

    def get_items_by_faculty(self) -> dict:
        """
        Group items by faculty.
        Returns: {
            'BMS': [ item1, item2, ... ],
            'ET': [ item3, item4, ... ],
            ...
        }
        """
        items_by_faculty = {}

        for faculty in FACULTIES:
            abbr = faculty['abbreviation']
            queryset = CopyrightItem.objects.filter(faculty=abbr)

            if self.workflow_status:
                queryset = queryset.filter(workflow_status=self.workflow_status)

            items_by_faculty[abbr] = list(queryset)

        return items_by_faculty

    def export_faculty_sheets(self, output_dir: Path = None):
        """
        Generate per-faculty Excel workbooks.
        Reference: ea-cli/easy_access/sheets/export.py group_by_faculty()

        Returns: { 'BMS': 'path/to/BMS.xlsx', 'ET': 'path/to/ET.xlsx', ... }
        """
        items_by_faculty = self.get_items_by_faculty()
        generated_files = {}

        for faculty_abbr, items in items_by_faculty.items():
            if not items:
                continue  # Skip empty faculties

            builder = ExcelBuilder(faculty_abbr, items)
            file_path = builder.build(output_dir)
            generated_files[faculty_abbr] = str(file_path)

        return generated_files
```
Service: ExcelBuilder (in excel_builder.py)

```python
Purpose: Build styled Excel workbook using openpyxl.

from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter

class ExcelBuilder:
    def __init__(self, faculty_abbr: str, items: list):
        self.faculty_abbr = faculty_abbr
        self.items = items
        self.workbook = Workbook()

        # Column configuration from legacy settings
        # Reference: ea-cli/easy_access/settings.py data_settings
        self.columns = [
            'material_id', 'title', 'course_name', 'course_code',
            'owner', 'filetype', 'file_exists', 'classification',
            'workflow_status', 'remarks', 'manual_identifier',
            'v2_manual_classification', 'v2_lengte', 'v2_overnamestatus'
        ]

    def build(self, output_dir: Path = None) -> Path:
        """
        Generate Excel workbook with:
        1. Complete data sheet (all items + fields)
        2. Data entry sheet (editable fields only with dropdowns)
        3. Conditional formatting (file_exists green/red)
        4. Data validation (workflow_status dropdown)
        5. Excel table structure
        """
        self._create_complete_sheet()
        self._create_data_entry_sheet()

        output_dir = output_dir or Path('/tmp')
        output_file = output_dir / f'{self.faculty_abbr}.xlsx'
        self.workbook.save(output_file)

        return output_file

    def _create_complete_sheet(self):
        """All items, all fields, read-only"""
        ws = self.workbook.active
        ws.title = "Complete Data"

        # Header row
        for col_idx, col_name in enumerate(self.columns, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.value = col_name
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")

        # Data rows
        for row_idx, item in enumerate(self.items, 2):
            for col_idx, col_name in enumerate(self.columns, 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                value = getattr(item, col_name, '')

                # Format file_exists with color
                if col_name == 'file_exists':
                    cell.value = "✓" if value else "✗"
                    fill_color = "00B050" if value else "FF0000"
                    cell.fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")
                else:
                    cell.value = value

    def _create_data_entry_sheet(self):
        """Editable fields with dropdowns"""
        ws = self.workbook.create_sheet("Data Entry")

        editable_columns = [
            'material_id', 'workflow_status', 'classification',
            'v2_manual_classification', 'v2_lengte', 'v2_overnamestatus', 'remarks'
        ]

        # Header row
        for col_idx, col_name in enumerate(editable_columns, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.value = col_name
            cell.font = Font(bold=True)

        # Data rows with validation
        for row_idx, item in enumerate(self.items, 2):
            for col_idx, col_name in enumerate(editable_columns, 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                value = getattr(item, col_name, '')
                cell.value = value

                # Add data validation for enum fields
                if col_name == 'workflow_status':
                    dv = DataValidation(type="list", formula1='"TODO,IN_PROGRESS,DONE"', allow_blank=True)
                    ws.add_data_validation(dv)
                    dv.add(cell)
                elif col_name == 'classification':
                    choices = ','.join([c[0] for c in Classification.choices])
                    dv = DataValidation(type="list", formula1=f'"{choices}"', allow_blank=True)
                    ws.add_data_validation(dv)
                    dv.add(cell)
```

Views for Excel Download (in views.py)
```python
from django.http import FileResponse
from django.views import View
from apps.ingest.services.export import ExportService
import tempfile

class ExportFacultySheetView(View):
    def get(self, request, faculty_abbr=None):
        """
        Download Excel for specific faculty or all faculties as ZIP.
        GET /export/faculty/{faculty_abbr}/  → Excel file
        GET /export/faculty/all/  → ZIP with all faculties
        """
        exporter = ExportService(faculty_abbr=faculty_abbr)

        with tempfile.TemporaryDirectory() as tmpdir:
            files = exporter.export_faculty_sheets(Path(tmpdir))

            if faculty_abbr and faculty_abbr != 'all':
                # Single faculty
                file_path = Path(tmpdir) / f'{faculty_abbr}.xlsx'
                return FileResponse(open(file_path, 'rb'),
                                   filename=f'{faculty_abbr}.xlsx')
            else:
                # All faculties as ZIP
                import zipfile
                zip_path = Path(tmpdir) / 'faculty_sheets.zip'
                with zipfile.ZipFile(zip_path, 'w') as zf:
                    for abbr, path in files.items():
                        zf.write(path, arcname=Path(path).name)
                return FileResponse(open(zip_path, 'rb'),
                                   filename='faculty_sheets.zip')
```
URLs (in src/apps/ingest/urls.py)
```python
from django.urls import path
from apps.ingest.views import ExportFacultySheetView

urlpatterns = [
    path('export/faculty/<str:faculty_abbr>/', ExportFacultySheetView.as_view(), name='export_faculty'),
    path('export/faculty/all/', ExportFacultySheetView.as_view(),
         {'faculty_abbr': 'all'}, name='export_all'),
]
```

Tests to Write: (in src/apps/ingest/tests/test_export.py)

    Test Excel generation with sample data
    Test conditional formatting (file_exists colors)
    Test data validation dropdowns
    Test per-faculty filtering
    Test workflow_status filtering
    Reference: ea-cli/tests/test_export_workflow.py

### Step 6: Add File Watcher & Ingestion Entry Points
Objective: Auto-detect new Excel/CSV files and trigger ingestion tasks.
Files to Create:

    src/apps/ingest/management/commands/watch_for_files.py
    src/apps/ingest/services/file_watcher.py

Management Command: watch_for_files (in management/commands/)

```python
from django.core.management.base import BaseCommand
from apps.ingest.services.file_watcher import FileWatcher
from pathlib import Path

class Command(BaseCommand):
    help = 'Watch directories for new ingestion files and trigger processing'

    def add_arguments(self, parser):
        parser.add_argument('--watch-dir', type=str,
                           help='Directory to watch (default: from settings.yaml)')
        parser.add_argument('--run-once', action='store_true',
                           help='Check once and exit (vs. continuous watch)')

    def handle(self, *args, **options):
        watch_dir = Path(options.get('watch_dir') or 'data/incoming')
        watcher = FileWatcher(watch_dir)

        if options['run_once']:
            watcher.check_once()
        else:
            self.stdout.write('Starting file watcher...')
            watcher.watch()
```
Service: FileWatcher (in file_watcher.py)
```python
from pathlib import Path
import time
from watchfiles import watch
from apps.ingest.models import FacultyIngestion, QlikIngestion
from apps.ingest.tasks import (
    ingest_excel_task,
    process_faculty_ingestion_task,
    process_qlik_ingestion_task
)
import polars as pl

class FileWatcher:
    def __init__(self, watch_dir: Path):
        self.watch_dir = Path(watch_dir)
        self.processed_files = set()

    def watch(self):
        """Continuously watch for new files"""
        for changes in watch(str(self.watch_dir), watch_filter=self._is_ingestion_file):
            for change_type, file_path in changes:
                if change_type == 'add':
                    self._process_new_file(Path(file_path))

    def check_once(self):
        """Check directory once without continuous watch"""
        for file_path in self.watch_dir.glob('**/*.{xlsx,csv}'):
            if file_path.suffix in ['.xlsx', '.csv']:
                self._process_new_file(file_path)

    def _is_ingestion_file(self, path: Path):
        """Filter for Excel and CSV files"""
        return path.suffix in ['.xlsx', '.csv'] and not path.name.startswith('~')

    def _process_new_file(self, file_path: Path):
        """
        Detect file type (Faculty or Qlik) and trigger ingestion.
        Heuristic: filename pattern or sheet names
        """
        if file_path in self.processed_files:
            return

        try:
            # Detect ingestion type from filename or content
            if 'faculty' in file_path.name.lower():
                ingestion_type = 'faculty'
            elif 'qlik' in file_path.name.lower():
                ingestion_type = 'qlik'
            else:
                # Auto-detect from sheet names
                ingestion_type = self._detect_type_from_content(file_path)

            if ingestion_type == 'faculty':
                self._ingest_faculty_file(file_path)
            elif ingestion_type == 'qlik':
                self._ingest_qlik_file(file_path)
            else:
                self.stdout.write(f'Unknown ingestion type for {file_path}')

            self.processed_files.add(file_path)
        except Exception as e:
            self.stdout.write(f'Error processing {file_path}: {e}')

    def _detect_type_from_content(self, file_path: Path) -> str:
        """Read first few rows to detect type"""
        df = pl.read_excel(file_path, n_rows=1)
        columns = df.columns

        # Heuristic: Qlik exports have specific column names
        if 'Material ID' in columns or 'file_exists' in columns:
            return 'qlik'
        elif 'material_id' in columns:
            return 'faculty'
        else:
            return None

    def _ingest_faculty_file(self, file_path: Path):
        """Read faculty Excel and create FacultyIngestion + entries"""
        df = pl.read_excel(file_path)

        # Create batch
        ingestion = FacultyIngestion.objects.create(
            source_file=str(file_path),
            status='PENDING',
            entries_count=len(df)
        )

        # Create entries
        from apps.ingest.models import FacultyEntry
        entries = [
            FacultyEntry(
                ingestion=ingestion,
                raw_data=row.to_dict()
            )
            for row in df.iter_rows()
        ]
        FacultyEntry.objects.bulk_create(entries, batch_size=5000)

        # Trigger processing task
        process_faculty_ingestion_task(ingestion.id)

    def _ingest_qlik_file(self, file_path: Path):
        """Read Qlik CSV and create QlikIngestion + entries"""
        # Similar to _ingest_faculty_file
        df = pl.read_csv(file_path)

        ingestion = QlikIngestion.objects.create(
            source_file=str(file_path),
            status='PENDING',
            entries_count=len(df)
        )

        from apps.ingest.models import QlikEntry
        entries = [
            QlikEntry(
                ingestion=ingestion,
                raw_data=row.to_dict()
            )
            for row in df.iter_rows()
        ]
        QlikEntry.objects.bulk_create(entries, batch_size=5000)

        process_qlik_ingestion_task(ingestion.id)
```

Tests to Write:

    Test file detection (Faculty vs. Qlik)
    Test ingestion batch creation
    Test entry bulk creation
    Test file move to processed/archive directory
    Reference: ea-cli/easy_access/pipeline.py (file handling)

### Step 7: Build Hard Overwrite Functionality
Objective: Accept targeted corrections (item_id → field → value) and apply direct updates.
Files to Create:

    src/apps/ingest/models.py (add OverrideIngestion model)
    src/apps/ingest/services/override.py
    src/apps/ingest/management/commands/apply_overrides.py
Model: OverrideIngestion (add to models.py)

```python
class OverrideIngestion(models.Model):
    """Hard overwrite batch for manual corrections"""
    source_file = models.CharField(max_length=2048)
    ingestion_timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('PROCESSING', 'Processing'),
            ('COMPLETE', 'Complete'),
            ('ERROR', 'Error'),
        ],
        default='PENDING'
    )
    applied_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    summary = models.JSONField(null=True)

    class Meta:
        ordering = ['-ingestion_timestamp']
```

Service: OverrideProcessor (in override.py)

```python
from apps.ingest.models import OverrideIngestion, ChangeLog
from apps.core.models import CopyrightItem
import polars as pl

class OverrideProcessor:
    def __init__(self, ingestion: OverrideIngestion):
        self.ingestion = ingestion
        self._summary = {'applied': 0, 'errors': []}

    def process_from_file(self, file_path: Path):
        """
        Read CSV/Excel with columns: material_id, field_name, corrected_value, reason (opt)
        """
        df = pl.read_csv(file_path) if file_path.suffix == '.csv' else pl.read_excel(file_path)

        for row in df.iter_rows():
            self._apply_override(row)

    def _apply_override(self, row: dict):
        """
        Apply single override:
        {
            'material_id': '12345',
            'field_name': 'classification',
            'corrected_value': 'OPEN_ACCESS',
            'reason': 'Manual correction - verified in CRC',
            'editor': 'john@example.com'
        }
        """
        try:
            material_id = row['material_id']
            field_name = row['field_name']
            new_value = row['corrected_value']
            reason = row.get('reason', 'Manual override')
            editor = row.get('editor', 'manual')

            item = CopyrightItem.objects.get(material_id=material_id)
            old_value = getattr(item, field_name)

            # Direct update (ignore all rules)
            setattr(item, field_name, new_value)
            item.last_corrected = timezone.now()  # Track correction timestamp
            item.save()

            # Log change
            ChangeLog.objects.create(
                item=item,
                ingestion_batch=self.ingestion,
                change_type='OVERRIDE',
                fields_changed={
                    field_name: {'old': old_value, 'new': new_value}
                },
                change_reason=reason,
                editor=editor
            )

            self._summary['applied'] += 1

        except Exception as e:
            self._summary['errors'].append({
                'material_id': row.get('material_id'),
                'error': str(e)
            })
```

Management Command: apply_overrides

```python
class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('file', type=str, help='CSV/Excel with overrides')
        parser.add_argument('--editor', type=str, default='system', help='Editor name')

    def handle(self, *args, **options):
        file_path = Path(options['file'])

        ingestion = OverrideIngestion.objects.create(
            source_file=str(file_path),
            status='PROCESSING'
        )

        processor = OverrideProcessor(ingestion)
        processor.process_from_file(file_path)

        ingestion.status = 'COMPLETE'
        ingestion.summary = processor._summary
        ingestion.save()

        self.stdout.write(f'Applied: {processor._summary["applied"]} overrides')
```
Future Enhancement: Timestamp Protection
```python
# In CopyrightItem model, add field:
last_corrected = models.DateTimeField(null=True)

# In processor, before accepting update from ingestion:
if item.last_corrected and ingestion_timestamp < item.last_corrected:
    skip_this_item()  # Don't overwrite manual corrections
```

Tests to Write:

    Test override application with valid material_id
    Test override with non-existent material_id
    Test ChangeLog entry with OVERRIDE type
    Test editor tracking
    Reference: restructure.md overwrite section


### Step 8: Write Comprehensive Test Suite
Objective: Port existing tests and write new Django-specific tests.

Test Files to Create:

src/apps/ingest/tests/test_standardizer.py
    Column renaming
    Enum parsing
    Type casting
    Faculty mapping
Reference: ea-cli/tests/test_safe_parsers.py
src/apps/ingest/tests/test_comparison.py
    PRIORITY_LIST strategy
    LONGER_STRING strategy
    min_changes_threshold
    Qlik merge rules
    Faculty merge rules
    Reference: ea-cli/tests/test_update_refactor.py
src/apps/ingest/tests/test_processor.py
    FacultyProcessor with real data
    QlikProcessor (new vs. update)
    Error handling
    ChangeLog creation
    ProcessingFailure logging
    Reference: ea-cli/tests/test_integration_staging.py
src/apps/ingest/tests/test_export.py
    Excel generation
    Conditional formatting
    Data validation
    Per-faculty filtering
    Reference: ea-cli/tests/test_export_workflow.py
src/apps/ingest/tests/test_models.py
    FacultyIngestion creation
    FacultyEntry creation and status tracking
    ChangeLog queries
    ProcessingFailure retry scenarios
src/apps/ingest/tests/conftest.py
    Shared pytest fixtures
    Sample CopyrightItem factory
    Sample FacultyIngestion + entries
    Reference: ea-cli/tests/conftest.py

Test Coverage Goals:

✓ Unit tests for each service
✓ Integration tests for full pipeline (ingest → process → export)
✓ Edge cases (missing fields, enum mismatches, null values)
✓ Real data scenarios from legacy test files
✓ Error cases (ProcessingFailure, retries)
Target: >85% code coverage for ingest app
Run Tests Command:
`uv run src/manage.py pytest src/apps/ingest/tests/ -v --cov=src/apps/ingest`

### Step 9: Create Database Migrations & Admin Interface
Objective: Generate Django migrations for new models and configure admin.
Files to Create:

    src/apps/ingest/migrations/
        0001_initial_ingestion_models.py
        0002_add_timestamp_fields.py
        etc. (auto-generated by makemigrations)
    src/apps/ingest/admin.py (update/create)

Generate Migrations:

`uv run src/manage.py makemigrations ingest`
`uv run src/manage.py migrate ingest`

Admin Configuration (in admin.py)

```python
from django.contrib import admin
from apps.ingest.models import (
    FacultyIngestion, FacultyEntry, QlikIngestion, QlikEntry,
    ChangeLog, ProcessingFailure, OverrideIngestion
)

@admin.register(FacultyIngestion)
class FacultyIngestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'source_file', 'ingestion_timestamp', 'status', 'entries_count', 'processed_count', 'error_count')
    list_filter = ('status', 'ingestion_timestamp')
    readonly_fields = ('ingestion_timestamp', 'entries_count', 'processed_count', 'error_count', 'summary')
    inlines = [FacultyEntryInline]
    actions = ['retry_processing']

    def retry_processing(self, request, queryset):
        from apps.ingest.tasks import process_faculty_ingestion_task
        for ingestion in queryset.filter(status__in=['ERROR', 'PENDING']):
            process_faculty_ingestion_task(ingestion.id)
        self.message_user(request, f'Queued {len(queryset)} ingestions for reprocessing')

@admin.register(ChangeLog)
class ChangeLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'item', 'change_type', 'timestamp', 'editor')
    list_filter = ('change_type', 'timestamp', 'editor')
    readonly_fields = ('item', 'ingestion_batch', 'fields_changed', 'timestamp')
    search_fields = ('item__material_id', 'editor')

@admin.register(ProcessingFailure)
class ProcessingFailureAdmin(admin.ModelAdmin):
    list_display = ('id', 'ingestion_batch', 'error_type', 'timestamp', 'resolved')
    list_filter = ('error_type', 'timestamp', 'resolved')
    readonly_fields = ('entry_data', 'stack_trace', 'timestamp')
    actions = ['mark_resolved']

    def mark_resolved(self, request, queryset):
        queryset.update(resolved=True, resolved_by=request.user.username)
        self.message_user(request, f'Marked {len(queryset)} failures as resolved')
```
Verify Migrations:


`uv run src/manage.py showmigrations ingest`
`uv run src/manage.py sqlmigrate ingest 0001`
`uv run src/manage.py migrate --dry-run`

### Step 10: Set Up Configuration Model (Future Extension)
Objective: Prepare infrastructure for database-backed config (future Phase B/C enhancement).

Current Status (Phase A):
    Keep legacy ea-cli/settings.yaml and src/config/university.py
    Load configuration on app startup: src/config/apps.py

File: src/config/apps.py (create or update)
```python
from django.apps import AppConfig

class ConfigAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'config'

    def ready(self):
        """Load settings on startup"""
        from src.config.university import UNIVERSITY_SETTINGS, FACULTIES, DEPARTMENT_MAPPING
        # Validate that required settings are loaded
        assert UNIVERSITY_SETTINGS is not None
        assert len(FACULTIES) > 0
        assert len(DEPARTMENT_MAPPING) > 0
```
Future Phase B/C Enhancement:

When dashboard is built, migrate to database-backed ConfigurationModel:

```python
# Future: src/apps/core/models.py
class Configuration(models.Model):
    """Database-backed configuration (future Phase B/C)"""
    key = models.CharField(max_length=255, unique=True)
    value = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Configuration"
```
For Phase A, document the location of configuration: src/config/university.py


### Implementation Checklist - unfinished

Models & Migrations
    Create FacultyEntry, QlikEntry models
    Create FacultyIngestion, QlikIngestion models
    Create ChangeLog model
    Create ProcessingFailure model
    Create OverrideIngestion model
    Generate and test migrations
    Run uv run src/manage.py migrate
Data Services
    Implement DataFrameStandardizer
    Implement FieldValidator
    Implement FieldComparisonStrategy and MergeRuleSet
    Implement FacultyProcessor and QlikProcessor
    Write unit tests for all services
    Verify against real data, align with legacy tests in ea-cli/tests/
Tasks & Commands
    Create process_faculty_ingestion_task()
    Create process_qlik_ingestion_task()
    Create management commands (process_faculty_ingestion, process_qlik_ingestion)
    Create file watcher service and watch_for_files command
    Create OverrideProcessor and apply_overrides command
    Test tasks with sample data
Export & Views
    Implement ExportService
    Implement ExcelBuilder with openpyxl
    Create export views and URLs
    Test Excel generation and formatting
    Verify backward compatibility with legacy sheets
