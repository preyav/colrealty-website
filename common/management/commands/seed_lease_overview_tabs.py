from django.core.management.base import BaseCommand
from django.db import transaction
from common.models import FormFieldSetting


class Command(BaseCommand):
    help = 'Initialize consolidated Lease 360 labels; preserve customized values.'

    @transaction.atomic
    def handle(self, *args, **options):
        for key, label in {
            'lease-overview': 'Lease Overview',
            'documents': 'Documents',
            'documents_title': 'Original lease & continuations',
            'requests_maintenance': 'Requests & Maintenance',
        }.items():
            FormFieldSetting.objects.get_or_create(
                form_key='lease_summary', field_key=key, defaults={'label': label})
        self.stdout.write(self.style.SUCCESS('Lease 360 tab labels initialized; existing edits preserved.'))
