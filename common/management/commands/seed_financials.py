from django.core.management.base import BaseCommand
from common.models import FormFieldSetting

class Command(BaseCommand):
    help='Initialize editable COL360 Financials labels; creates no transactions.'
    def handle(self,*args,**kwargs):
        ui={'title':'Financials','period':'Period','three':'Three months to date','six':'Six months to date','twelve':'Twelve months to date','year':'Year to date','month':'Current month to date','income':'Income','expense':'Expenses','income_total':'Total income','expense_total':'Total expenses','net':'Net income','total':'Period total','to_date':'to date','matches':'properties','account':'Property / account','expand':'Expand all accounts','collapse':'Collapse all accounts','no_activity':'No posted income or expense journal entries in this period.','empty':'No properties match these filters.','coverage':'Accrual basis · posted COL360 journals. Rent charges, rent receipts, vendor bills and payments appear only after journal posting integration; they are not automatically included yet. Security deposits, bank transfers, owner contributions and distributions are excluded from income and expenses.','net_help':'Net income is posted income less posted expenses for the selected period. It is not a bank balance or the amount available for owner distribution. No separate net operating income is inferred without account classification.'}
        ui.update({'show_empty':'Show accounts with no activity','accrual':'Accrual basis','cash':'Cash basis (not yet available)',
            'totals_help':'Net income is posted income less posted expenses. Net operating income includes only accounts classified as operating. These totals are not bank balances or funds available for distribution.',
            'basis_info':'Reporting basis information','cash_help':'Cash-basis reporting requires settlement links between payments and journals. The figures shown here use posted accrual journals.',
            'property_level':'Property level','single_unit':'1','view_entries':'View underlying journal entries',
            'operating_net':'Net operating income','unclassified':'—',
            'classification_help':'Classify accounts in Django admin → Form field settings → financial_account_classification. Set classification to operating or non_operating. Net operating income remains unavailable while accounts with activity are unclassified.'})
        row,_=FormFieldSetting.objects.get_or_create(form_key='financials',field_key='ui',defaults={'label':'Financials interface','option_labels':ui})
        options=dict(row.option_labels)
        for key,value in ui.items():options.setdefault(key,value)
        if options!=row.option_labels:row.option_labels=options;row.save(update_fields=['option_labels'])
        self.stdout.write(self.style.SUCCESS('Financials settings initialized; existing wording preserved.'))

        from accounting.models import ChartAccount
        for account in ChartAccount.objects.filter(account_type__in=['income','expense']):
            FormFieldSetting.objects.get_or_create(form_key='financial_account_classification',field_key=str(account.pk),defaults={
                'label':str(account), 'help_text':'Use classification: operating, non_operating, or unclassified. Account classification applies to all report periods.',
                'option_labels':{'classification':'unclassified'}})
