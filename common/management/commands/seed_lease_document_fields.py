from django.core.management.base import BaseCommand
from common.models import FormFieldSetting
from leasing.models import LeaseDocument


class Command(BaseCommand):
    help = 'Initialize editable document type wording without overwriting existing settings.'

    def handle(self, *args, **options):
        FormFieldSetting.objects.get_or_create(
            form_key='lease_document', field_key='category',
            defaults={'label': 'Document Type', 'help_text': '',
                      'option_labels': dict(LeaseDocument.CATEGORY_CHOICES)},
        )
        self.stdout.write(self.style.SUCCESS('Document type settings initialized; existing edits preserved.'))
