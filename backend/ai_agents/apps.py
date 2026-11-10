from django.apps import AppConfig


class AiAgentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_agents'
    verbose_name = 'AI Agents'

    def ready(self):
        from . import signals  # noqa: F401
