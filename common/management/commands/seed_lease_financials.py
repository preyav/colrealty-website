from django.core.management.base import BaseCommand
from common.models import FormFieldSetting

class Command(BaseCommand):
    help='Initialize editable lease Financials wording.'
    def handle(self,*args,**kwargs):
        FormFieldSetting.objects.get_or_create(form_key='lease_financials',field_key='ui',defaults={
            'label':'Lease Financials','option_labels':{
                'financials':'Financials','ledger':'Ledger','current_balance':'Current rent balance',
                'receive':'Receive payment','charge':'Enter charge','save_payment':'Save payment','save_charge':'Save charge',
                'another':'Save and add another','cancel':'Cancel','all':'All transactions','charges':'Charges','payments':'Payments',
                'filter':'Filter transactions','date':'Date','transaction':'Transaction','reference':'Reference','amount':'Amount','balance':'Balance','actions':'Actions',
                'payment':'Payment','reversal':'Void reversal','void':'Void entry','empty':'No rent transactions recorded.',
                'back':'Back to Financials','apply':'Apply payment to rent balances','period':'Rent period','due':'Due date','unpaid':'Unpaid rent','applied':'Payment applied',
                'allocation_help':'Payments automatically cover the oldest open rent charges first. The preview uses posted charges only; excess remains unapplied credit. The saved allocation is recalculated when you submit.',
                'ledger_help':'Rent-only ledger. Charges use their due dates; payments use received dates. Void reversals preserve history. Rows are newest first; running balances include all transaction types. A negative balance represents credit. Deposits and bank balances are separate.',
                'rent':'Rent','proof_link':'Supporting document link','proof_help':'Optional Google Drive or other document URL; this keeps a reference to the original document.'}})
        self.stdout.write(self.style.SUCCESS('Lease Financials settings initialized; existing edits preserved.'))
