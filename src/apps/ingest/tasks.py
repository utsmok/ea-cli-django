import polars as pl
from django.tasks import task

from apps.core.models import StagedItem


@task(queue_name="default")
def ingest_excel_task(file_path: str):
    try:
        # 1. Read with Polars (Super fast)
        df = pl.read_excel(file_path)

        # 2. Convert to list of dictionaries
        rows = df.to_dicts()

        # 3. Bulk create StagedItems
        batch = [StagedItem(source_file=file_path, payload=row) for row in rows]
        StagedItem.objects.bulk_create(batch, batch_size=5000)

        return f"Successfully staged {len(batch)} rows from {file_path}"
    except Exception:
        # In Django 6, this error is saved to TaskResult.errors
        raise
