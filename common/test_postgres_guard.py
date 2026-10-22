"""Configuration-policy tests. These functions do not open a database."""
from unittest import TestCase
from django.core.exceptions import ImproperlyConfigured
from common.postgres_guard import require_postgres_databases


class PostgreSQLGuardTests(TestCase):
    def test_postgres_configuration_is_accepted(self):
        require_postgres_databases({'default': {'ENGINE': 'django.db.backends.postgresql'}})

    def test_missing_default_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            require_postgres_databases({})

    def test_other_backend_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            require_postgres_databases({'default': {'ENGINE': 'django.db.backends.dummy'}})

    def test_secondary_backend_cannot_bypass_policy(self):
        with self.assertRaises(ImproperlyConfigured):
            require_postgres_databases({'default': {'ENGINE': 'django.db.backends.postgresql'},
                                        'secondary': {'ENGINE': 'django.db.backends.dummy'}})
