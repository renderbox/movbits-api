from django.apps import AppConfig


class ShortlinkConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shortlink"

    def ready(self):
        import shortlink.signals  # noqa: F401  registers user_logged_in receiver
