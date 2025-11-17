# pool_app/apps.py
from django.apps import AppConfig

class PoolAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pool_app'

    def ready(self):
        import pool_app.models  # Load signals