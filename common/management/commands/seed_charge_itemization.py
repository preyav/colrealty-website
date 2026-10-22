from django.core.management.base import BaseCommand
from common.models import FormFieldSetting
class Command(BaseCommand):
    def handle(self,*args,**kwargs):
        FormFieldSetting.objects.get_or_create(form_key='rent_ledger',field_key='income_items',defaults={'label':'Income items','help_text':'Optional: itemize this charge using income accounts. Item amounts must equal the total charge. Blank uses the property rental income account. Partial payments are apportioned across items; this does not create additional receipts.','option_labels':{'account':'Income account','description':'Description','amount':'Amount','default':'Property default','add':'Add income item','remove':'Remove'}})
        self.stdout.write('Income item settings ready; existing labels preserved.')
