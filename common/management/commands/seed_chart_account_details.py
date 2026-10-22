from django.core.management.base import BaseCommand
from common.models import FormFieldSetting

class Command(BaseCommand):
    help='Initialize editable chart-account detail fields without creating accounts.'
    def handle(self,*args,**kwargs):
        fields={
            'cash_asset':('Cash asset','Identifies an asset account representing cash. This flag does not create a bank connection or change balances.',{}),
            'account_level':('Account level','Choose Parent account for a top-level account, or Subaccount and select its parent.',{'parent':'Parent account','subaccount':'Subaccount'}),
            'parent':('Parent account','Select an account of the same accounting type. Accounts cannot be their own parent or descendants.',{}),
            'fund_type':('Fund type','Classification only; it does not move money or establish fund segregation.',{'operating':'Operating'}),
        }
        for key,(label,help_text,options) in fields.items():
            FormFieldSetting.objects.get_or_create(form_key='chart_account_details',field_key=key,defaults={'label':label,'help_text':help_text,'option_labels':options})
            if key!='account_level':
                FormFieldSetting.objects.get_or_create(form_key='accounting_workspace',field_key='chart_'+key,defaults={'label':label,'help_text':help_text,'option_labels':options})
        FormFieldSetting.objects.get_or_create(form_key='chart_account_details',field_key='defaults',defaults={'label':'Chart account defaults','option_labels':{'fund_type':'operating'}})
        FormFieldSetting.objects.get_or_create(form_key='chart_account_details',field_key='linked_help',defaults={'label':'Linked financial account','help_text':'This chart account is linked to a financial account. Its accounting type is locked; bank, trust and cash accounts are marked as cash assets.'})
        FormFieldSetting.objects.get_or_create(form_key='chart_account_details',field_key='errors',defaults={'label':'Chart account validation','option_labels':{
            'cash_type':'Cash asset is available only for asset accounts.','cycle':'An account cannot be its own parent or a descendant of itself.',
            'parent_type':'Parent and subaccount must have the same accounting type.','children_type':'This type conflicts with existing subaccounts. Update their structure first.',
            'linked_type':'This accounting type is required by the linked financial account.','parent_required':'Select a parent account for this subaccount.'}})
        row,created=FormFieldSetting.objects.get_or_create(form_key='accounting_workspace',field_key='chart_description',defaults={'label':'Notes'})
        if not created and row.label=='Description':row.label='Notes';row.save(update_fields=['label'])
        ui=FormFieldSetting.objects.get(form_key='accounting_workspace',field_key='ui')
        options=dict(ui.option_labels)
        for key,value in {'cash_asset':'Cash asset','fund_type':'Fund type','parent':'Parent account'}.items():options.setdefault(key,value)
        if options!=ui.option_labels:ui.option_labels=options;ui.save(update_fields=['option_labels'])
        self.stdout.write(self.style.SUCCESS('Chart account detail settings initialized; existing account values preserved.'))
