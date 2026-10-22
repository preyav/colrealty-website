from django.apps import AppConfig


class AccountingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounting"
    verbose_name = "COL360 Accounting"

    def __init__(self, app_name, app_module):
        super().__init__(app_name, app_module)
        from django.conf import settings
        from common.postgres_guard import require_postgres_databases
        require_postgres_databases(settings.DATABASES)
