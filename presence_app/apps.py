from django.apps import AppConfig


class PresenceAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'presence_app'
    
    def ready(self):
        import presence_app.signals
