from django.core.management.base import BaseCommand
from django.db import transaction
from common.models import FormFieldSetting


class Command(BaseCommand):
    help = 'Initialize editable signed-document link wording without overwriting edits.'

    @transaction.atomic
    def handle(self, *args, **options):
        labels = {'view_signed_lease': 'View signed lease ↗',
                  'view_signed_extension': 'View signed extension ↗',
                  'view_signed_agreement': 'View signed agreement ↗',
                  'add_document_link': 'Add document link'}
        for key, label in labels.items():
            FormFieldSetting.objects.get_or_create(form_key='lease_agreement_page', field_key=key, defaults={'label': label})
        self.stdout.write(self.style.SUCCESS('Signed-document link wording initialized; existing edits preserved.'))
