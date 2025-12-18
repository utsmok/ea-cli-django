import asyncio
from django.core.management.base import BaseCommand
from apps.enrichment.services.osiris_scraper import OsirisScraperService


class Command(BaseCommand):
    help = "Verify connection and scraping from Osiris"

    def add_arguments(self, parser):
        parser.add_argument("--course", type=int, help="Course code to test", default=191154340)  # Example from legacy
        parser.add_argument("--person", type=str, help="Person name to test", default="Augustijn")

    def handle(self, *args, **options):
        self.stdout.write("Testing Osiris & People Page connection...")

        async def run_test():
            async with OsirisScraperService() as scraper:
                # Test course
                course_code = options["course"]
                self.stdout.write(f"Testing course: {course_code}")
                course_data = await scraper.fetch_course_details(course_code)
                if course_data:
                    self.stdout.write(self.style.SUCCESS(f"Course found: {course_data.get('name')}"))
                    self.stdout.write(f"  Internal ID: {course_data.get('internal_id')}")
                    self.stdout.write(f"  Teachers: {course_data.get('teachers')}")
                else:
                    self.stdout.write(self.style.ERROR(f"Course {course_code} not found or error occurred"))

                # Test person
                person_name = options["person"]
                self.stdout.write(f"\nTesting person: {person_name}")
                person_data = await scraper.fetch_person_data(person_name)
                if person_data:
                    self.stdout.write(self.style.SUCCESS(f"Person found: {person_data.get('main_name')}"))
                    self.stdout.write(f"  Email: {person_data.get('email')}")
                    self.stdout.write(f"  Orgs: {person_data.get('orgs')}")
                else:
                    self.stdout.write(self.style.ERROR(f"Person {person_name} not found or error occurred"))

        asyncio.run(run_test())
