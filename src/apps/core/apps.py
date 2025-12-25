from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Core"

    def ready(self):
        """
        Import signal handlers when Django app is ready.

        This ensures cache invalidation signals are registered
        when the app starts up.
        """
        # Import cache invalidation signals
        import apps.core.services.cache_invalidation  # noqa: F401
