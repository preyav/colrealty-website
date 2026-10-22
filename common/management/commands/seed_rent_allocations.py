from django.core.management.base import BaseCommand
from common.models import FormFieldSetting
DEFAULTS={
 'action':'Edit allocations','title':'Payment allocations','help':'Expand each payment and enter amounts against the rent periods it covers. Zero clears an allocation. Save all changes together. Unapplied amounts remain tenant credit. Payment dates and bank accounts are unchanged. Posted accounting or client-funds activity requires a separate accounting correction.',
 'period':'Rent period','amount':'Amount applied ($)','credit':'Unapplied credit ($)',
 'reason':'Reason for correction','save':'Save allocations','cancel':'Cancel',
 'saved':'Payment allocations saved.','stale':'Records changed or this form expired. Reload and review again.',
 'reason_required':'Enter a reason for the correction.','invalid':'Enter valid nonnegative amounts with at most two decimal places for this lease.',
 'overallocated':'Allocations exceed a payment amount or a rent charge. Adjust the amounts before saving.',
 'locked':'This property has accounting postings or this lease has client-funds activity. Allocation changes require a reviewed accounting correction.'}
class Command(BaseCommand):
    def handle(self,*args,**options):
        row,created=FormFieldSetting.objects.get_or_create(form_key='rent_allocations',field_key='ui',defaults={'label':'Payment allocations','option_labels':DEFAULTS})
        if not created:
            row.option_labels={**DEFAULTS,**row.option_labels};row.save(update_fields=['option_labels'])
        self.stdout.write('Payment allocation settings ready.')
