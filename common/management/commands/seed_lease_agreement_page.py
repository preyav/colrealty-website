from django.core.management.base import BaseCommand
from django.db import transaction
from common.models import FormFieldSetting


class Command(BaseCommand):
    help = 'Initialize editable agreement page headings and navigation wording.'

    @transaction.atomic
    def handle(self, *args, **options):
        labels = {
            'identity': 'Agreement & Parties', 'dates': 'Term & Dates',
            'rent': 'Rent', 'contact': 'Designated Contact',
            'amendments': 'Amendments & Additional Clauses',
            'conditional': 'Conditional Notice', 'review': 'Signatures & Review',
            'view_details': 'View agreement details →', 'view_extension': 'View extension details →',
            'back': '← Lease 360', 'create': 'Record Lease Agreement',
            'save': 'Save Agreement', 'read_only': 'Executed agreement',
        }
        for key, label in labels.items():
            FormFieldSetting.objects.get_or_create(form_key='lease_agreement_page', field_key=key, defaults={'label': label})
        self.stdout.write(self.style.SUCCESS('Agreement page wording initialized; existing edits preserved.'))
