import uuid
from django import forms
from common.models import FormFieldSetting
from leasing.models import Lease
from .book_models import AccountingEntity,PropertyBooks,EntityBank,FundsEvent
from .models import FinancialAccount
from .rent_models import RentCharge,RentReceipt
from .bank_services import bank_lines

class FundsForm(forms.ModelForm):
    token=forms.UUIDField(widget=forms.HiddenInput)
    class Meta:
        model=FundsEvent
        fields=['property','lease','kind','date','amount','bank','source','receipt','charge','invoice','reference','notes']
        widgets={'date':forms.DateInput(attrs={'type':'date'}),'notes':forms.Textarea(attrs={'rows':2})}
    def __init__(self,*args,entity=None,**kwargs):
        super().__init__(*args,**kwargs)
        props=PropertyBooks.objects.filter(enabled=True)
        if entity:props=props.filter(entity=entity)
        ids=list(props.values_list('property_id',flat=True))
        self.fields['property'].queryset=self.fields['property'].queryset.filter(pk__in=ids)
        self.fields['lease'].queryset=Lease.objects.filter(unit__property_id__in=ids)
        self.fields['source'].queryset=FundsEvent.objects.filter(property_id__in=ids,kind__in=['deposit_in','credit_to_deposit','advance_in'])
        self.fields['receipt'].queryset=RentReceipt.objects.filter(lease__unit__property_id__in=ids,status='recorded')
        self.fields['charge'].queryset=RentCharge.objects.filter(lease__unit__property_id__in=ids,status='posted')
        self.fields['invoice'].queryset=self.fields['invoice'].queryset.filter(work_order__unit__property_id__in=ids).exclude(status='void')
        self.fields['bank'].queryset=FinancialAccount.objects.filter(entity_book__entity__in=props.values('entity_id'),is_active=True).exclude(kind='credit_card')
        rows={r.field_key:r for r in FormFieldSetting.objects.filter(form_key='accounting_books')}
        for name,field in self.fields.items():
            if name in rows:field.label=rows[name].label;field.help_text=rows[name].help_text
        if 'event_kinds' in rows:self.fields['kind'].choices=list(rows['event_kinds'].option_labels.items())

class ReconcileForm(forms.Form):
    bank=forms.ModelChoiceField(queryset=EntityBank.objects.none())
    statement_start=forms.DateField(widget=forms.DateInput(attrs={'type':'date'}))
    statement_end=forms.DateField(widget=forms.DateInput(attrs={'type':'date'}))
    opening_balance=forms.DecimalField(max_digits=14,decimal_places=2)
    closing_balance=forms.DecimalField(max_digits=14,decimal_places=2)
    lines=forms.MultipleChoiceField(required=False,widget=forms.CheckboxSelectMultiple)
    def __init__(self,*args,entity=None,**kwargs):
        super().__init__(*args,**kwargs)
        banks=EntityBank.objects.all()
        if entity:banks=banks.filter(entity=entity)
        self.fields['bank'].queryset=banks
        bank_id=self.data.get('bank') if self.is_bound else None
        bank=banks.filter(pk=bank_id).first() if bank_id and str(bank_id).isdigit() else None
        from django.utils import timezone
        self.fields['lines'].choices=[(str(line.pk),f'{line.journal.date} · {line.journal.memo} · {line.debit-line.credit}') for line in bank_lines(bank,timezone.localdate()).filter(bank_clearance__isnull=True)] if bank else []
        rows={r.field_key:r for r in FormFieldSetting.objects.filter(form_key='accounting_books')}
        for name,field in self.fields.items():
            if name in rows:field.label=rows[name].label;field.help_text=rows[name].help_text
