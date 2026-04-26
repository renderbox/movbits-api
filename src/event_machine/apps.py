from django.apps import AppConfig


class EventMachineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "event_machine"

    def ready(self):
        from django.conf import settings

        # Dynamically set EVENT_MACHINE_REDIS_URL if not already defined
        if not hasattr(settings, "EVENT_MACHINE_REDIS_URL"):
            settings.EVENT_MACHINE_REDIS_URL = "redis://localhost:6379"

        # Dynamically set EVENT_MACHINE_S3_BUCKET_NAME if not already defined
        if not hasattr(settings, "EVENT_MACHINE_S3_BUCKET_NAME"):
            settings.EVENT_MACHINE_S3_BUCKET_NAME = None
