from django.core.management.base import BaseCommand
from common.models import FormFieldSetting
from accounting.models import ChartAccount,FinancialAccount

class Command(BaseCommand):
    help='Initialize editable Accounting labels; preserve existing accounts and settings.'
    def handle(self,*args,**kwargs):
        ui={'accounting':'Accounting','financials':'Financials','general_ledger':'General ledger','banking':'Banking','bills':'Bills',
            'recurring':'Recurring transactions','eft':'EFT approvals','budgets':'Budgets','chart':'Chart of accounts','company':'Company financials',
            'tax':'1099 tax filings','quickbooks':'QuickBooks','unavailable':'This workflow is not yet available.','planned':'Not yet available',
            'add':'Add account','add_bank':'Add financial account','edit_chart':'Edit chart account','add_chart':'Add chart account',
            'edit_bank':'Edit financial account','back':'Back to chart of accounts','back_bank':'Back to Banking','save':'Save account','cancel':'Cancel',
            'types_selected':'account types selected','all':'All accounts','active':'Active','inactive':'Inactive','all_statuses':'All statuses','search':'Search accounts','filter':'Apply filters','reset':'Reset',
            'show_codes':'Show account numbers','matches':'matches','export':'Export CSV','name':'Name','code':'Account number','type':'Type','notes':'Notes',
            'status':'Status','actions':'Actions','edit':'Edit','empty':'No accounts match these filters.','help':'Chart accounts classify transactions. Banking holds the actual financial accounts linked to those classifications. No balances or transactions are changed by these filters.',
            'bank_help':'Configured financial accounts. Opening balances are setup values, not live bank balances.','kind':'Kind','institution':'Institution','linked':'Ledger account','opening':'Opening balance',
            'required':'Required','form_help':'Enter an account number, name and accounting type. Notes are optional. Deactivating an account preserves its history.'}
        FormFieldSetting.objects.get_or_create(form_key='accounting_workspace',field_key='ui',defaults={'label':'Accounting interface','option_labels':ui})
        for kind,Model,fields in [('chart',ChartAccount,['code','name','account_type','description','is_active']),('bank',FinancialAccount,['name','kind','ledger_account','institution_name','account_last_four','opening_balance','opening_balance_date','notes','is_active'])]:
            for name in fields:
                field=Model._meta.get_field(name)
                choices=dict(field.choices or [])
                FormFieldSetting.objects.get_or_create(form_key='accounting_workspace',field_key=kind+'_'+name,defaults={
                    'label':ui['code'] if kind=='chart' and name=='code' else str(field.verbose_name).replace('_',' ').capitalize(),
                    'help_text':ui['help'] if name=='account_type' else '', 'option_labels':choices})
        self.stdout.write(self.style.SUCCESS('Accounting workspace settings initialized; existing accounts preserved.'))
