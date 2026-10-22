from django.core.management.base import BaseCommand
from common.models import FormFieldSetting

class Command(BaseCommand):
    help = "Initialize editable Lease 360 workspace labels without replacing existing edits."
    def handle(self,*args,**kwargs):
        FormFieldSetting.objects.get_or_create(form_key='lease_workspace',field_key='ui',defaults={
            'label':'Lease 360 workspace','option_labels':{
                'lease':'Lease','rent_ledger':'Rent ledger','financial_summary':'Rent balance',
                'outstanding':'Outstanding rent','overdue':'Overdue rent','credit':'Unapplied credit',
                'open_ledger':'View rent ledger','current_terms':'Current recorded terms',
                'balance_info':'About these balances',
                'balance_help':'Totals reflect recorded rent charges and payments across all periods for this lease. An empty ledger shows zero; it does not establish that all contractual rent has been collected. Credit is shown separately. These are not bank balances, and security deposits are excluded.'}})
        self.stdout.write(self.style.SUCCESS('Lease workspace settings initialized; existing edits preserved.'))
