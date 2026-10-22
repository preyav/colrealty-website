"""On-behalf payments use the existing bill workspace, with signed retry tokens."""
import uuid
from decimal import Decimal
from django import forms
from django.core import signing
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from common.models import FormFieldSetting
from maintenance.models import VendorInvoice, VendorPayment
from accounting.models import ChartAccount, FinancialAccount
from accounting.book_models import PropertyBooks, BillAccounting
from accounting.reimbursement_models import ReimbursementPayer, OnBehalfSettlement, BillReimbursement
from accounting.reimbursements import authorize, record_on_behalf, reimburse, void_reimbursement


def wording():
    return FormFieldSetting.objects.get(form_key='bill_reimbursement', field_key='ui').option_labels


class SettlementForm(forms.Form):
    payer = forms.ModelChoiceField(queryset=ReimbursementPayer.objects.none())
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('.01'))
    payment_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    payment_method = forms.ChoiceField(choices=VendorPayment.METHOD_CHOICES)
    reference = forms.CharField(max_length=150)
    expense_account = forms.ModelChoiceField(queryset=ChartAccount.objects.none())
    service_start = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    service_end = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    recognition_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, invoice, **kwargs):
        super().__init__(*args, **kwargs)
        config = PropertyBooks.objects.filter(property_id=invoice.work_order.unit.property_id, enabled=True).first()
        self.fields['payer'].queryset = ReimbursementPayer.objects.filter(entity=config.entity, is_active=True) if config else ReimbursementPayer.objects.none()
        self.fields['expense_account'].queryset = ChartAccount.objects.filter(is_active=True, account_type='expense').order_by('code')
        details = BillAccounting.objects.filter(invoice=invoice).first()
        if details:
            for key in ['expense_account', 'service_start', 'service_end', 'recognition_date']:
                self.initial[key] = getattr(details, key); self.fields[key].disabled = True
        configure_fields(self)


class ReimburseForm(forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('.01'))
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    bank = forms.ModelChoiceField(queryset=FinancialAccount.objects.none())
    reference = forms.CharField(max_length=180)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, settlement, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['bank'].queryset = FinancialAccount.objects.filter(is_active=True, entity_book__entity=settlement.payer.entity).exclude(kind='credit_card')
        configure_fields(self)


def configure_fields(form):
    rows = {r.field_key: r for r in FormFieldSetting.objects.filter(form_key='bill_reimbursement')}
    for name, field in form.fields.items():
        field.widget.attrs['class'] = 'form-control'
        if name in rows:
            field.label = rows[name].label; field.help_text = rows[name].help_text
            if name == 'payment_method' and rows[name].option_labels:
                field.choices = [(key, rows[name].option_labels.get(key, label)) for key, label in field.choices]


def signed_token(request, kind, pk):
    if request.method == 'GET':
        return signing.dumps({'kind': kind, 'pk': pk, 'token': str(uuid.uuid4())}, salt='bill-reimbursement')
    return request.POST.get('version', '')


def decode_token(version, kind, pk):
    value = signing.loads(version, salt='bill-reimbursement', max_age=3600)
    if value.get('kind') != kind or value.get('pk') != pk:
        raise signing.BadSignature
    return uuid.UUID(value['token'])


@login_required(login_url='/accounts/login/')
@require_http_methods(['GET', 'POST'])
def on_behalf_payment(request, invoice_id):
    authorize(request.user, 'maintenance.add_vendorpayment')
    invoice = get_object_or_404(VendorInvoice.objects.select_related('work_order__unit__property'), pk=invoice_id)
    from financial.services import get_financial_provider
    if get_financial_provider().key != 'col360':
        raise PermissionDenied('On-behalf payments require the native COL360 provider.')
    form = SettlementForm(request.POST or None, invoice=invoice, initial={'amount': invoice.outstanding_amount})
    version = signed_token(request, 'payment', invoice.pk)
    if request.method == 'POST' and form.is_valid():
        try:
            token = decode_token(version, 'payment', invoice.pk)
            record_on_behalf(invoice.pk, form.cleaned_data, token, request.user)
        except signing.BadSignature:
            form.add_error(None, wording()['expired'])
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        else:
            messages.success(request, wording()['saved'])
            return redirect('portal:finance_vendor_invoice_detail', invoice_id=invoice.pk)
    return render(request, 'portal/bill_reimbursement_form.html', {'form': form, 'version': version, 'invoice': invoice, 'ui': wording(), 'is_settlement': True, 'section': 'finance'})


@login_required(login_url='/accounts/login/')
@require_http_methods(['GET', 'POST'])
def bill_reimbursement(request, settlement_id):
    authorize(request.user, 'accounting.add_billreimbursement')
    settlement = get_object_or_404(OnBehalfSettlement.objects.select_related('payment__invoice', 'payer'), pk=settlement_id)
    form = ReimburseForm(request.POST or None, settlement=settlement, initial={'amount': settlement.outstanding, 'date': timezone.localdate()})
    version = signed_token(request, 'reimburse', settlement.pk)
    if request.method == 'POST' and form.is_valid():
        try:
            token = decode_token(version, 'reimburse', settlement.pk)
            reimburse(settlement.pk, form.cleaned_data, token, request.user)
        except signing.BadSignature:
            form.add_error(None, wording()['expired'])
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        else:
            messages.success(request, wording()['reimbursed'])
            return redirect('portal:finance_vendor_invoice_detail', invoice_id=settlement.payment.invoice_id)
    return render(request, 'portal/bill_reimbursement_form.html', {'form': form, 'version': version, 'invoice': settlement.payment.invoice, 'settlement': settlement, 'ui': wording(), 'section': 'finance'})


@login_required(login_url='/accounts/login/')
@require_http_methods(['POST'])
def bill_reimbursement_void(request, reimbursement_id):
    authorize(request.user, 'accounting.change_billreimbursement')
    row = get_object_or_404(BillReimbursement, pk=reimbursement_id)
    try:
        void_reimbursement(row.pk, request.POST.get('reason', ''), request.user)
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages))
    return redirect('portal:finance_vendor_invoice_detail', invoice_id=row.settlement.payment.invoice_id)
