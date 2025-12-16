import logging
from typing import List, Dict, Set, Any
from django.db import transaction
from django.db.models import Q
from apps.core.models import CopyrightItem, Course, Person, CourseEmployee
from apps.core.utils.course_parser import determine_course_code
from apps.core.utils.safecast import safe_int

logger = logging.getLogger(__name__)

def link_courses() -> None:
    """
    Link copyright items to courses based on course codes.
    """
    logger.info("Linking courses to copyright items...")

    # Process all items to ensure current links are up to date
    items = list(CopyrightItem.objects.all())

    if not items:
        logger.info("No items to process for course linking")
        return

    logger.info(f"Found {len(items)} items to consider for course links")

    # Extract all potential course codes
    item_course_map: Dict[int, List[str]] = {}
    all_course_codes: Set[Any] = set()

    for item in items:
        course_codes = determine_course_code(
            item.course_code or "", item.course_name or ""
        )
        if course_codes:
            course_codes_list = list(course_codes)
            item_course_map[item.material_id] = course_codes_list
            all_course_codes.update(course_codes_list)

    if not all_course_codes:
        logger.warning("No course codes found to link")
        return

    # Filter valid integer codes
    valid_course_codes: Set[int] = set()
    for code in all_course_codes:
        if code:
            int_code = safe_int(code)
            if int_code is not None:
                valid_course_codes.add(int_code)

    if not valid_course_codes:
        logger.warning("No valid course codes found")
        return

    # Fetch courses
    courses = list(Course.objects.filter(cursuscode__in=valid_course_codes))
    course_map = {c.cursuscode: c for c in courses}

    logger.info(f"Fetched {len(courses)} courses for {len(valid_course_codes)} course codes")

    links_added = 0

    # Batch processing with transaction
    with transaction.atomic():
        for item in items:
            item_id = item.material_id
            if item_id not in item_course_map:
                continue

            # Identify desired course objects
            desired_courses = []
            for code_str in item_course_map[item_id]:
                int_code = safe_int(code_str)
                if int_code and int_code in course_map:
                    desired_courses.append(course_map[int_code])

            if not desired_courses:
                continue

            # Check existing links (prefetching usually better, but for now simple loop)
            # Optimization: could bulk prefetch item.courses for all items
            # But let's stick to correctness first.
            existing_ids = set(item.courses.values_list('cursuscode', flat=True))

            to_add = [c for c in desired_courses if c.cursuscode not in existing_ids]

            if to_add:
                item.courses.add(*to_add)
                links_added += len(to_add)

    if links_added:
        logger.info(f"Added {links_added} course links")
    else:
        logger.info("No new course links to create")


def link_persons_to_courses(
    course_to_person_mapping: Dict[int, List[Dict[str, str]]]
) -> None:
    """
    Links persons to courses based on the provided mapping.
    """
    all_course_codes = {
        safe_int(code)
        for code in course_to_person_mapping
        if safe_int(code) is not None
    }

    if not all_course_codes:
        logger.info("No valid course codes provided for person linking")
        return

    courses = list(Course.objects.filter(cursuscode__in=all_course_codes))
    if not courses:
        logger.warning("No courses found to link")
        return

    courses_dict = {c.cursuscode: c for c in courses}

    # Fetch persons by people page URL
    all_urls = {
        x.get("people_page_url")
        for person_list in course_to_person_mapping.values()
        for x in person_list
        if x.get("people_page_url")
    }

    persons = []
    if all_urls:
        persons = list(Person.objects.filter(people_page_url__in=all_urls))

    if not persons:
        logger.warning("No persons found to link")
        return

    persons_dict = {p.people_page_url: p for p in persons}

    created_count = 0
    with transaction.atomic():
        for course_code, person_list in course_to_person_mapping.items():
            int_code = safe_int(course_code)
            if not int_code or int_code not in courses_dict:
                continue

            course = courses_dict[int_code]

            for p_entry in person_list:
                url = p_entry.get("people_page_url")
                if not url:
                    continue

                person = persons_dict.get(url)
                if not person:
                    continue

                role = p_entry.get("role")

                # Check existance
                # Using get_or_create to verify/create link
                obj, created = CourseEmployee.objects.get_or_create(
                    course=course,
                    person=person,
                    defaults={'role': role}
                )
                if created:
                    created_count += 1
                elif obj.role != role and role:
                   obj.role = role
                   obj.save()

    if created_count:
        logger.info(f"Created {created_count} course-person relations")
    else:
        logger.info("No new course-person relations created")
