import polars as pl
import pytest

from apps.core.models import CopyrightItem, Course, CourseEmployee, Faculty, Person
from apps.ingest.services.export import ExportService


@pytest.mark.django_db(transaction=True)
def test_export_enrichment_data():
    # Setup
    faculty, _ = Faculty.objects.get_or_create(
        abbreviation="EEMCS-ENRICH",
        defaults={
            "name": "EEMCS",
            "hierarchy_level": 1,
            "full_abbreviation": "UT-EEMCS-ENRICH",
        },
    )
    item = CopyrightItem.objects.create(
        material_id=123456789,  # Unique ID
        course_code="191154340-Unique",
        faculty=faculty,
        title="Test Item Unique",
    )

    course, _ = Course.objects.get_or_create(
        cursuscode=19115434099, defaults={"name": "Gasdynamics Unique", "year": 2024}
    )
    item.courses.add(course)

    person, _ = Person.objects.get_or_create(
        input_name="Augustijn-Unique-2",
        defaults={
            "main_name": "Denie Augustijn Unique",
            "email": "d.augustijn.unique@utwente.nl",
        },
    )

    CourseEmployee.objects.get_or_create(
        course=course, person=person, defaults={"role": "contacts"}
    )

    # Execute export for the faculty
    service = ExportService()
    df = service._fetch_faculty_dataframe(faculty)

    # Verify
    assert isinstance(df, pl.DataFrame)
    assert df.height == 1

    row = df.to_dicts()[0]
    assert row["cursuscodes"] == "19115434099"
    assert row["course_names"] == "Gasdynamics Unique"
    assert row["course_contacts_names"] == "Denie Augustijn Unique"
    assert row["course_contacts_emails"] == "d.augustijn.unique@utwente.nl"


@pytest.mark.django_db(transaction=True)
def test_export_organization_data():
    from apps.core.models import Organization

    # Setup
    faculty, _ = Faculty.objects.get_or_create(
        abbreviation="EEMCS",
        defaults={
            "name": "EEMCS",
            "hierarchy_level": 1,
            "full_abbreviation": "UT-EEMCS",
        },
    )
    item = CopyrightItem.objects.create(
        material_id=789012,
        course_code="202200096",
        faculty=faculty,
        title="Test Item Org",
    )

    course, _ = Course.objects.get_or_create(
        cursuscode=202200096, defaults={"name": "Test Course", "year": 2024}
    )
    item.courses.add(course)

    person, _ = Person.objects.get_or_create(
        input_name="Test Person",
        defaults={
            "main_name": "Test Person",
            "email": "test@utwente.nl",
            "faculty": faculty,
        },
    )

    # Create and link organizations
    ut, _ = Organization.objects.get_or_create(
        abbreviation="UT",
        defaults={
            "name": "University of Twente",
            "hierarchy_level": 0,
            "full_abbreviation": "UT",
        },
    )
    ps, _ = Organization.objects.get_or_create(
        abbreviation="EEMCS-PS",
        defaults={
            "name": "Pervasive Systems",
            "hierarchy_level": 2,
            "full_abbreviation": "UT-EEMCS-EEMCS-PS",
            "parent": faculty,
        },
    )
    person.orgs.add(ut, faculty, ps)

    CourseEmployee.objects.get_or_create(
        course=course, person=person, defaults={"role": "contacts"}
    )

    # Execute export
    service = ExportService()
    df = service._fetch_faculty_dataframe(faculty)

    # Verify
    row = df.to_dicts()[0]
    assert row["course_contacts_organizations"] == "UT | UT-EEMCS | UT-EEMCS-EEMCS-PS"
