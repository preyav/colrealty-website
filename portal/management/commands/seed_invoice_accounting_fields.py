from django.core.management.base import BaseCommand
from common.models import FormFieldSetting
from portal.invoice_accounting import FORM_KEY, FIELD_DEFAULTS, UI_DEFAULTS

class Command(BaseCommand):
    help = 'Add editable invoice accounting labels and help without replacing custom settings.'

    def handle(self, *args, **options):
        for key, (label, help_text) in FIELD_DEFAULTS.items():
            FormFieldSetting.objects.get_or_create(form_key=FORM_KEY, field_key=key, defaults={'label': label, 'help_text': help_text})
        row, created = FormFieldSetting.objects.get_or_create(form_key=FORM_KEY, field_key='ui', defaults={'label': 'Invoice accounting text', 'option_labels': UI_DEFAULTS})
        if not created:
            merged = {**UI_DEFAULTS, **row.option_labels}
            if merged != row.option_labels:
                row.option_labels = merged
                row.save(update_fields=['option_labels'])
        self.stdout.write(self.style.SUCCESS('Invoice accounting field settings ready.'))
