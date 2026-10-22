"""Enforce PostgreSQL for COL360 and its Django test databases."""
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test.runner import DiscoverRunner

from .postgres_guard import require_postgres_databases


def require_real_test_schema():
    require_postgres_databases(settings.DATABASES)
    disabled = [app for app, module in settings.MIGRATION_MODULES.items() if module is None]
    if disabled:
        raise ImproperlyConfigured(
            'PostgreSQL validation requires real migrations; migration disabling is configured for: '
            + ', '.join(sorted(disabled))
        )
    for alias in connections:
        connection = connections[alias]
        if connection.vendor != 'postgresql':
            raise ImproperlyConfigured(f'Database alias {alias} is not PostgreSQL.')
        config = connection.settings_dict
        test = config.get('TEST', {})
        if test.get('MIRROR'):
            raise ImproperlyConfigured('This validation requires independent test databases, not database mirrors.')
        name = test.get('NAME') or 'test_' + str(config.get('NAME', ''))
        # Refuse a configuration that could point tests at the application database.
        if name == config.get('NAME') or not str(name).startswith('test_'):
            raise ImproperlyConfigured(
                f'Test database for {alias} must be distinct and start with test_.'
            )


class PostgresOnlyDiscoverRunner(DiscoverRunner):
    """Use the real project URLs, app registry and migrations without substitutes."""
    def setup_databases(self, **kwargs):
        require_real_test_schema()
        return super().setup_databases(**kwargs)

    def run_suite(self, suite, **kwargs):
        result = super().run_suite(suite, **kwargs)
        self.validation_summary = {
            'tests_run': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'skipped': len(getattr(result, 'skipped', [])),
            'expected_failures': len(getattr(result, 'expectedFailures', [])),
            'unexpected_successes': len(getattr(result, 'unexpectedSuccesses', [])),
            'successful': result.wasSuccessful(),
        }
        return result
