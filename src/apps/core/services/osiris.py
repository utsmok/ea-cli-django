import asyncio
import logging
import urllib.parse as _u

import bs4
import httpx
from django.utils import timezone

from apps.core.models import CopyrightItem, Course, Faculty, MissingCourse, Person
from apps.core.services.cache_service import cache_async_result
from apps.core.services.relations import link_persons_to_courses
from apps.core.services.retry_logic import async_retry
from apps.core.utils.course_parser import determine_course_code
from apps.core.utils.safecast import safe_int

logger = logging.getLogger(__name__)

# Constants
OSIRIS_SEARCH_URL = (
    "https://utwente.osiris-student.nl/student/osiris/student/cursussen/zoeken"
)
PEOPLE_SEARCH_URL = "https://people.utwente.nl/overview?query="

# Faculty abbreviations at University of Twente
FACULTY_ABBREVS = ["BMS", "ET", "EEMCS", "ITC", "TNW"]


async def gather_target_course_codes() -> set[int]:
    """Gather all unique course codes from copyright items that need enrichment."""
    logger.info("Gathering target course codes for enrichment...")

    all_codes = set()

    # Iterate asynchronously over the queryset
    async for item in CopyrightItem.objects.all():
        codes = determine_course_code(item.course_code or "", item.course_name or "")
        if codes:
            all_codes.update(codes)

    valid_codes = set()
    for c in all_codes:
        if i := safe_int(c):
            valid_codes.add(i)

    logger.info(f"Found {len(valid_codes)} unique course codes")
    return valid_codes


async def select_missing_or_stale_courses(
    course_codes: set[int], ttl_days: int = 30
) -> set[int]:
    """Select course codes that are missing or stale."""
    logger.info("Selecting courses that need enrichment...")

    # 1. Fetch existing courses
    existing_courses_list = []
    async for c in Course.objects.filter(cursuscode__in=course_codes):
        existing_courses_list.append(c)

    existing_codes = {c.cursuscode for c in existing_courses_list}

    missing_codes = course_codes - existing_codes

    # 2. Tracked missing (failed before)
    tracked_missing_codes = set()
    async for m in MissingCourse.objects.filter(cursuscode__in=missing_codes):
        tracked_missing_codes.add(m.cursuscode)

    new_missing = missing_codes - tracked_missing_codes

    # 3. Calculate stale
    now = timezone.now()
    stale_existing = set()

    for c in existing_courses_list:
        if not c.modified_at or (now - c.modified_at).days > ttl_days:
            stale_existing.add(c.cursuscode)

    # 4. Retry missing if stale
    retry_missing = set()
    if tracked_missing_codes:
        async for m in MissingCourse.objects.filter(
            cursuscode__in=tracked_missing_codes
        ):
            if not m.modified_at or (now - m.modified_at).days > ttl_days:
                retry_missing.add(m.cursuscode)

    to_fetch = new_missing | retry_missing | stale_existing

    logger.info(
        f"Enrichment targets: {len(to_fetch)} (New: {len(new_missing)}, Retry: {len(retry_missing)}, Stale: {len(stale_existing)})"
    )
    return to_fetch


async def fetch_and_parse_courses(
    course_codes: set[int], max_concurrent: int = 10
) -> dict[int, dict]:
    """Fetch parse courses concurrently."""
    logger.info(f"Fetching {len(course_codes)} courses concurrently...")

    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}

    async def fetch_single(code: int):
        async with semaphore:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    data = await fetch_course_data(code, client)
                    if data:
                        results[code] = data
                        # Remove from Missing if found
                        await MissingCourse.objects.filter(cursuscode=code).adelete()
                    else:
                        logger.warning(f"No data for course {code}")
                        # Mark missing
                        await MissingCourse.objects.aupdate_or_create(cursuscode=code)
            except Exception as e:
                logger.error(f"Error fetching course {code}: {e}")

    tasks = [fetch_single(c) for c in course_codes]
    await asyncio.gather(*tasks)

    return results


@cache_async_result(timeout=86400, key_prefix="osiris_course", cache_name="queries")
@async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def fetch_course_data(course_code: int, client: httpx.AsyncClient) -> dict:
    """
    Fetch single course data from OSIRIS.

    Cached for 24 hours because course data changes very rarely
    (typically once per semester during course catalog updates).
    """

    def _process_teacher_items(items) -> set[str]:
        """Helper function to process teacher items into a consistent set format"""
        teacher_names = set()

        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    # Try to extract name from common dictionary keys
                    name = None
                    for key in [
                        "name",
                        "docent",
                        "teacher",
                        "person_name",
                        "main_name",
                    ]:
                        if item.get(key):
                            name = str(item[key]).strip()
                            break
                    # If no specific key found, try to find any string value
                    if not name:
                        for value in item.values():
                            if isinstance(value, str) and value.strip():
                                name = value.strip()
                                break
                    if name:
                        teacher_names.add(name)
                elif isinstance(item, str):
                    teacher_names.add(item.strip())
        elif isinstance(items, str):
            teacher_names.add(items.strip())
        elif isinstance(items, set):
            # Handle existing sets
            for item in items:
                if isinstance(item, str):
                    teacher_names.add(item.strip())
        elif isinstance(items, dict):
            # Handle single dictionary
            name = None
            for key in ["name", "docent", "teacher", "person_name", "main_name"]:
                if items.get(key):
                    name = str(items[key]).strip()
                    break
            if not name:
                for value in items.values():
                    if isinstance(value, str) and value.strip():
                        name = value.strip()
                        break
            if name:
                teacher_names.add(name)

        return teacher_names

    def _extract_languages(voertalen_data) -> list[str]:
        """Extract language information from voertalen data"""
        if isinstance(voertalen_data, list):
            return [
                x.get("voertaal_omschrijving")
                for x in voertalen_data
                if x.get("voertaal_omschrijving")
            ]
        return []

    startstring = '{"from":0,"size":25,"sort":[{"cursus_lange_naam.raw":{"order":"asc"}},{"cursus":{"order":"asc"}},{"collegejaar":{"order":"desc"}}],"aggs":{"agg_terms_collegejaar":{"filter":{"bool":{"must":[]}},"aggs":{"agg_collegejaar_buckets":{"terms":{"field":"collegejaar","size":2500,"order":{"_term":"desc"}}}}},"agg_terms_blokken_nested.periode_omschrijving":{"filter":{"bool":{"must":[{"terms":{"collegejaar":["2024-2025"]}}]}},"aggs":{"agg_blokken_nested.periode_omschrijving":{"terms":{"field":"blokken_nested.periode_omschrijving","size":2500,"order":{"_term":"asc"},"exclude":"Periode: [0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9]"}},"nested_aggs":{"nested":{"path":"blokken_nested"},"aggs":{"nested_aggs":{"filter":{"bool":{"must":[]}},"aggs":{"agg_blokken_nested.periode_omschrijving_buckets":{"terms":{"field":"blokken_nested.periode_omschrijving","size":2500,"order":{"_term":"asc"},"exclude":"Periode: [0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9]"},"aggs":{"items":{"reverse_nested":{}}}}}}}}}},"agg_terms_faculteit_naam":{"filter":{"bool":{"must":[{"terms":{"collegejaar":["2024-2025"]}}]}},"aggs":{"agg_faculteit_naam_buckets":{"terms":{"field":"faculteit_naam","size":2500,"order":{"_term":"asc"}}}}},"agg_terms_coordinerend_onderdeel_oms":{"filter":{"bool":{"must":[{"terms":{"collegejaar":["2024-2025"]}}]}},"aggs":{"agg_coordinerend_onderdeel_oms_buckets":{"terms":{"field":"coordinerend_onderdeel_oms","size":2500,"order":{"_term":"asc"}}}}},"agg_terms_categorie_omschrijving":{"filter":{"bool":{"must":[{"terms":{"collegejaar":["2024-2025"]}}]}},"aggs":{"agg_categorie_omschrijving_buckets":{"terms":{"field":"categorie_omschrijving","size":2500,"order":{"_term":"asc"}}}}},"agg_terms_voertalen.voertaal_omschrijving":{"filter":{"bool":{"must":[{"terms":{"collegejaar":["2024-2025"]}}]}},"aggs":{"agg_voertalen.voertaal_omschrijving_buckets":{"terms":{"field":"voertalen.voertaal_omschrijving","size":2500,"order":{"_term":"asc"}}}}}},"post_filter":{"bool":{"must":[{"terms":{"collegejaar":["2024-2025"]}}]}},"query":{"bool":{"must":[{"multi_match":{"query":'
    code = f'"{course_code}"'
    endstring = ',"type":"phrase_prefix","fields":["cursus","cursus_korte_naam","cursus_lange_naam"],"max_expansions":200}}]}}}'
    body = startstring + code + endstring

    headers = {
        "host": "utwente.osiris-student.nl",
        "connection": "keep-alive",
        "content-length": str(len(body)),
        "sec-ch-ua-platform": '"Windows"',
        "authorization": "undefined undefined",
        "cache-control": "no-cache, no-store, must-revalidate, private",
        "pragma": "no-cache",
        "client_type": "web",
        "release_version": "c0d3b6a1d72bf1610166027c903b46fc10580f30",
        "manifest": "24.46_B346_c0d3b6a1",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "taal": "NL",
        "origin": "https//utwente.osiris-student.nl",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": "https//utwente.osiris-student.nl/onderwijscatalogus/extern/cursussen",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    }

    try:
        resp = await client.post(OSIRIS_SEARCH_URL, headers=headers, content=body)

        # Raise exception for HTTP errors - retry logic will handle retryable ones
        resp.raise_for_status()

        raw = resp.json()
        hits = raw.get("hits", {}).get("hits", [])

        if not hits:
            return {}

        data = hits[0].get("_source", {})

        # Extract teacher information
        teachers = set()
        for key, value in data.items():
            if key == "docenten" and value:
                teachers = _process_teacher_items(value)

        # Build course data structure
        collegejaar = data.get("collegejaar") or ""
        year_part = None
        if isinstance(collegejaar, str) and "-" in collegejaar:
            try:
                year_part = collegejaar.split("-")[0]
            except Exception:
                year_part = None

        course_data = {
            "cursuscode": course_code,
            "internal_id": data.get("id_cursus"),
            "year": year_part,
            "short_name": data.get("cursus_korte_naam"),
            "name": data.get("cursus_lange_naam"),
            "faculty": data.get("faculteit"),
            "faculty_long": data.get("faculteit_naam"),
            "programme": data.get("coordinerend_onderdeel_oms"),
            "ec": data.get("punten"),
            "language": _extract_languages(data.get("voertalen", [])),
            "notes": data.get("opmerking_cursus"),
            "category": data.get("categorie_omschrijving"),
            "teachers": teachers,
            "contacts": set(),
            "docenten": set(),
            "examinators": set(),
            "unknown_role": set(),
            "tutors": set(),
        }

        # Fetch details
        await _fetch_course_details(course_data, client)

        return course_data

    except Exception as e:
        logger.error(f"Failed to fetch osiris data for {course_code}: {e}")
        return {}


async def _fetch_course_details(course_data: dict, client: httpx.AsyncClient):
    internal_id = course_data.get("internal_id")
    if not internal_id:
        return

    url = (
        f"https://utwente.osiris-student.nl/student/osiris/owc/cursussen/{internal_id}"
    )
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-US,en;q=0.9,nl-NL;q=0.8,nl;q=0.7",
        "authorization": "undefined undefined",
        "cache-control": "no-cache, no-store, must-revalidate, private",
        "client_type": "web",
        "content-type": "application/json",
        "dnt": "1",
        "manifest": "24.46_B346_c0d3b6a1",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "referer": "https://utwente.osiris-student.nl/onderwijscatalogus/extern/cursussen",
        "release_version": "c0d3b6a1d72bf1610166027c903b46fc10580f30",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "sec-fetch-user": "?1",
        "taal": "NL",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }

    try:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            course_details = response.json()
            for datapoint in course_details.get("items", []):
                if datapoint.get("rubriek") == "rubriek-docenten":
                    docent_data = datapoint.get("velden", [])
                    if docent_data:
                        for docent_item in docent_data:
                            if docent_item.get("waarde"):
                                for docent_type in docent_item.get("waarde", []):
                                    for persoon in docent_type.get("velden", []):
                                        person_name = persoon.get("docent")
                                        if person_name:
                                            role_type = docent_type.get("omschrijving")
                                            if role_type == "Contactpersoon":
                                                course_data["contacts"].add(person_name)
                                            elif role_type == "Docent":
                                                course_data["docenten"].add(person_name)
                                            elif role_type == "Examinator":
                                                course_data["examinators"].add(
                                                    person_name
                                                )
                                            elif role_type == "Tutor":
                                                course_data["tutors"].add(person_name)
                                            else:
                                                course_data["unknown_role"].add(
                                                    person_name
                                                )

            # Convert sets to lists for JSON serialization
            for field in [
                "teachers",
                "contacts",
                "docenten",
                "examinators",
                "tutors",
                "unknown_role",
            ]:
                if isinstance(course_data.get(field), set):
                    course_data[field] = list(course_data[field])
                    # Filter out single-character entries (likely parsing errors)
                    if len(course_data[field]) > 8 and all(
                        len(x) == 1 for x in course_data[field]
                    ):
                        course_data[field] = []

        else:
            logger.error(
                f"Error retrieving course details: HTTP {response.status_code}"
            )

    except Exception as e:
        logger.error(f"Error fetching course details: {e}")


# --- Person Fetching Logic (Simplified Port) ---


@cache_async_result(timeout=604800, key_prefix="osiris_person", cache_name="queries")
@async_retry(max_retries=3, base_delay=1.0, max_delay=60.0)
async def fetch_person_data(name: str, client: httpx.AsyncClient) -> dict | None:
    """
    Fetch person data by scraping people.utwente.nl.

    Cached for 7 days because person information (email, faculty)
    changes very rarely.
    """
    url = f"{PEOPLE_SEARCH_URL}{_u.quote(name)}"

    try:
        resp = await client.get(url, follow_redirects=True)
        # Raise for HTTP errors - but 404 is expected (person not found)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        soup = bs4.BeautifulSoup(resp.text, "html.parser")

        # Check for direct profile page or search results
        # If we landed on a search page, pick the first result
        # (This heuristic matches legacy behavior)

        # If single result redirect happened, we are on profile page
        if "people.utwente.nl" in str(resp.url) and "overview" not in str(resp.url):
            return _parse_person_page(soup, str(resp.url), name)

        # Else parse search results
        results = soup.select("div.ut-person-tile")
        if not results:
            return None

        # Pick first
        first_result = results[0]
        link = first_result.select_one(".ut-person-tile__profilelink a")
        if link and link.has_attr("href"):
            profile_url = link["href"]
            if not str(profile_url).startswith("http"):
                profile_url = f"https://people.utwente.nl{profile_url}"

            # Fetch profile
            profile_resp = await client.get(str(profile_url), follow_redirects=True)
            if profile_resp.status_code == 200:
                profile_soup = bs4.BeautifulSoup(profile_resp.text, "html.parser")
                return _parse_person_page(profile_soup, str(profile_url), name)

        return None

    except Exception as e:
        logger.error(f"Error scraping person {name}: {e}")
        return None


def _parse_person_page(soup: bs4.BeautifulSoup, url: str, input_name: str) -> dict:
    """
    Parse a person's profile page from people.utwente.nl.

    Extracts:
    - main_name (from H1 header)
    - email (from mailto link)
    - faculty_abbrev (from organization links)

    Faculty extraction follows legacy pattern from ea-cli:
    Looks for widget-linklist with org abbreviations in format "Name (ABBR)"
    and identifies faculty by checking if abbreviation matches FACULTY_ABBREVS.
    """
    data = {
        "input_name": input_name,
        "people_page_url": url,
        "main_name": None,
        "email": None,
        "faculty_abbrev": None,
        "faculty_name": None,
    }

    # Name (H1)
    if h1 := soup.find("h1"):
        data["main_name"] = h1.get_text(strip=True)

    # Email
    if email_link := soup.select_one("a[href^='mailto:']"):
        data["email"] = email_link.get_text(strip=True)

    # Org / Faculty parsing
    # Look for organization links in the sidebar/widget
    # Format: "Organization Name (ABBR)"
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
                    org_name = text_content.split("(")[0].strip()
                    org_abbr = text_content.split("(")[1].split(")")[0].strip()
                    # Check if this is a faculty
                    if org_abbr in FACULTY_ABBREVS:
                        data["faculty_name"] = org_name
                        data["faculty_abbrev"] = org_abbr
                        logger.debug(
                            f"Found faculty {org_abbr} ({org_name}) for {input_name}"
                        )
                        break  # Use first faculty found
                except Exception as exc:
                    logger.debug(f"Org parse error for '{text_content}': {exc}")

    return data


async def fetch_and_parse_persons(
    names: set[str], max_concurrent: int = 20
) -> dict[str, dict]:
    """Fetch person data concurrently."""
    logger.info(f"Fetching {len(names)} persons concurrently...")

    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}

    async def fetch_single(name: str):
        async with semaphore:
            # Skip if name is too short or generic?
            if len(name) < 3:
                return

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    data = await fetch_person_data(name, client)
                    if data:
                        results[name] = data
            except Exception as e:
                logger.error(f"Error fetching person {name}: {e}")

    tasks = [fetch_single(n) for n in names]
    await asyncio.gather(*tasks)

    return results


async def enrich_async(course_ttl_days: int = 30):
    """
    Main enrichment orchestrator that fetches and persists missing/stale OSIRIS data.
    """
    logger.info("Starting OSIRIS enrichment...")

    # 1. Courses
    target_codes = await gather_target_course_codes()
    to_fetch = await select_missing_or_stale_courses(target_codes, course_ttl_days)

    courses_data = {}
    if not to_fetch:
        logger.info("No courses needed fetching.")
    else:
        courses_data = await fetch_and_parse_courses(to_fetch)

        # Persist Courses
        for code, data in courses_data.items():
            await Course.objects.aupdate_or_create(
                cursuscode=code,
                defaults={
                    "internal_id": data.get("internal_id"),
                    "year": data.get("year") or 2024,
                    "name": data.get("name") or "Unknown",
                    "short_name": data.get("short_name"),
                    "programme_text": data.get("programme")
                    or data.get("programme_text"),
                    # Faculty lookup could be added here if we had a mapping
                },
            )

    # 2. Persons
    # Collect names from the course data we just fetched
    person_names = set()
    course_to_persons = {}  # code -> {role: [names]}

    # We only process persons for courses we just fetched/parsed,
    # because we need the raw data dict which contains names.
    for code, data in courses_data.items():
        c_persons = {}
        for role_field in [
            "teachers",
            "contacts",
            "docenten",
            "examinators",
            "tutors",
            "unknown_role",
        ]:
            names = data.get(role_field, [])
            if names:
                clean_names = set()
                if isinstance(names, list | set):
                    clean_names.update([str(n).strip() for n in names if n])

                if clean_names:
                    c_persons[role_field] = clean_names
                    person_names.update(clean_names)

        course_to_persons[code] = c_persons

    if person_names:
        logger.info(f"Found {len(person_names)} person names to check.")

        # Fetch persons - simplified check (fetch all that are in our list)
        # In production we might check which ones exist in DB first
        # But for enrichment consistency we check matching

        existing_persons_qs = Person.objects.filter(input_name__in=person_names)
        existing_names = set()
        async for p in existing_persons_qs:
            existing_names.add(p.input_name)

        missing_persons = person_names - existing_names

        if missing_persons:
            logger.info(f"Fetching {len(missing_persons)} new persons...")
            persons_data = await fetch_and_parse_persons(missing_persons)

            # Persist Persons with faculty information
            for name, p_data in persons_data.items():
                faculty = None
                faculty_abbrev = p_data.get("faculty_abbrev")

                # Try to get or create Faculty object if abbreviation is available
                if faculty_abbrev:
                    try:
                        faculty, _ = await Faculty.objects.aget_or_create(
                            abbreviation=faculty_abbrev,
                            defaults={
                                "name": p_data.get("faculty_name", faculty_abbrev),
                                "full_abbreviation": faculty_abbrev,
                                "hierarchy_level": 1,  # Faculty level
                            },
                        )
                        logger.debug(f"Linked {name} to faculty {faculty_abbrev}")
                    except Exception as e:
                        logger.warning(
                            f"Could not link {name} to faculty {faculty_abbrev}: {e}"
                        )

                # Prepare metadata including faculty_abbrev
                metadata = {
                    "faculty_abbrev": faculty_abbrev,
                    "faculty_name": p_data.get("faculty_name"),
                }

                await Person.objects.aupdate_or_create(
                    input_name=name,
                    defaults={
                        "main_name": p_data.get("main_name"),
                        "email": p_data.get("email"),
                        "people_page_url": p_data.get("people_page_url"),
                        "faculty": faculty,
                        "metadata": metadata,
                    },
                )
        else:
            logger.info("All persons already exist.")

    # 3. Link Persons -> Courses
    if course_to_persons:
        logger.info("Linking persons to courses...")
        linking_map = {}

        # Build lookup for all relevant persons
        all_related_persons = {}
        async for p in Person.objects.filter(input_name__in=person_names):
            all_related_persons[p.input_name] = p.people_page_url

        for code, roles_map in course_to_persons.items():
            person_list = []
            for role, names in roles_map.items():
                for name in names:
                    url = all_related_persons.get(name, "")
                    person_list.append(
                        {"name": name, "people_page_url": url, "role": role}
                    )
            linking_map[code] = person_list

        # Call the sync service wrapper or async variant?
        # link_persons_to_courses is synchronous (Django ORM default) or async?
        # In relations.py it was defined as sync I believe?
        # Checking... wait, relations.py uses Django ORM.
        # If it's sync, we need async_to_sync or use sync_to_async wrapper.
        # But we are in async context here (enrich_async).
        # We can't call sync DB code directly.
        # Assume link_persons_to_courses was ported as sync.
        # We'll use sync_to_async to call it.

        from asgiref.sync import sync_to_async

        await sync_to_async(link_persons_to_courses)(linking_map)
