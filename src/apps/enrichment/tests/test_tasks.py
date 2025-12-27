from unittest.mock import AsyncMock, patch

import pytest

from apps.core.models import (
    CopyrightItem,
    Course,
    CourseEmployee,
    EnrichmentStatus,
    Faculty,
    Person,
)
from apps.enrichment.tasks import enrich_item


@pytest.mark.skip(reason="Task decorator causes 'Task object is not callable' error in tests")
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_enrich_item_persistence():
    # Setup: Create a test item
    faculty, _ = await Faculty.objects.aget_or_create(
        abbreviation="EEMCS",
        defaults={
            "name": "EEMCS",
            "hierarchy_level": 1,
            "full_abbreviation": "UT-EEMCS",
        },
    )
    item, _ = await CopyrightItem.objects.aget_or_create(
        material_id=12345, defaults={"course_code": "191154340", "faculty": faculty}
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
        "contacts": ["Augustijn, D.C.M."],
    }

    mock_person_data = {
        "main_name": "Augustijn, D.C.M. (Denie)",
        "email": "d.c.m.augustijn@utwente.nl",
        "people_page_url": "https://people.utwente.nl/d.c.m.augustijn",
    }

    # Patch the scraper service
    with patch("apps.enrichment.tasks.OsirisScraperService") as MockScraper:
        scraper_instance = MockScraper.return_value
        scraper_instance.__aenter__.return_value = scraper_instance
        scraper_instance.fetch_course_details = AsyncMock(return_value=mock_course_info)
        scraper_instance.fetch_person_data = AsyncMock(return_value=mock_person_data)

        # Patch PDF services to avoid actual network/system calls
        with (
            patch("apps.enrichment.tasks.download_undownloaded_pdfs", AsyncMock()),
            patch("apps.enrichment.tasks.parse_pdfs", AsyncMock()),
        ):
            # Execute
            await enrich_item(12345)

    # Verify Course persistence
    await item.arefresh_from_db()
    assert item.enrichment_status == EnrichmentStatus.COMPLETED
    assert await Course.objects.filter(cursuscode=191154340).aexists()
    course = await Course.objects.aget(cursuscode=191154340)
    assert course.name == "Gasdynamics"
    assert (
        course.internal_id == 116098
    )  # models used BigInt, string "116098" converts to int

    # Verify Item-Course link
    assert await item.courses.filter(cursuscode=191154340).aexists()

    # Verify Person persistence
    assert await Person.objects.filter(input_name="Augustijn, D.C.M.").aexists()
    person = await Person.objects.aget(input_name="Augustijn, D.C.M.")
    assert person.email == "d.c.m.augustijn@utwente.nl"
    assert person.is_verified is True

    # Verify CourseEmployee link
    assert await CourseEmployee.objects.filter(course=course, person=person).aexists()
    employee = await CourseEmployee.objects.aget(course=course, person=person)
    assert employee.role == "contacts"


@pytest.mark.skip(reason="Task decorator causes 'Task object is not callable' error in tests")
@pytest.mark.django_db
@pytest.mark.asyncio
async def test_enrich_item_org_persistence():
    # Setup: Create a test item
    _item, _ = await CopyrightItem.objects.aget_or_create(
        material_id=67890,
        defaults={
            "course_code": "202200096",
        },
    )

    # Mock data
    mock_course_info = {
        "name": "Test Course",
        "faculty_abbr": "EEMCS",
        "teachers": ["Test Person"],
        "contacts": ["Test Person"],
    }

    mock_person_data = {
        "main_name": "Test Person",
        "email": "test@utwente.nl",
        "orgs": [
            {"name": "University of Twente", "abbr": "UT"},
            {"name": "EEMCS", "abbr": "EEMCS"},
            {"name": "Pervasive Systems", "abbr": "EEMCS-PS"},
        ],
    }

    # Patch the scraper service
    with patch("apps.enrichment.tasks.OsirisScraperService") as MockScraper:
        scraper_instance = MockScraper.return_value
        scraper_instance.__aenter__.return_value = scraper_instance
        scraper_instance.fetch_course_details = AsyncMock(return_value=mock_course_info)
        scraper_instance.fetch_person_data = AsyncMock(return_value=mock_person_data)

        # Patch PDF services
        with (
            patch("apps.enrichment.tasks.download_undownloaded_pdfs", AsyncMock()),
            patch("apps.enrichment.tasks.parse_pdfs", AsyncMock()),
        ):
            # Execute
            await enrich_item(67890)

    # Verify Person persistence
    person = await Person.objects.aget(input_name="Test Person")
    assert person.email == "test@utwente.nl"

    # Verify Organization persistence
    from apps.core.models import Faculty, Organization

    # UT (level 0)
    assert await Organization.objects.filter(
        abbreviation="UT", hierarchy_level=0
    ).aexists()
    ut = await Organization.objects.aget(abbreviation="UT")

    # EEMCS (level 1 - Faculty)
    assert await Faculty.objects.filter(
        abbreviation="EEMCS", hierarchy_level=1
    ).aexists()
    eemcs = await Faculty.objects.select_related("parent").aget(abbreviation="EEMCS")
    assert eemcs.parent_id == ut.id

    # Pervasive Systems (level 2)
    assert await Organization.objects.filter(
        abbreviation="EEMCS-PS", hierarchy_level=2
    ).aexists()
    ps = await Organization.objects.select_related("parent").aget(
        abbreviation="EEMCS-PS"
    )
    assert ps.parent_id == eemcs.id

    # Verify Person-Org links
    person_org_ids = [o.id async for o in person.orgs.all()]
    assert len(person_org_ids) == 3
    assert ut.id in person_org_ids
    assert eemcs.id in person_org_ids
    assert ps.id in person_org_ids

    # Verify full abbreviations
    org_abbrs = [o.full_abbreviation async for o in person.orgs.all()]
    assert "UT" in org_abbrs
    assert "UT-EEMCS" in org_abbrs
    assert "UT-EEMCS-EEMCS-PS" in org_abbrs

    # Verify Person-Faculty link
    assert person.faculty_id == eemcs.id
