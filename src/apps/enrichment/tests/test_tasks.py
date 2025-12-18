import pytest
from unittest.mock import AsyncMock, patch
from django.utils import timezone
from apps.core.models import CopyrightItem, Course, Person, CourseEmployee, EnrichmentStatus, Faculty
from apps.enrichment.tasks import enrich_item

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_enrich_item_persistence():
    # Setup: Create a test item
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="EEMCS",
        defaults={
            "name": "EEMCS",
            "hierarchy_level": 1,
            "full_abbreviation": "UT-EEMCS"
        }
    )
    item, _ = await CopyrightItem.objects.aget_or_create(
        material_id=12345,
        defaults={
            "course_code": "191154340",
            "faculty": faculty
        }
    )

    # Mock data
    mock_course_info = {
        "name": "Gasdynamics",
        "short_name": "GD",
        "programme": "Mechanical Engineering",
        "faculty_abbr": "EEMCS",
        "internal_id": "116098",
        "year": "2024",
        "teachers": ["Augustijn, D.C.M."],
        "contacts": ["Augustijn, D.C.M."]
    }

    mock_person_data = {
        "main_name": "Augustijn, D.C.M. (Denie)",
        "email": "d.c.m.augustijn@utwente.nl",
        "people_page_url": "https://people.utwente.nl/d.c.m.augustijn"
    }

    # Patch the scraper service
    with patch("apps.enrichment.tasks.OsirisScraperService") as MockScraper:
        scraper_instance = MockScraper.return_value
        scraper_instance.__aenter__.return_value = scraper_instance
        scraper_instance.fetch_course_details = AsyncMock(return_value=mock_course_info)
        scraper_instance.fetch_person_data = AsyncMock(return_value=mock_person_data)

        # Patch PDF services to avoid actual network/system calls
        with patch("apps.enrichment.tasks.download_undownloaded_pdfs", AsyncMock()), \
             patch("apps.enrichment.tasks.parse_pdfs", AsyncMock()):

            # Execute
            await enrich_item(12345)

    # Verify Course persistence
    await item.arefresh_from_db()
    print(f"Status: {item.enrichment_status}")
    assert item.enrichment_status == EnrichmentStatus.COMPLETED
    print(f"Course exists: {await Course.objects.filter(cursuscode=191154340).aexists()}")
    assert await Course.objects.filter(cursuscode=191154340).aexists()
    course = await Course.objects.aget(cursuscode=191154340)
    print(f"Course name: {course.name}, Internal ID: {course.internal_id}")
    assert course.name == "Gasdynamics"
    assert course.internal_id == 116098 # models used BigInt, string "116098" converts to int

    # Verify Item-Course link
    print(f"Item-Course link exists: {await item.courses.filter(cursuscode=191154340).aexists()}")
    assert await item.courses.filter(cursuscode=191154340).aexists()

    # Verify Person persistence
    print(f"Person Augustijn exists: {await Person.objects.filter(input_name='Augustijn, D.C.M.').aexists()}")
    assert await Person.objects.filter(input_name="Augustijn, D.C.M.").aexists()
    person = await Person.objects.aget(input_name="Augustijn, D.C.M.")
    print(f"Person email: {person.email}, Verified: {person.is_verified}")
    assert person.email == "d.c.m.augustijn@utwente.nl"
    assert person.is_verified is True

    # Verify CourseEmployee link
    print(f"CourseEmployee link exists: {await CourseEmployee.objects.filter(course=course, person=person).aexists()}")
    assert await CourseEmployee.objects.filter(course=course, person=person).aexists()
    employee = await CourseEmployee.objects.aget(course=course, person=person)
    print(f"Role: {employee.role}")
    assert employee.role == "contacts"
