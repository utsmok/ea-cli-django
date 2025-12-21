from django.core.management.base import BaseCommand
from watchfiles import watch

from apps.ingest.tasks import ingest_excel_task


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write("Watching /raw_data for .xlsx files...")
        for changes in watch("/app/raw_data"):
            for _change, path in changes:
                if path.endswith(".xlsx"):
                    # Enqueue the Django 6 Task
                    ingest_excel_task.enqueue(file_path=path)
