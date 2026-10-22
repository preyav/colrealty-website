from django.core.management.base import BaseCommand
from common.models import FormFieldSetting

DEFAULTS = {
    'customize': 'Customize rows', 'hide_empty': 'Hide accounts without activity',
    'income': 'Income', 'expense': 'Expenses', 'save': 'Apply display',
    'show_all': 'Show all accounts', 'select_all': 'Select all', 'select_none': 'Clear selection',
    'hidden_activity': 'Accounts with activity are hidden. Totals and their detail links still include all applicable transactions.',
    'hidden_empty': 'Accounts without activity hidden', 'selected': 'selected',
    'help': 'Choose the income and expense rows to display. Your choices are remembered across property income statements for your login. Totals remain complete, including hidden rows. Accounts with transactions remain visible under the activity filter even when their net amount is zero.',
    'default_hide_empty': '1', 'saved': 'Income statement display preferences saved.',
}

class Command(BaseCommand):
    def handle(self, *args, **options):
        row, created = FormFieldSetting.objects.get_or_create(form_key='income_statement_rows', field_key='ui', defaults={'label': 'Income statement row display', 'option_labels': DEFAULTS})
        if not created:
            row.option_labels = {**DEFAULTS, **row.option_labels}; row.save(update_fields=['option_labels'])
        self.stdout.write('Income statement display settings ready. Accounts and transactions unchanged.')
