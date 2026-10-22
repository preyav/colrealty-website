"""COL360 database policy, enforced during application startup."""
from django.core.exceptions import ImproperlyConfigured

POSTGRES_ENGINES = frozenset({
    'django.db.backends.postgresql',
    'django.db.backends.postgresql_psycopg2',
})


def require_postgres_databases(databases):
    if not databases or 'default' not in databases:
        raise ImproperlyConfigured('COL360 requires a configured PostgreSQL default database.')
    invalid = [alias for alias, config in databases.items()
               if config.get('ENGINE') not in POSTGRES_ENGINES]
    if invalid:
        raise ImproperlyConfigured(
            'COL360 permits PostgreSQL only. Correct these database aliases: '
            + ', '.join(sorted(invalid))
            + '. No alternate database fallback is permitted.'
        )
