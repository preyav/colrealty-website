from django.core.management.base import BaseCommand
from common.models import FormFieldSetting

class Command(BaseCommand):
    help='Initialize editable bank-action wording; does not change or delete bank accounts.'
    def handle(self,*args,**kwargs):
        ui={'delete':'Delete','inactivate':'Inactivate','activate':'Reactivate','cancel':'Cancel','confirm':'Confirm','ledger':'Linked ledger account','opening':'Opening balance',
            'delete_help':'Delete this unused bank account configuration, including its displayed opening balance and unused ownership assignment. The deleted values are retained in the audit history. Its chart account remains. Accounts with transaction or reconciliation records cannot be deleted. This does not close the account at your bank.',
            'inactivate_help':'Stop offering this bank account for new transactions while retaining its balances, ownership links and accounting history. This does not close the real bank account.',
            'activate_help':'Make this financial account available for new transactions again.',
            'used':'This account has posted journals, transaction records or reconciliation records and cannot be deleted. Inactivate it instead when appropriate.',
            'delete_reason':'Unused bank account configuration deleted after confirmation.','status_reason':'Bank account availability changed after confirmation.'}
        row,_=FormFieldSetting.objects.get_or_create(form_key='bank_account_actions',field_key='ui',defaults={'label':'Bank account actions','option_labels':ui})
        options=dict(row.option_labels)
        for key,value in ui.items():options.setdefault(key,value)
        prior={'delete_help':'Delete this unused bank account record from COL360. Its chart account remains. This does not close the account at your bank.',
               'used':'This account has an opening balance, posted journals or linked records and cannot be deleted. Inactivate it instead when appropriate.'}
        for key,value in prior.items():
            if options.get(key)==value:options[key]=ui[key]
        if row.option_labels!=options:row.option_labels=options;row.save(update_fields=['option_labels'])
        self.stdout.write(self.style.SUCCESS('Bank account action wording initialized.'))
