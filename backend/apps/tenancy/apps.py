from django.apps import AppConfig


class TenancyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenancy"

    def ready(self) -> None:
        from . import signals  # noqa: F401
