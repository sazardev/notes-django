from django.apps import AppConfig


class NotesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notes'
    
    def ready(self):
        """Conectar signals cuando la app esté lista."""
        import notes.signals
