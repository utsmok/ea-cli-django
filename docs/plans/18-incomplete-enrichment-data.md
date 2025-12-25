# Task 18: Incomplete Enrichment Data Extraction

## Overview

Fix incomplete person data enrichment - specifically the missing faculty/organization extraction from people pages. The legacy code has a fully working implementation that should be referenced.

**Current Status:** ❌ **NOT STARTED**
**Priority:** **HIGH** (Fix Soon)

## The Problem

**File:** `src/apps/core/services/osiris.py:433-456`

The `_parse_person_page` function returns incomplete data - it does NOT extract faculty/organization information from the people page:

```python
def _parse_person_page(soup: bs4.BeautifulSoup, url: str, input_name: str) -> dict:
    data = {
        "input_name": input_name,
        "people_page_url": url,
        "main_name": None,
        "email": None,
        "faculty_abbrev": None,  # ❌ to be extracted - NEVER POPULATED!
    }

    # Name (H1)
    if h1 := soup.find("h1"):
        data["main_name"] = h1.get_text(strip=True)

    # Email
    if email_link := soup.select_one("a[href^='mailto:']"):
        data["email"] = email_link.get_text(strip=True)

    # Org / Faculty info
    # Usually in sidebar or header. Legacy extracted 'organization'
    # Let's try to find organization info.
    # .org-unit-link or similar?
    # Simple heuristic to extract faculty from organization hierarchy if present

    return data  # ❌ Returns WITHOUT faculty_abbrev populated!
```

**Impact:**
- Person records lack faculty association
- Faculty-based filtering doesn't work
- Cannot properly attribute persons to faculties
- Data incomplete for reporting

## Legacy Code Reference

The legacy implementation in `ea-cli/easy_access/enrichment/osiris.py` (lines 990-1019) has a complete, working implementation:

```python
# Organisation parsing
orgs: list[dict] = []
faculty_abbr = ""
faculty_name = ""
org_containers = detail_soup.find_all(class_="widget-linklist--smallicons")
if org_containers:
    container = org_containers[0]
    if isinstance(container, Tag):
        for org_tag in container.find_all(class_="widget-linklist__text"):
            if not isinstance(org_tag, Tag):
                continue
            text_content = org_tag.string
            if not text_content or "(" not in text_content:
                continue
            try:
                org_name = text_content.split("(")[0].strip()
                org_abbr = text_content.split("(")[1].split(")")[0].strip()
                if org_abbr in ["BMS", "ET", "EEMCS", "ITC", "TNW"]:
                    faculty_name = org_name
                    faculty_abbr = org_abbr
                else:
                    orgs.append({"name": org_name, "abbr": org_abbr})
            except Exception as exc:
                logger.debug(f"Org parse error for '{text_content}': {exc}")

if faculty_abbr and faculty_name:
    orgs.insert(0, {"name": faculty_name, "abbr": faculty_abbr})
    for org in orgs[1:]:
        if faculty_abbr in org.get("abbr", ""):
            org["abbr"] = org["abbr"].replace(f"-{faculty_abbr}", "")

person_data = {
    "input_name": person_name,
    "main_name": main_name,
    "match_confidence": best["ratio"],
    "first_name": " ".join(other_names),
    "email": email,
    "orgs": orgs,
    "courses": courses,
    "programmes": programmes,
    "faculty": faculty_abbr,  # ✅ PROPERLY EXTRACTED
    "people_page_url": detail_url,
}
```

**Key differences:**
1. Legacy code uses `class_="widget-linklist--smallicons"` to find org containers
2. Parses org name as `text_content.split("(")[0].strip()`
3. Parses org abbreviation as `text_content.split("(")[1].split(")")[0].strip()`
4. Checks for faculty abbreviations: `["BMS", "ET", "EEMCS", "ITC", "TNW"]`
5. Returns `faculty` field with the faculty abbreviation

## Implementation Steps

### Step 1: Add Faculty Constants

**File:** `src/apps/core/services/osiris.py`

**Add faculty abbreviations constant:**

```python
# Faculty abbreviations at University of Twente
FACULTY_ABBREVS = ["BMS", "ET", "EEMCS", "ITC", "TNW"]
```

### Step 2: Fix _parse_person_page Function

**File:** `src/apps/core/services/osiris.py:433-456`

**Replace the incomplete implementation with the working logic from legacy:**

```python
def _parse_person_page(soup: bs4.BeautifulSoup, url: str, input_name: str) -> dict:
    """
    Parse person data from people.utwente.nl profile page.

    Extracts:
    - main_name (from H1)
    - email (from mailto: links)
    - faculty_abbrev (from organization list)
    - organizations (list of orgs with name and abbreviation)

    Based on working implementation from:
    ea-cli/easy_access/enrichment/osiris.py:fetch_person_data
    """
    data = {
        "input_name": input_name,
        "people_page_url": url,
        "main_name": None,
        "email": None,
        "faculty_abbrev": None,
        "organizations": [],  # NEW: List of organizations
    }

    # Name (H1)
    h1 = soup.find("h1", class_="pageheader__title")
    if h1:
        data["main_name"] = h1.get_text(strip=True)

    # Email
    for a in soup.find_all("a"):
        if isinstance(a, bs4.Tag):
            href = a.get("href")
            if href and isinstance(href, str) and href.startswith("mailto:"):
                data["email"] = href.replace("mailto:", "")
                break

    # Organization parsing - from legacy implementation
    # Reference: ea-cli/easy_access/enrichment/osiris.py:990-1019
    orgs = []
    faculty_abbr = ""
    faculty_name = ""

    org_containers = soup.find_all(class_="widget-linklist--smallicons")
    if org_containers:
        container = org_containers[0]
        if isinstance(container, bs4.Tag):
            for org_tag in container.find_all(class_="widget-linklist__text"):
                if not isinstance(org_tag, bs4.Tag):
                    continue
                text_content = org_tag.string
                if not text_content or "(" not in text_content:
                    continue
                try:
                    # Format: "Organization Name (ABBR)"
                    org_name = text_content.split("(")[0].strip()
                    org_abbr = text_content.split("(")[1].split(")")[0].strip()

                    # Check if this is a faculty
                    if org_abbr in FACULTY_ABBREVS:
                        faculty_name = org_name
                        faculty_abbr = org_abbr
                    else:
                        orgs.append({"name": org_name, "abbr": org_abbr})
                except Exception as exc:
                    logger.debug(f"Org parse error for '{text_content}': {exc}")

    # Add faculty as first organization if found
    if faculty_abbr and faculty_name:
        orgs.insert(0, {"name": faculty_name, "abbr": faculty_abbr})
        # Clean up faculty suffix from other orgs
        for org in orgs[1:]:
            if faculty_abbr in org.get("abbr", ""):
                org["abbr"] = org["abbr"].replace(f"-{faculty_abbr}", "")

    # Populate data
    data["faculty_abbrev"] = faculty_abbr if faculty_abbr else None
    data["organizations"] = orgs

    return data
```

### Step 3: Update Person Model (if needed)

**Check if Person model has faculty field:**

**File:** `src/apps/core/models.py`

**Person model should have:**

```python
class Person(TimestampedModel):
    input_name = models.CharField(max_length=2048, db_index=True)
    main_name = models.CharField(max_length=2048)
    email = models.EmailField(max_length=255, null=True, blank=True)
    people_page_url = models.URLField(max_length=2048, null=True, blank=True)

    # Faculty association
    faculty = models.ForeignKey(
        'Faculty',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='persons',
        db_index=True
    )

    # Store raw faculty abbrev from enrichment
    faculty_abbrev = models.CharField(max_length=50, null=True, blank=True, db_index=True)

    # Additional organizations (JSON)
    organizations = models.JSONField(default=list, null=True, blank=True)

    class Meta:
        verbose_name = "Person"
        verbose_name_plural = "People"
        ordering = ["main_name"]
        indexes = [
            models.Index(fields=["input_name"], name="core_person_input_name_idx"),
            models.Index(fields=["main_name"], name="core_person_main_name_idx"),
            models.Index(fields=["faculty_abbrev"], name="core_person_faculty_idx"),
        ]
```

**If faculty_abbrev field doesn't exist, create migration:**

```bash
uv run python src/manage.py makemigrations core --name add_person_faculty_fields
```

### Step 4: Update Person Persistence Logic

**File:** `src/apps/core/services/osiris.py:567-575`

**Update person creation to include faculty:**

```python
# Persist Persons
for name, p_data in persons_data.items():
    # Look up faculty from abbreviation
    faculty = None
    faculty_abbrev = p_data.get("faculty_abbrev")
    if faculty_abbrev:
        try:
            faculty = await Faculty.objects.aget(abbreviation=faculty_abbrev)
        except Faculty.DoesNotExist:
            logger.warning(f"Faculty not found for abbreviation: {faculty_abbrev}")

    await Person.objects.aupdate_or_create(
        input_name=name,
        defaults={
            "main_name": p_data.get("main_name"),
            "email": p_data.get("email"),
            "people_page_url": p_data.get("people_page_url"),
            "faculty_abbrev": p_data.get("faculty_abbrev"),
            "organizations": p_data.get("organizations", []),
            "faculty": faculty,
        },
    )
```

### Step 5: Add Tests for Faculty Extraction

**File:** `src/apps/core/tests/test_osiris_person_extraction.py` (NEW)

```python
import pytest
import bs4
from apps.core.services.osiris import _parse_person_page, FACULTY_ABBREVS


@pytest.mark.django_db
def test_faculty_extraction_from_html():
    """Test that faculty information is extracted from people page HTML."""

    # Sample HTML structure from people.utwente.nl
    html = """
    <html>
        <body>
            <h1 class="pageheader__title">John Doe</h1>
            <a href="mailto:j.doe@utwente.nl">j.doe@utwente.nl</a>

            <div class="widget-linklist--smallicons">
                <div class="widget-linklist__text">
                    Electrical Engineering, Mathematics and Computer Science (EEMCS)
                </div>
                <div class="widget-linklist__text">
                    Department of Computer Science (CS-EEMCS)
                </div>
            </div>
        </body>
    </html>
    """

    soup = bs4.BeautifulSoup(html, "html.parser")
    result = _parse_person_page(soup, "https://people.utwente.nl/jdoe", "John Doe")

    # Verify extraction
    assert result["main_name"] == "John Doe"
    assert result["email"] == "j.doe@utwente.nl"
    assert result["faculty_abbrev"] == "EEMCS"
    assert len(result["organizations"]) == 2
    assert result["organizations"][0]["name"] == "Electrical Engineering, Mathematics and Computer Science"
    assert result["organizations"][0]["abbr"] == "EEMCS"


def test_faculty_abbreviations():
    """Verify faculty abbreviations constant."""
    assert "EEMCS" in FACULTY_ABBREVS
    assert "TNW" in FACULTY_ABBREVS
    assert "BMS" in FACULTY_ABBREVS
    assert "ET" in FACULTY_ABBREVS
    assert "ITC" in FACULTY_ABBREVS


@pytest.mark.django_db
def test_no_faculty_in_html():
    """Test handling when no faculty info is present."""

    html = """
    <html>
        <body>
            <h1 class="pageheader__title">Jane Smith</h1>
            <a href="mailto:jane@example.com">jane@example.com</a>
        </body>
    </html>
    """

    soup = bs4.BeautifulSoup(html, "html.parser")
    result = _parse_person_page(soup, "https://people.utwente.nl/jsmith", "Jane Smith")

    # Should still parse other fields
    assert result["main_name"] == "Jane Smith"
    assert result["email"] == "jane@example.com"
    assert result["faculty_abbrev"] is None
    assert result["organizations"] == []
```

### Step 6: Test with Real Data

**Create test script:**

**File:** `scripts/test_person_extraction.py` (NEW)

```python
"""
Test person extraction with real data from people.utwente.nl
"""
import asyncio
import httpx
import bs4
from apps.core.services.osiris import _parse_person_page


async def test_real_person():
    """Test extraction from a real person page."""

    # Test with a known UT person page
    test_url = "https://people.utwente.nl/j.doe@example.com"

    async with httpx.AsyncClient() as client:
        resp = await client.get(test_url, follow_redirects=True)
        if resp.status_code != 200:
            print(f"Failed to fetch: {resp.status_code}")
            return

        soup = bs4.BeautifulSoup(resp.text, "html.parser")
        result = _parse_person_page(soup, test_url, "Test Person")

        print(f"Name: {result.get('main_name')}")
        print(f"Email: {result.get('email')}")
        print(f"Faculty: {result.get('faculty_abbrev')}")
        print(f"Organizations: {result.get('organizations')}")

        # Verify faculty was extracted
        assert result.get("faculty_abbrev"), "Faculty should be extracted"
        assert len(result.get("organizations", [])) > 0, "Should have at least one organization"


if __name__ == "__main__":
    asyncio.run(test_real_person())
```

**Run test:**

```bash
uv run python scripts/test_person_extraction.py
```

## Testing

### 1. Unit Tests

```bash
# Run person extraction tests
uv run pytest src/apps/core/tests/test_osiris_person_extraction.py -v
```

### 2. Integration Test with Real Data

```bash
# Test with real people pages
uv run python scripts/test_person_extraction.py
```

### 3. Full Enrichment Test

```bash
# Run enrichment and verify faculty data is populated
uv run python src/manage.py shell

from apps.core.services.osiris import enrich_async
from apps.core.models import Person

# Run enrichment
await enrich_async()

# Check if persons have faculty
async for p in Person.objects.all()[:10]:
    print(f"{p.main_name}: faculty={p.faculty_abbrev}")
```

## Success Criteria

- [ ] `_parse_person_page` extracts faculty_abbrev from HTML
- [ ] `_parse_person_page` extracts organizations list
- [ ] Person model has faculty_abbrev field (or migration created)
- [ ] Person persistence logic saves faculty_abbrev
- [ ] Person persistence logic links to Faculty object
- [ ] Unit tests pass (test_faculty_extraction_from_html)
- [ ] Integration test with real data works
- [ ] Existing persons can be re-enriched to get faculty data
- [ ] Faculty-based filtering works in UI

## Files Modified

- `src/apps/core/services/osiris.py` - Fix _parse_person_page function
- `src/apps/core/models.py` - Add faculty_abbrev field to Person (if needed)
- `src/apps/core/tests/test_osiris_person_extraction.py` - NEW: Tests
- `scripts/test_person_extraction.py` - NEW: Integration test script

## Migration Required

If Person model doesn't have `faculty_abbrev` and `organizations` fields:

```bash
uv run python src/manage.py makemigrations core --name add_person_faculty_fields
uv run python src/manage.py migrate
```

## Related Tasks

- **Task 15:** Transaction Management (data integrity)
- **Task 13:** Test Coverage Expansion (add more enrichment tests)

## Benefits

1. **Complete data** - Person records have faculty associations
2. **Faculty filtering** - UI can filter by faculty properly
3. **Data quality** - Enrichment completes all intended fields
4. **Legacy parity** - Matches working implementation from legacy code

## Legacy Code Reference

**Working implementation:** `ea-cli/easy_access/enrichment/osiris.py:990-1019`
**Function:** `fetch_person_data` -> Organization parsing section
**Key patterns:**
- Uses `class_="widget-linklist--smallicons"` for org containers
- Parses format: "Organization Name (ABBR)"
- Checks against `FACULTY_ABBREVS` list
- Returns `faculty` field in person_data dict

---

**Next Task:** [Task 19: API & Service Layer Consistency](19-api-service-layer.md)
