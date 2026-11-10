"""Native invoice entry and its required accounting metadata."""
from django import forms
from django.core.exceptions import ValidationError
from accounting.models import ChartAccount
from accounting.book_models import BillAccounting, BookPosting
from common.models import FormFieldSetting
from .forms import VendorInvoiceForm

FORM_KEY = 'vendor_invoice_accounting'
FIELD_DEFAULTS = {
    'expense_account': ('Expense account', 'Select the active expense account that describes this work.'),
    'service_start': ('Service period start', 'First day covered by this invoice.'),
    'service_end': ('Service period end', 'Last day covered by this invoice.'),
    'recognition_date': ('Recognition date', 'Date this expense is recognized in accrual reports. Cash reports use the payment date.'),
}
UI_DEFAULTS = {
    'heading': 'Accounting details',
    'missing': 'Accounting details have not been recorded.',
    'locked': 'Posted invoice accounting details cannot be changed.',
    'status_locked': 'Only a submitted invoice can be edited.',
    'required': 'Complete the invoice accounting details before approval.',
    'period_order': 'Service period end cannot precede its start.',
}

def wording():
    row = FormFieldSetting.objects.filter(form_key=FORM_KEY, field_key='ui').first()
    return {**UI_DEFAULTS, **(row.option_labels if row else {})}

class NativeVendorInvoiceForm(VendorInvoiceForm):
    expense_account = forms.ModelChoiceField(queryset=ChartAccount.objects.none())
    service_start = forms.DateField(widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    service_end = forms.DateField(widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    recognition_date = forms.DateField(widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.accounting_ui = wording()
        settings = {row.field_key: row for row in FormFieldSetting.objects.filter(form_key=FORM_KEY)}
        self.fields['expense_account'].queryset = ChartAccount.objects.filter(is_active=True, account_type='expense').order_by('code', 'name')
        details = BillAccounting.objects.filter(invoice_id=self.instance.pk).first() if self.instance.pk else None
        self.posted = bool(self.instance.pk and BookPosting.objects.filter(source_key='bill:' + str(self.instance.pk)).exists())
        for name, (label, help_text) in FIELD_DEFAULTS.items():
            row = settings.get(name)
            self.fields[name].label = row.label if row else label
            self.fields[name].help_text = row.help_text if row else help_text
            if row:
                self.fields[name].error_messages.update(row.error_messages or {})
            self.fields[name].widget.attrs['class'] = 'form-control'
            if details:
                self.initial[name] = getattr(details, name + '_id' if name == 'expense_account' else name)
        if self.posted or (self.instance.pk and self.instance.status != 'submitted'):
            for field in self.fields.values():
                field.disabled = True

    @property
    def accounting_fields(self):
        return [self[name] for name in FIELD_DEFAULTS]

    def clean(self):
        cleaned = super().clean()
        if self.posted:
            raise ValidationError(self.accounting_ui['locked'])
        if self.instance.pk and self.instance.status != 'submitted':
            raise ValidationError(self.accounting_ui['status_locked'])
        start, end = cleaned.get('service_start'), cleaned.get('service_end')
        if start and end and end < start:
            self.add_error('service_end', self.accounting_ui['period_order'])
        return cleaned

    def save_accounting(self, invoice):
        # The provider holds the invoice row lock and the encompassing transaction.
        if BookPosting.objects.filter(source_key='bill:' + str(invoice.pk)).exists():
            raise ValidationError(self.accounting_ui['locked'])
        details = BillAccounting.objects.filter(invoice=invoice).first() or BillAccounting(invoice=invoice)
        for name in FIELD_DEFAULTS:
            setattr(details, name, self.cleaned_data[name])
        details.full_clean()
        details.save()
        return details
