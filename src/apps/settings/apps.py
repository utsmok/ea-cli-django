from django.apps import AppConfig


class SettingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.settings'
    verbose_name = 'Settings Management'

    def ready(self):
        """Import signal handlers when app is ready."""
        pass
