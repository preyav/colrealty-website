from django.core.management.base import BaseCommand
from django.core.management import call_command
from common.models import FormFieldSetting

class Command(BaseCommand):
    help='Initialize ledger column labels and income-statement row controls without changing financial records.'
    def handle(self,*args,**kwargs):
        call_command('seed_property_financials',verbosity=0)
        row=FormFieldSetting.objects.get(form_key='lease_financials',field_key='ui');options=dict(row.option_labels)
        additions={'invoice':'Invoice','account':'Account','invoice_help':'Invoice number stored on the entry, if available. A payment reference is not an invoice number.','account_help':'Income chart accounts from linked postings, otherwise the property-configured account. This is not the receiving bank account.'}
        for key,value in additions.items():options.setdefault(key,value)
        row.option_labels=options;row.save(update_fields=['option_labels'])
        for form in ['property_income_statement','lease_income_statement','financials']:
            row=FormFieldSetting.objects.get(form_key=form,field_key='ui');options=dict(row.option_labels)
            for key,value in {'show_empty_accounts':'1','expand_rows':'Expand all rows','collapse_rows':'Collapse all rows'}.items():options.setdefault(key,value)
            for key,old,new in [('expand','Expand all accounts','Expand all rows'),('collapse','Collapse all accounts','Collapse all rows')]:
                if options.get(key)==old:options[key]=new
            row.option_labels=options;row.save(update_fields=['option_labels'])
        self.stdout.write(self.style.SUCCESS('Financial presentation settings initialized. No transactions changed.'))
