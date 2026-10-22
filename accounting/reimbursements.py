"""Reviewed settlements: pay the vendor once; reimburse the advancing party separately."""
from decimal import Decimal, InvalidOperation
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from common.audit.services import record_event
from .book_models import BillAccounting, BookPosting
from .reimbursement_models import ReimbursementPayer, OnBehalfSettlement, BillReimbursement
from .book_services import books_for, bank_account, _book, post_bill, snapshot, reverse_source


def authorize(actor, permission):
    if not actor or not actor.is_active or not actor.is_staff or not actor.has_perm(permission):
        raise PermissionDenied


def money(value):
    try:
        value = Decimal(str(value))
        if not value.is_finite() or value <= 0 or value != value.quantize(Decimal('.01')):
            raise ValueError
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError('Enter a positive amount with at most two decimal places.')
    return value


@transaction.atomic
def post_on_behalf(payment, actor):
    from .general_ledger import staff
    staff(actor)
    settlement = OnBehalfSettlement.objects.select_related('payer').get(payment=payment)
    invoice = payment.invoice
    config = books_for(invoice.work_order.unit.property_id)
    payer = ReimbursementPayer.objects.select_for_update().get(pk=settlement.payer_id)
    if payer.entity_id != config.entity_id or payment.financial_account_id:
        raise ValidationError('Payer and property books must match; an on-behalf payment cannot use a property bank.')
    if payment.status != 'recorded' or payment.payment_date > timezone.localdate():
        raise ValidationError('Only recorded, non-future payments can be posted.')
    payer.full_clean()
    post_bill(invoice, actor)
    details = invoice.book_details
    source = {**snapshot(payment, ['amount', 'payment_date', 'invoice_id', 'financial_account_id', 'payment_method', 'reference_number']),
              **snapshot(payer, ['entity_id', 'liability_account_id', 'prepaid_account_id']), 'payer_id': str(payer.pk)}
    if invoice.outstanding_amount < 0 or invoice.paid_amount > invoice.amount:
        raise ValidationError('Bill payments or credits exceed the invoice; review before posting.')
    key = 'bill-payment:' + str(payment.pk)
    memo = f'Vendor payment advanced by {payer.name}: {invoice.invoice_number or invoice.pk}'
    _book(config, 'cash', key, payment.payment_date,
          [(details.expense_account, payment.amount), (payer.liability_account, -payment.amount)], actor, source, memo, invoice.work_order.unit)
    early = payment.payment_date < details.recognition_date
    target = payer.prepaid_account if early else config.payable
    _book(config, 'accrual', key, payment.payment_date,
          [(target, payment.amount), (payer.liability_account, -payment.amount)], actor, source, memo, invoice.work_order.unit)
    if early:
        _book(config, 'accrual', key + ':service', details.recognition_date,
              [(config.payable, payment.amount), (payer.prepaid_account, -payment.amount)], actor, source, memo, invoice.work_order.unit)


@transaction.atomic
def record_on_behalf(invoice_id, data, token, actor):
    from maintenance.models import VendorInvoice, VendorPayment
    authorize(actor, 'maintenance.add_vendorpayment')
    invoice = VendorInvoice.objects.select_for_update().select_related('work_order__unit__property').get(pk=invoice_id)
    config = books_for(invoice.work_order.unit.property_id)
    previous = OnBehalfSettlement.objects.filter(token=token).select_related('payment').first()
    if previous:
        if previous.payment.invoice_id != invoice.pk:
            raise ValidationError('This submission belongs to another invoice.')
        return previous
    if invoice.status not in ['approved', 'partially_paid'] or invoice.fund_events.exists():
        raise ValidationError('Use an approved bill with a balance due and no unresolved credit/refund events.')
    amount = money(data['amount'])
    if amount > invoice.outstanding_amount:
        raise ValidationError('Payment exceeds the remaining bill balance.')
    date = data['payment_date']
    if date > timezone.localdate() or (invoice.invoice_date and date < invoice.invoice_date):
        raise ValidationError('Use the actual payment date, on or after the invoice date and not in the future.')
    if not data['reference'].strip():
        raise ValidationError('Enter the payment confirmation or transaction reference.')
    from maintenance.models import VendorPayment
    if data['payment_method'] not in dict(VendorPayment.METHOD_CHOICES):
        raise ValidationError('Choose a valid payment method.')
    payer = ReimbursementPayer.objects.select_for_update().get(pk=data['payer'].pk)
    if not payer.is_active or payer.entity_id != config.entity_id:
        raise ValidationError('Select an active payer for these property books.')
    # Posting details are supplied explicitly; never infer service dates from completion.
    details = BillAccounting.objects.filter(invoice=invoice).first()
    proposed = {key: data[key] for key in ['expense_account', 'service_start', 'service_end', 'recognition_date']}
    if details:
        for key, value in proposed.items():
            if getattr(details, key) != value:
                raise ValidationError('Bill accounting details already exist. Retain their original values.')
    else:
        details = BillAccounting(invoice=invoice, **proposed)
        details.full_clean(); details.save()
    payment = VendorPayment(invoice=invoice, amount=amount, payment_date=date,
                            payment_method=data['payment_method'], reference_number=data['reference'].strip(),
                            payment_account=payer.name, financial_account=None, notes=data.get('notes', ''), recorded_by=actor)
    payment.full_clean(); payment.save()
    settlement = OnBehalfSettlement.objects.create(token=token, payment=payment, payer=payer)
    invoice.status = 'paid' if invoice.outstanding_amount == 0 else 'partially_paid'
    invoice.paid_at = timezone.now() if invoice.status == 'paid' else None
    invoice.save(update_fields=['status', 'paid_at', 'updated_at'])
    post_on_behalf(payment, actor)
    record_event(action='VENDOR_PAYMENT_ON_BEHALF', instance=payment, actor=actor,
                 property_id=config.property_id, new_values={'amount': str(amount), 'payment_date': str(date), 'payer_id': payer.pk,
                 'reimbursement_outstanding': str(amount), 'reference': payment.reference_number}, reason='Vendor paid by an advancing party; reimbursement remains due.')
    return settlement


@transaction.atomic
def reimburse(settlement_id, data, token, actor):
    authorize(actor, 'accounting.add_billreimbursement')
    from maintenance.models import VendorInvoice
    invoice_id = OnBehalfSettlement.objects.values_list('payment__invoice_id', flat=True).get(pk=settlement_id)
    VendorInvoice.objects.select_for_update().get(pk=invoice_id)
    property_id = VendorInvoice.objects.values_list('work_order__unit__property_id', flat=True).get(pk=invoice_id)
    config = books_for(property_id)
    settlement = OnBehalfSettlement.objects.select_for_update(of=('self',)).select_related('payment__invoice__work_order__unit', 'payer').get(pk=settlement_id)
    previous = BillReimbursement.objects.filter(token=token).first()
    if previous:
        if previous.settlement_id != settlement.pk:
            raise ValidationError('Submission belongs to another reimbursement.')
        return previous
    if settlement.payment.status != 'recorded':
        raise ValidationError('Cannot reimburse a void payment.')
    amount = money(data['amount']); date = data['date']
    if amount > settlement.outstanding:
        raise ValidationError('Reimbursement exceeds the amount still owed.')
    if date < settlement.payment.payment_date or date > timezone.localdate():
        raise ValidationError('Reimbursement must be on or after the original payment, and not in the future.')
    if not data['reference'].strip():
        raise ValidationError('Enter the reimbursement transaction reference.')
    post_on_behalf(settlement.payment, actor)
    bank = bank_account(config, data['bank'])
    row = BillReimbursement(token=token, settlement=settlement, amount=amount, date=date, bank=data['bank'],
                            reference=data['reference'].strip(), notes=data.get('notes', ''), created_by=actor)
    row.full_clean(); row.save()
    source = snapshot(row, ['amount', 'date', 'bank_id', 'settlement_id', 'reference'])
    for basis in ['cash', 'accrual']:
        _book(config, basis, 'bill-reimbursement:' + str(row.pk), date,
              [(settlement.payer.liability_account, amount), (bank, -amount)], actor, source,
              'Reimbursement to ' + settlement.payer.name, settlement.payment.invoice.work_order.unit)
    record_event(action='BILL_REIMBURSEMENT_RECORDED', instance=row, actor=actor, property_id=config.property_id,
                 new_values=source, reason='Reimbursement clears the advance; no additional expense.')
    return row


@transaction.atomic
def void_reimbursement(row_id, reason, actor):
    authorize(actor, 'accounting.change_billreimbursement')
    from maintenance.models import VendorInvoice
    invoice_id = BillReimbursement.objects.values_list('settlement__payment__invoice_id', flat=True).get(pk=row_id)
    invoice = VendorInvoice.objects.select_for_update().select_related('work_order__unit').get(pk=invoice_id)
    config = books_for(invoice.work_order.unit.property_id)
    row = BillReimbursement.objects.select_related('settlement__payment__invoice__work_order__unit').get(pk=row_id)
    OnBehalfSettlement.objects.select_for_update().get(pk=row.settlement_id)
    row = BillReimbursement.objects.select_for_update(of=('self',)).select_related('settlement__payment__invoice__work_order__unit').get(pk=row_id)
    if not reason.strip():
        raise ValidationError('Enter a reason for voiding the reimbursement.')
    if row.status == 'void':
        return row
    reverse_source(config, ['bill-reimbursement:' + str(row.pk)], timezone.localdate(), reason, actor)
    row.status = 'void'; row.voided_by = actor; row.voided_at = timezone.now(); row.void_reason = reason.strip()
    row._reviewed_void = True
    row.save(update_fields=['status', 'voided_by', 'voided_at', 'void_reason'])
    record_event(action='BILL_REIMBURSEMENT_VOIDED', instance=row, actor=actor, property_id=config.property_id,
                 new_values={'status': 'void'}, reason=reason)
    return row
