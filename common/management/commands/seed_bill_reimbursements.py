from django.core.management.base import BaseCommand
from common.models import FormFieldSetting

UI = {
    'title': 'Record payment made on behalf', 'reimburse_title': 'Record reimbursement',
    'explanation': 'Record a vendor payment already made by another party. No property bank is reduced. The advance remains payable until reimbursed. Cash management reports recognize the expense on the vendor payment date; accrual reports use the service recognition date.',
    'reimburse_explanation': 'Record an actual reimbursement to the advancing party. This clears the payable and reduces the selected bank; it does not create another expense.',
    'remaining': 'Reimbursement outstanding', 'bank_payment': 'Pay from a property bank',
    'configure': 'Configure reimbursement payers', 'cancel': 'Cancel', 'save': 'Record payment',
    'reimburse': 'Record reimbursement', 'expired': 'The form expired. Reload and review before submitting.',
    'saved': 'Vendor payment recorded. Reimbursement remains outstanding.', 'reimbursed': 'Reimbursement recorded; no additional expense created.',
    'heading': 'Payments made on behalf & reimbursements', 'payer': 'Paid on behalf by',
    'payment_date': 'Vendor payment date', 'amount': 'Amount ($)', 'repaid': 'Reimbursed',
    'actions': 'Actions', 'repayment': 'Reimbursement', 'reason': 'Reason for correction',
    'void': 'Void reimbursement', 'source_action': 'Paid on behalf — reimbursement due',
}
FIELDS = {
    'payer': ('Paid on behalf by', 'Select the party that advanced its own funds. Configure the party and its liability account in Portal Settings.'),
    'amount': ('Amount ($)', 'Actual amount paid to the vendor, not an estimate.'),
    'payment_date': ('Vendor payment date', 'Actual date the vendor received payment, including an earlier card charge date.'),
    'payment_method': ('Payment method', 'How the advancing party paid the vendor. Its card is not a property bank account.'),
    'reference': ('Transaction reference', 'Receipt or transaction confirmation identifying this payment.'),
    'expense_account': ('Expense account', 'Active expense account for this bill. Reimbursement does not create another expense.'),
    'service_start': ('Service period from', 'First day of the service covered by this bill.'),
    'service_end': ('Service period through', 'Last day of the service covered by this bill.'),
    'recognition_date': ('Accrual recognition date', 'Date the expense was incurred. An earlier on-behalf payment is held in the configured prepaid account until this date in accrual books.'),
    'date': ('Reimbursement date', 'Actual date money was returned to the advancing party.'),
    'bank': ('Reimbursement paid from', 'Select the actual authorized bank used, within the property accounting entity.'),
    'notes': ('Notes', 'Optional supporting detail. Notes do not replace transaction fields.'),
}

class Command(BaseCommand):
    def handle(self, *args, **options):
        row, created = FormFieldSetting.objects.get_or_create(form_key='bill_reimbursement', field_key='ui', defaults={'label': 'Bill reimbursements', 'option_labels': UI})
        if not created:
            row.option_labels = {**UI, **row.option_labels}; row.save(update_fields=['option_labels'])
        for key, (label, help_text) in FIELDS.items():
            FormFieldSetting.objects.get_or_create(form_key='bill_reimbursement', field_key=key, defaults={'label': label, 'help_text': help_text})
        for key, label in [('payers', 'Reimbursement payers'), ('reimbursements', 'Reimbursements payable')]:
            form_key = 'portal_settings' if key == 'payers' else 'accounting_books'
            row = FormFieldSetting.objects.filter(form_key=form_key, field_key='ui').first()
            if row:
                row.option_labels = {key: label, **row.option_labels}; row.save(update_fields=['option_labels'])
        for key, label, help_text in [
            ('liability_account', 'Reimbursement liability account', 'Choose a distinct liability account for advances owed to this payer. Do not use tenant deposits, rent credits or vendor accounts payable.'),
            ('prepaid_account', 'Prepaid expense account', 'Choose a non-bank asset account used when a vendor payment precedes accrual recognition.')]:
            FormFieldSetting.objects.get_or_create(form_key='portal_settings', field_key=key, defaults={'label': label, 'help_text': help_text})
        self.stdout.write('Reimbursement settings ready. No business parties, accounts or payments created.')
