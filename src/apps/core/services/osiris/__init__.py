"""
Osiris integration package.

This package provides functionality for fetching course and person data
from the University of Twente's Osiris system.

Backwards compatible imports - all public APIs are re-exported here.
"""

from loguru import logger

from apps.core.models import Course, Faculty, Person
from apps.core.services.relations import link_persons_to_courses

# Re-export all constants
from .constants import FACULTY_ABBREVS, OSIRIS_SEARCH_URL, PEOPLE_SEARCH_URL

# Re-export all course-related functions
from .courses import (
    _fetch_course_details,
    fetch_and_parse_courses,
    fetch_course_data,
    gather_target_course_codes,
    select_missing_or_stale_courses,
)

# Re-export all person-related functions
from .persons import (
    _parse_person_page,
    fetch_and_parse_persons,
    fetch_person_data,
)

__all__ = [
    # Constants
    "OSIRIS_SEARCH_URL",
    "PEOPLE_SEARCH_URL",
    "FACULTY_ABBREVS",
    # Course functions
    "gather_target_course_codes",
    "select_missing_or_stale_courses",
    "fetch_and_parse_courses",
    "fetch_course_data",
    "_fetch_course_details",
    # Person functions
    "fetch_person_data",
    "fetch_and_parse_persons",
    "_parse_person_page",
    # Orchestrator
    "enrich_async",
]


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
