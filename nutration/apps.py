from django.apps import AppConfig


class NutrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "nutration"
    verbose_name = "Nutrition & Lifestyle Planner"

    def ready(self):
        # registers models in models_log.py
        from . import models_log    # noqa: F401