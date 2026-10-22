from django.core.management.base import BaseCommand
from common.models import FormFieldSetting


class Command(BaseCommand):
    help='Add the editable deposit classification label without changing business records.'

    def handle(self,*args,**options):
        row=FormFieldSetting.objects.get(form_key='accounting_books',field_key='event_kinds')
        labels=dict(row.option_labels)
        labels.setdefault('credit_to_deposit','Classify payment credit as security deposit')
        row.option_labels=labels;row.save(update_fields=['option_labels'])
        ui=FormFieldSetting.objects.get(form_key='lease_financials',field_key='ui')
        labels=dict(ui.option_labels);labels.setdefault('deposit_held','Refundable security deposit held')
        ui.option_labels=labels;ui.save(update_fields=['option_labels'])
        self.stdout.write('Deposit classification label ready. No transactions changed.')
