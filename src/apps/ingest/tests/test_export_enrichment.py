import pytest
import polars as pl
from apps.core.models import CopyrightItem, Course, Person, CourseEmployee, Faculty
from apps.ingest.services.export import ExportService

@pytest.mark.django_db
def test_export_enrichment_data():
    # Setup
    faculty = Faculty.objects.create(
        abbreviation="EEMCS",
        name="EEMCS",
        hierarchy_level=1,
        full_abbreviation="UT-EEMCS"
    )
    item = CopyrightItem.objects.create(
        material_id=123,
        course_code="191154340",
        faculty=faculty,
        title="Test Item"
    )

    course = Course.objects.create(
        cursuscode=191154340,
        name="Gasdynamics",
        year=2024
    )
    item.courses.add(course)

    person = Person.objects.create(
        input_name="Augustijn",
        main_name="Denie Augustijn",
        email="d.augustijn@utwente.nl"
    )

    CourseEmployee.objects.create(
        course=course,
        person=person,
        role="contacts"
    )

    # Execute export for the faculty
    service = ExportService()
    df = service._fetch_faculty_dataframe(faculty)

    # Verify
    assert isinstance(df, pl.DataFrame)
    assert df.height == 1

    row = df.to_dicts()[0]
    assert row["cursuscodes"] == "191154340"
    assert row["course_names"] == "Gasdynamics"
    assert row["course_contacts_names"] == "Denie Augustijn"
    assert row["course_contacts_emails"] == "d.augustijn@utwente.nl"
