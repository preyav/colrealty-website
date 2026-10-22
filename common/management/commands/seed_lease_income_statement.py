from django.core.management.base import BaseCommand
from django.core.management import call_command
from common.models import FormFieldSetting

class Command(BaseCommand):
    help='Initialize Lease 360 income-statement controls. Does not post or change transactions.'
    def handle(self,*args,**kwargs):
        call_command('seed_financials',verbosity=0)
        options={'income_statement':'Income Statement','ledger':'Ledger','period':'Timeframe','basis':'Reporting basis','cash':'Cash basis','accrual':'Accrual basis','apply':'Apply','default_period':'three','scope_help':'This income statement covers the entire property, including other leases, units and property-level expenses. The Ledger tab covers this lease only.','coverage_help':'Only posted journals for the selected accounting entity and basis are included. Unposted rent payments and bills are not income or expenses in this report. No historical entries are posted automatically.','incomplete':'Accounting coverage is incomplete. Review unposted source records and unassigned journals before relying on these totals.','setup':'Assign this property to an accounting entity in Portal Settings → Property accounting before viewing its income statement.','disabled':'Property accounting is disabled. Existing posted journals are shown; new operational transactions may not be posted.','classification_help':'Set each income/expense account classification in Portal Settings → Field labels & options → financial_account_classification to operating or non_operating. Net operating income is unavailable while accounts with activity remain unclassified.'}
        row,_=FormFieldSetting.objects.get_or_create(form_key='lease_income_statement',field_key='ui',defaults={'label':'Lease income statement','option_labels':options})
        merged=dict(row.option_labels)
        for key,value in options.items():merged.setdefault(key,value)
        if merged!=row.option_labels:row.option_labels=merged;row.save(update_fields=['option_labels'])
        self.stdout.write(self.style.SUCCESS('Lease income-statement settings initialized. No transactions changed.'))
