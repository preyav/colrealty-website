from django.core.management.base import BaseCommand
from common.models import FormFieldSetting

class Command(BaseCommand):
    help = 'Initialize editable rent entry action wording without overwriting existing settings.'
    def handle(self, *args, **kwargs):
        groups = {
            'rent_ledger': {'edit':'Edit entry','delete':'Delete entry','edit_help':'Correct the entry and provide a reason. Existing payment allocations are retained. Delete voids an entry and retains its history.',
                'edit_stale':'This entry changed or the form expired. Reload before editing.',
                'edit_allocated':'The amount cannot be less than the payment already allocated. Review the allocations or void the payment first.'},
            'lease_financials': {'edit':'Edit','delete':'Delete'},
        }
        for form_key, values in groups.items():
            row = FormFieldSetting.objects.get(form_key=form_key, field_key='ui')
            labels = dict(row.option_labels)
            for key, value in values.items():
                labels.setdefault(key, value)
            row.option_labels = labels
            row.save(update_fields=['option_labels'])
        self.stdout.write(self.style.SUCCESS('Rent entry actions initialized.'))
