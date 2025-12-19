import fastexcel
import polars as pl

excel_path = r"C:\dev\ea-cli-django\ea-cli\faculty_sheets\BMS\overview.xlsx"
excel = fastexcel.read_excel(excel_path)
sheet = excel.load_sheet(0)
df = sheet.to_polars()

print(f"Total rows: {len(df)}")
# The column names are 'course_contacts_organizations'
# and 'course_contacts_names'
contacts_col = "course_contacts_names"
orgs_col = "course_contacts_organizations"

rows_with_contacts = df.filter(
    pl.col(contacts_col).is_not_null() & (pl.col(contacts_col) != "")
)
rows_with_orgs = df.filter(pl.col(orgs_col).is_not_null() & (pl.col(orgs_col) != ""))

print(f"Rows with contacts: {len(rows_with_contacts)}")
print(f"Rows with organizations: {len(rows_with_orgs)}")

missing_orgs = rows_with_contacts.filter(
    pl.col(orgs_col).is_null() | (pl.col(orgs_col) == "")
)
print(f"Rows with contacts but missing orgs: {len(missing_orgs)}")

if len(missing_orgs) > 0:
    print("Sample missing orgs:")
    print(missing_orgs.select(["material_id", contacts_col, orgs_col]).head(10))
