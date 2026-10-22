from django.core.management.base import BaseCommand
from common.models import FormFieldSetting

class Command(BaseCommand):
    help = "Initialize editable unified rent workspace wording."
    def handle(self,*args,**kwargs):
        FormFieldSetting.objects.get_or_create(form_key='rent_ledger',field_key='workspace',defaults={
            'label':'Rent workspace','option_labels':{
                'default_due_day':'1',
                'select_method':'Select payment method',
                'charge_defaults_help':'Dates and amount are suggestions. Confirm contractual due date, effective rent and any proration. If no numeric lease due day is stored, the configured default due day is used.',
                'pending':'Pending amount after this payment',
                'excess':'Excess amount / unapplied credit after this payment',
                'reference_help':'The suggested RENT reference is an internal identifier, not bank verification. Replace it with the actual check or transaction reference when available.',
                'preview_help':'Preview assumes only this payment is saved against posted charges. Save new charges first. Payments apply to the oldest open rent; excess stays as credit. Existing unapplied credit is shown separately above.'}})
        self.stdout.write(self.style.SUCCESS('Rent workspace settings initialized.'))
