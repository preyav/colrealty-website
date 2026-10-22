"""Run COL360 regression tests against PostgreSQL using the real project."""
import json
from datetime import datetime, timezone
from pathlib import Path
from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.db import connections
from common.postgres_validation import PostgresOnlyDiscoverRunner, require_real_test_schema

DEFAULT_LABELS = [
    'common.test_postgres_guard',
    'accounting.test_postgres_transactions',
    'accounting.test_rent_phase1', 'accounting.test_book_accounting',
    'accounting.test_deposit_classification', 'accounting.test_rent_reconciliation',
    'accounting.test_rent_edit', 'accounting.test_allocation_editor',
    'accounting.test_charge_itemization', 'accounting.test_reimbursements',
    'accounting.test_workspace', 'accounting.test_chart_details',
    'accounting.test_chart_actions', 'accounting.test_general_ledger',
    'accounting.test_bank_actions', 'accounting.test_financials',
    'accounting.test_financial_breakdowns',
    'portal.test_owner_work', 'portal.test_tenant_work', 'portal.test_historical_work',
    'portal.test_invoice_payees', 'portal.test_property_overview',
    'portal.test_statement_rows', 'portal.test_property_financials',
    'portal.test_financial_presentation', 'portal.test_dashboard_phase1',
    'portal.test_settings', 'portal.test_navigation_registers', 'portal.test_lease_income',
]


class Command(BaseCommand):
    help = 'Validate real migrations and run COL360 tests on PostgreSQL only.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('labels', nargs='*', help='Optional specific Django test labels.')
        parser.add_argument('--output', default='COL360_PostgreSQL_Validation.json')
        parser.add_argument('--keepdb', action='store_true', help='Reuse only an existing test_ database.')

    def handle(self, *args, **options):
        report = {
            'started_at': datetime.now(timezone.utc).isoformat(),
            'settings_module': getattr(settings, 'SETTINGS_MODULE', ''),
            'backend': 'postgresql', 'status': 'not_run',
            'labels': options['labels'] or DEFAULT_LABELS,
        }
        path = Path(options['output']).resolve()
        try:
            require_real_test_schema()
            versions = {}
            for alias in connections:
                with connections[alias].cursor() as cursor:
                    cursor.execute('SHOW server_version')
                    versions[alias] = cursor.fetchone()[0]
            report['server_versions'] = versions
            self.stdout.write('PostgreSQL confirmed. Checking real project settings and migrations.')
            report['stage'] = 'migration_checks'
            call_command('check', verbosity=options['verbosity'])
            call_command('makemigrations', '--check', dry_run=True, interactive=False,
                         verbosity=options['verbosity'])
            call_command('migrate', '--check', verbosity=options['verbosity'])
            report['stage'] = 'tests'
            runner = PostgresOnlyDiscoverRunner(
                verbosity=options['verbosity'], interactive=True,
                keepdb=options['keepdb'], parallel=1,
            )
            failures = runner.run_tests(report['labels'])
            report.update(getattr(runner, 'validation_summary', {}))
            if not report.get('tests_run'):
                raise CommandError('No tests ran; validation cannot pass.')
            report['status'] = 'failed' if failures else ('needs_review' if report.get('skipped') or report.get('expected_failures') else 'passed')
        except (Exception, SystemExit) as exc:
            report['status'] = 'blocked_or_failed'
            # Do not write connection strings, credentials or exception text to the report.
            report['error_type'] = type(exc).__name__
            if isinstance(exc, SystemExit):
                raise CommandError('Migration preflight failed. Review the output above.') from exc
            raise
        finally:
            report['finished_at'] = datetime.now(timezone.utc).isoformat()
            path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
            self.stdout.write(f'Validation report: {path}')
        if report['status'] != 'passed':
            raise CommandError('PostgreSQL validation needs review. Resolve failures, errors, skips or expected failures before continuing.')
        self.stdout.write(self.style.SUCCESS('PostgreSQL validation passed. No alternate backend was used.'))
