"""
Management command to inspect Redis cache statistics.

Usage:
    python manage.py cache_stats
    python manage.py cache_stats --cache default
    python manage.py cache_stats --cache queries
"""

from django.core.cache import caches
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Show Redis cache statistics for all configured backends"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--cache",
            type=str,
            choices=["default", "queries", "all"],
            default="all",
            help="Which cache backend to show stats for (default: all)",
        )

    def handle(self, *args, **options):
        """Display cache stats for configured backends."""
        cache_choice = options["cache"]

        # Determine which caches to show
        if cache_choice == "all":
            cache_names = ["default", "queries"]
        else:
            cache_names = [cache_choice]

        for cache_name in cache_names:
            try:
                cache = caches[cache_name]

                self.stdout.write(self.style.SUCCESS(f"\n=== Cache: {cache_name} ==="))

                # Get redis client
                if hasattr(cache, "client"):
                    client = cache.client.get_client()

                    # Get basic info
                    info = client.info("stats")
                    key_count = client.dbsize()

                    # Display stats
                    self.stdout.write(f"Total keys: {key_count}")
                    self.stdout.write(
                        f"Total connections received: {info.get('total_connections_received', 'N/A')}"
                    )
                    self.stdout.write(
                        f"Total commands processed: {info.get('total_commands_processed', 'N/A')}"
                    )

                    # Get memory info
                    mem_info = client.info("memory")
                    self.stdout.write(
                        f"Used memory: {mem_info.get('used_memory_human', 'N/A')}"
                    )
                    self.stdout.write(
                        f"Memory peak: {mem_info.get('used_memory_peak_human', 'N/A')}"
                    )

                    # Get cache-specific keys with our prefix
                    from django.conf import settings

                    prefix = settings.CACHE_KEY_PREFIX
                    if cache_name == "queries":
                        prefix = f"{prefix}_queries"

                    # Count keys with our prefix
                    pattern = f"{prefix}*"
                    keys_with_prefix = list(client.scan_iter(match=pattern, count=1000))
                    self.stdout.write(
                        f"Keys with prefix '{prefix}': {len(keys_with_prefix)}"
                    )

                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Cache '{cache_name}' does not support Redis stats"
                        )
                    )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error getting stats for '{cache_name}': {e}")
                )

        self.stdout.write("")  # Final newline
