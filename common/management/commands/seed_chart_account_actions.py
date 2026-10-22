from django.core.management.base import BaseCommand
from common.models import FormFieldSetting

class Command(BaseCommand):
    help='Initialize editable chart-account action menu wording.'
    def handle(self,*args,**kwargs):
        FormFieldSetting.objects.get_or_create(form_key='chart_account_actions',field_key='ui',defaults={'label':'Chart account actions','option_labels':{
            'edit':'Edit account','move':'Move transactions','inactivate':'Inactivate account','activate':'Reactivate account','delete':'Delete account',
            'move_help':'Not yet available: general-ledger transaction reclassification has not been implemented.',
            'inactivate_help':'Inactivate this account while preserving its configuration and history. Active linked financial accounts and active subaccounts must be addressed first.',
            'activate_help':'Make this account available again. Its accounting classifications remain unchanged.',
            'delete_help':'Permanently delete this unused account configuration. Accounts linked to other records cannot be deleted; inactivate them instead. Existing audit history is retained.',
            'used':'This account is linked to other records and cannot be deleted. Inactivate it when appropriate.',
            'bank_active':'Inactivate the linked financial account before inactivating this chart account.',
            'children_active':'Inactivate or reassign active subaccounts before inactivating this parent account.',
            'delete_reason':'Unused chart account configuration deleted after confirmation.',
            'status_reason':'Chart account availability changed after confirmation.',
            'cancel':'Cancel','confirm':'Confirm','back':'Back to chart of accounts','actions':'Account actions'}})
        self.stdout.write(self.style.SUCCESS('Chart account action settings initialized.'))
