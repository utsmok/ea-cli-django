import pytest
from openpyxl import load_workbook

from apps.core.models import CopyrightItem, Faculty
from apps.ingest.services.excel_builder import ExcelBuilder


@pytest.mark.django_db
def test_excel_builder_creates_faculty_sheet(tmp_path):
    faculty = Faculty.objects.create(
        hierarchy_level=1,
        name="Electrical Engineering",
        abbreviation="EEMCS",
        full_abbreviation="EEMCS",
    )

    CopyrightItem.objects.create(
        material_id=123,
        title="Test Item",
        faculty=faculty,
    )

    builder = ExcelBuilder(faculty_code="EEMCS")
    output = builder.build()

    wb = load_workbook(output)

    assert "EEMCS" in wb.sheetnames
    assert "Overview" in wb.sheetnames

    ws = wb["EEMCS"]
    headers = [cell.value for cell in ws[1]]
    for col in ExcelBuilder.FACULTY_SHEET_COLUMNS:
        assert col in headers


@pytest.mark.django_db
def test_excel_builder_overview_counts(tmp_path):
    faculty = Faculty.objects.create(
        hierarchy_level=1,
        name="Behavioural Sciences",
        abbreviation="BMS",
        full_abbreviation="BMS",
    )

    for idx in range(2):
        CopyrightItem.objects.create(
            material_id=idx + 1,
            title=f"Item {idx + 1}",
            faculty=faculty,
            count_students_registered=10,
        )

    builder = ExcelBuilder()
    wb = load_workbook(builder.build())

    overview = wb["Overview"]
    rows = list(overview.iter_rows(min_row=2, values_only=True))

    assert any(row[0] == "BMS" and row[1] == 2 for row in rows)
