from django.apps import AppConfig


class HeritageConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "heritage"
    verbose_name = "Nội dung di tích"

    def ready(self):
        from . import signals  # noqa: F401
