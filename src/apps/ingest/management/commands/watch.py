from django.core.management.base import BaseCommand
from watchfiles import watch


class Command(BaseCommand):
    help = "Watch a directory for new Excel files and automatically ingest them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default="/raw_data",
            help="Path to watch for new Excel files (default: /raw_data)",
        )

    def handle(self, *args, **options):
        watch_path = options["path"]
        self.stdout.write(f"Watching {watch_path} for .xlsx files...")

        for changes in watch(watch_path):
            for _change, path in changes:
                if path.endswith(".xlsx"):
                    self.stdout.write(f"New file detected: {path}")

                    # Use the ingest_qlik_file management command to process the file
                    from apps.ingest.management.commands.ingest_qlik_file import (
                        Command as IngestCommand,
                    )

                    ingest_cmd = IngestCommand()
                    try:
                        ingest_cmd.handle(file_path=path)
                    except Exception as e:
                        self.stderr.write(
                            self.style.ERROR(f"Failed to ingest {path}: {e}")
                        )
