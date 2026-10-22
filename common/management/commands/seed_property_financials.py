from django.core.management import call_command
from django.core.management.base import BaseCommand
from common.models import FormFieldSetting


class Command(BaseCommand):
    help='Configure Property 360 financial navigation, preserving existing income-statement settings.'
    def handle(self,*args,**kwargs):
        call_command('seed_lease_income_statement',verbosity=0)
        source=FormFieldSetting.objects.get(form_key='lease_income_statement',field_key='ui')
        report_options=dict(source.option_labels)
        report_options['scope_help']='Property-wide posted income and expenses, including all leases, units and property-level activity. Tenant transactions remain available in each lease Ledger.'
        FormFieldSetting.objects.get_or_create(form_key='property_income_statement',field_key='ui',defaults={'label':'Property income statement','option_labels':report_options})
        values={'overview':'Overview','financials':'Financials','income_statement':'Income Statement','back':'Back to properties'}
        row,_=FormFieldSetting.objects.get_or_create(form_key='property_financials',field_key='ui',defaults={'label':'Property financial navigation','option_labels':values})
        options=dict(row.option_labels)
        for key,value in values.items():options.setdefault(key,value)
        if options!=row.option_labels:row.option_labels=options;row.save(update_fields=['option_labels'])
        self.stdout.write(self.style.SUCCESS('Property financial settings initialized. Transactions unchanged.'))
