"""Explicit dual-basis posting adapters. No historical sources are auto-imported."""
import uuid
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from common.audit.services import record_event
from .book_models import PropertyBooks,EntityBank,BookPosting,FundsEvent,BillAccounting
from .journal_models import JournalLine
from .general_ledger import post_journal,reverse_journal,staff

ZERO=Decimal('0.00')

def snapshot(instance,fields):
    return {key:(format(getattr(instance,key),'.2f') if isinstance(getattr(instance,key),Decimal) else str(getattr(instance,key))) for key in fields}

def books_for(property_id):
    config=PropertyBooks.objects.select_for_update().select_related('entity','property').get(property_id=property_id)
    if not config.enabled or not config.entity.is_active:raise ValidationError('Property accounting is not enabled.')
    config.full_clean()
    return config

def bank_account(config,bank):
    if not bank or not bank.is_active or bank.kind=='credit_card' or bank.ledger_account.account_type!='asset':raise ValidationError('Select an active bank or cash account.')
    if not EntityBank.objects.filter(entity=config.entity,bank=bank).exists():raise ValidationError('The bank account belongs to another or unconfigured accounting entity.')
    return bank.ledger_account

def source_posted(prefix):
    from django.db.models import Q
    return BookPosting.objects.filter(Q(source_key=prefix)|Q(source_key__startswith=prefix+':')).exists()

def _book(config,basis,key,date,lines,actor,source,memo,unit=None):
    previous=BookPosting.objects.filter(entity=config.entity,basis=basis,source_key=key).first()
    if previous:
        if previous.snapshot!=source:raise ValidationError('This source has changed after posting. Review and reverse it before correcting the books.')
        return previous
    from .book_models import BankReconciliation
    bank_ids=[account.pk for account,amount in lines if hasattr(account,'financial_account')]
    list(EntityBank.objects.select_for_update().filter(entity=config.entity,bank__ledger_account_id__in=bank_ids).order_by('pk'))
    if basis=='cash' and BankReconciliation.objects.filter(entity_bank__entity=config.entity,entity_bank__bank__ledger_account_id__in=bank_ids,status='final',statement_end__gte=date).exists():raise ValidationError('This bank period is finalized. Use an open-period correction.')
    fund_types={account.fund_type for account,amount in lines if account.fund_type}
    if len(fund_types)>1:raise ValidationError('Posting accounts have conflicting fund types.')
    journal=post_journal({'date':date,'memo':memo,'property':config.property,'unit':unit,'fund_type':next(iter(fund_types),''),'book_future':True},
        [{'account':account,'debit':max(amount,ZERO),'credit':max(-amount,ZERO)} for account,amount in lines if amount],
        uuid.uuid5(uuid.NAMESPACE_URL,f'col360-book:{config.entity_id}:{basis}:{key}'),actor,book_internal=True)
    return BookPosting.objects.create(journal=journal,entity=config.entity,basis=basis,source_key=key,snapshot=source)

@transaction.atomic
def post_rent_charge(charge,actor):
    staff(actor)
    from .rent_services import _lock
    _lock(charge.lease_id)
    charge=type(charge).objects.select_related('lease__unit__property').get(pk=charge.pk)
    config=books_for(charge.lease.unit.property_id)
    if charge.status!='posted':raise ValidationError('Only live rent charges can be posted.')
    source=snapshot(charge,['amount','period_start','period_end','due_date','lease_id'])
    from .charge_items import income_lines
    if charge.income_items:source['income_items']=charge.income_items
    return _book(config,'accrual','rent-charge:'+str(charge.pk),charge.period_start,
        [(config.receivable,charge.amount)]+[(a,-v) for a,v in income_lines(charge,config)],actor,source,str(charge),charge.lease.unit)

def _receipt_allocation(config,receipt,allocation,actor):
    charge=allocation.charge
    post_rent_charge(charge,actor)
    source={'receipt':str(receipt.pk),'charge':str(charge.pk),'amount':format(allocation.amount,'.2f'),'date':str(receipt.received_date)}
    # Receipt is first held as a client credit. Cash income is recognized on receipt.
    key='rent-allocation:'+str(allocation.pk)
    from .charge_items import income_lines
    prior=charge.allocations.filter(pk__lt=allocation.pk,receipt__status='recorded').aggregate(total=Sum('amount'))['total'] or ZERO
    if charge.income_items:source['income_items']=charge.income_items
    _book(config,'cash',key,receipt.received_date,[(config.credits,allocation.amount)]+[(a,-v) for a,v in income_lines(charge,config,allocation.amount,prior)],actor,source,str(receipt),receipt.lease.unit)
    target=config.advances if receipt.received_date<charge.period_start else config.receivable
    _book(config,'accrual',key,receipt.received_date,[(config.credits,allocation.amount),(target,-allocation.amount)],actor,source,str(receipt),receipt.lease.unit)
    if target.pk==config.advances_id:
        _book(config,'accrual',key+':earned',charge.period_start,[(config.advances,allocation.amount),(config.receivable,-allocation.amount)],actor,source,str(charge),receipt.lease.unit)

@transaction.atomic
def post_rent_receipt(receipt,actor):
    staff(actor)
    from .rent_services import _lock
    _lock(receipt.lease_id)
    receipt=type(receipt).objects.select_related('lease__unit__property','financial_account').get(pk=receipt.pk)
    config=books_for(receipt.lease.unit.property_id)
    if receipt.received_date>timezone.localdate():raise ValidationError('Future receipts cannot be posted.')
    if receipt.status!='recorded':raise ValidationError('Only live payments can be posted.')
    bank=bank_account(config,receipt.financial_account)
    source=snapshot(receipt,['amount','received_date','lease_id','financial_account_id','payment_method','reference'])
    for basis in ['cash','accrual']:
        _book(config,basis,'rent-receipt:'+str(receipt.pk),receipt.received_date,[(bank,receipt.amount),(config.credits,-receipt.amount)],actor,source,str(receipt),receipt.lease.unit)
    for allocation in receipt.allocations.select_related('charge').all():_receipt_allocation(config,receipt,allocation,actor)

@transaction.atomic
def post_bill(invoice,actor):
    staff(actor);config=books_for(invoice.work_order.unit.property_id)
    invoice=type(invoice).objects.select_for_update().select_related('work_order__unit__property').get(pk=invoice.pk)
    if invoice.status not in ('approved','partially_paid','paid'):raise ValidationError('Approve the bill before posting it.')
    try:details=invoice.book_details
    except BillAccounting.DoesNotExist as exc:raise ValidationError('Set the bill service period, recognition date and expense account first.') from exc
    details.full_clean()
    source={**snapshot(invoice,['amount','invoice_date','due_date','vendor_id']),**snapshot(details,['service_start','service_end','recognition_date','expense_account_id'])}
    return _book(config,'accrual','bill:'+str(invoice.pk),details.recognition_date,[(details.expense_account,invoice.amount),(config.payable,-invoice.amount)],actor,source,str(invoice),invoice.work_order.unit)

@transaction.atomic
def post_bill_payment(payment,actor):
    staff(actor);invoice=payment.invoice;config=books_for(invoice.work_order.unit.property_id)
    payment=type(payment).objects.select_for_update(of=('self',)).select_related('invoice__work_order__unit__property','financial_account').get(pk=payment.pk)
    invoice=payment.invoice
    if payment.payment_date>timezone.localdate():raise ValidationError('Future payments cannot be posted.')
    if payment.status!='recorded':raise ValidationError('Only live bill payments can be posted.')
    from .reimbursement_models import OnBehalfSettlement
    if OnBehalfSettlement.objects.filter(payment=payment).exists():
        from .reimbursements import post_on_behalf
        return post_on_behalf(payment,actor)
    post_bill(invoice,actor);bank=bank_account(config,payment.financial_account)
    details=invoice.book_details
    if payment.payment_date<details.recognition_date:raise ValidationError('Prepaid vendor expenses need a prepaid-asset schedule; this payment cannot be treated as an incurred bill.')
    if invoice.outstanding_amount<0 and not source_posted('bill-payment:'+str(payment.pk)):raise ValidationError('Payment exceeds the remaining bill after credits; review the vendor credit/refund first.')
    if invoice.paid_amount>invoice.amount:raise ValidationError('Bill payments exceed the bill amount.')
    source=snapshot(payment,['amount','payment_date','invoice_id','financial_account_id'])
    for basis,account in [('cash',details.expense_account),('accrual',config.payable)]:
        _book(config,basis,'bill-payment:'+str(payment.pk),payment.payment_date,[(account,payment.amount),(bank,-payment.amount)],actor,source,str(payment),invoice.work_order.unit)

@transaction.atomic
def reverse_source(config,prefixes,date,reason,actor):
    staff(actor)
    # Call from the same transaction that voids the operational source.
    books_for(config.property_id)
    for posting in BookPosting.objects.filter(entity=config.entity,journal__property_id=config.property_id).select_related('journal'):
        if not any(posting.source_key==prefix or posting.source_key.startswith(prefix+':') for prefix in prefixes):continue
        if posting.source_key.startswith('reverse:'):continue
        key='reverse:'+posting.source_key
        if BookPosting.objects.filter(entity=config.entity,basis=posting.basis,source_key=key).exists():continue
        when=max(date,posting.journal.date)
        reversed_journal=reverse_journal(posting.journal_id,when,reason,uuid.uuid5(uuid.NAMESPACE_URL,f'col360-reverse:{posting.pk}'),actor,book_internal=True)
        BookPosting.objects.create(journal=reversed_journal,entity=config.entity,basis=posting.basis,source_key=key,snapshot={'reason':reason})

@transaction.atomic
def record_funds(data,token,actor):
    staff(actor)
    if data.get('lease'):
        from .rent_services import _lock
        _lock(data['lease'].pk)
    config=books_for(data['property'].pk)
    previous=FundsEvent.objects.filter(token=token).first()
    if previous:
        if previous.property_id!=config.property_id:raise ValidationError('Entry token belongs to another property.')
        return previous
    event=FundsEvent(created_by=actor,token=token,**data)
    event.full_clean()
    if event.date>timezone.localdate():raise ValidationError('Future cash transactions are not allowed.')
    if event.lease_id and event.lease.unit.property_id!=config.property_id:raise ValidationError('Lease belongs to another property.')
    if not event.kind.startswith(('owner_','bill_')) and not event.lease_id:raise ValidationError('Select a lease for client funds.')
    if event.charge_id and event.charge.lease_id!=event.lease_id:raise ValidationError('Charge belongs to another lease.')
    if event.receipt_id and event.date<event.receipt.received_date:raise ValidationError('Refund date cannot precede the original payment date.')
    if event.receipt_id and event.receipt.lease_id!=event.lease_id:raise ValidationError('Payment belongs to another lease.')
    if event.source_id and (event.source.lease_id!=event.lease_id or event.source.property_id!=config.property_id or event.source.date>event.date):raise ValidationError('Funds source must belong to this lease and precede this event.')
    if event.kind in ('advance_apply','advance_refund','deposit_apply','deposit_refund'):
        expected='advance_in' if event.kind.startswith('advance_') else 'deposit_in'
        if not event.source_id or event.source.kind not in ([expected, 'credit_to_deposit'] if expected=='deposit_in' else [expected]):raise ValidationError('Select the original funds receipt.')
        used=event.source.applications.aggregate(total=Sum('amount'))['total'] or ZERO
        if event.amount>event.source.amount-used:raise ValidationError('Amount exceeds the remaining funds.')
    from .rent_services import ledger_data
    if event.charge_id and event.charge.income_items:
        raise ValidationError('Itemized-charge credits, refunds and held-funds applications require a reviewed item-level correction; this action has not been posted.')
    if event.kind in ('advance_apply','deposit_apply','rent_credit'):
        if not event.charge_id or event.charge.status!='posted' or event.date<event.charge.period_start:raise ValidationError('Select a live charge whose service period has started.')
        post_rent_charge(event.charge,actor)
        charge=next(c for c in ledger_data(event.lease)['charges'] if c.pk==event.charge_id)
        if event.amount>charge.balance:raise ValidationError('Amount exceeds the remaining charge balance.')
    if event.kind=='rent_refund':
        if not event.receipt_id or not event.charge_id or event.receipt.status!='recorded':raise ValidationError('Select the original payment and paid charge for an earned-rent refund.')
        from .rent_models import RentAllocation
        allocation=RentAllocation.objects.filter(receipt=event.receipt,charge=event.charge).first()
        refunded=FundsEvent.objects.filter(receipt=event.receipt,charge=event.charge,kind='rent_refund').aggregate(total=Sum('amount'))['total'] or ZERO
        if not allocation or event.amount>allocation.amount-refunded:raise ValidationError('Refund exceeds the paid amount for this charge.')
        post_rent_receipt(event.receipt,actor)
    if event.kind=='credit_to_deposit':
        if not event.receipt_id or event.receipt.status!='recorded':raise ValidationError('Select the original live payment for deposit classification.')
        if event.date != event.receipt.received_date:raise ValidationError('Deposit classification must retain the original payment date.')
        from .book_models import BankReconciliation
        if BankReconciliation.objects.filter(entity_bank__entity=config.entity,entity_bank__bank_id=event.receipt.financial_account_id,status='final',statement_end__gte=event.date).exists():
            raise ValidationError('The bank period is finalized. Use an open-period reviewed correction.')
        post_rent_receipt(event.receipt,actor)
        receipt=next(r for r in ledger_data(event.lease)['receipts'] if r.pk==event.receipt_id)
        if event.amount>receipt.credit:raise ValidationError('Deposit classification exceeds unapplied payment credit.')
    if event.kind=='credit_refund':
        if not event.receipt_id or event.receipt.status!='recorded':raise ValidationError('Select a live payment with unapplied credit.')
        post_rent_receipt(event.receipt,actor)
        receipt=next(r for r in ledger_data(event.lease)['receipts'] if r.pk==event.receipt_id)
        if event.amount>receipt.credit:raise ValidationError('Refund exceeds unapplied credit.')
    if event.kind.startswith('bill_'):
        if not event.invoice_id or event.invoice.work_order.unit.property_id!=config.property_id:raise ValidationError('Select a bill for this property.')
        post_bill(event.invoice,actor)
        invoice=event.invoice
        if event.date<invoice.book_details.recognition_date:raise ValidationError('Bill credit/refund must follow bill recognition.')
        if event.kind=='bill_credit':
            used=invoice.fund_events.filter(kind='bill_credit').aggregate(total=Sum('amount'))['total'] or ZERO
            if event.amount>invoice.amount-used:raise ValidationError('Credit exceeds the remaining bill amount.')
        elif event.amount>max(ZERO,-invoice.outstanding_amount):raise ValidationError('Refund exceeds vendor credit balance.')
        if event.kind=='bill_refund':
            if invoice.payments.filter(status='recorded',payment_date__gt=event.date).exists() or invoice.fund_events.filter(kind='bill_credit',date__gt=event.date).exists():raise ValidationError('Vendor refund must follow the related payment and credit dates.')
    elif event.invoice_id:raise ValidationError('This event does not use a vendor bill.')
    noncash=event.kind in ('credit_to_deposit','advance_apply','deposit_apply','rent_credit','bill_credit')
    bank=bank_account(config,event.bank) if not noncash else None
    if noncash and event.bank_id:raise ValidationError('A non-cash application must not select a bank.')
    # Avoid accepting unrelated source fields that would reduce another deposit balance.
    if event.kind not in ('advance_apply','advance_refund','deposit_apply','deposit_refund') and event.source_id:raise ValidationError('This transaction does not use a funds source.')
    if event.kind not in ('advance_apply','deposit_apply','rent_credit','rent_refund') and event.charge_id:raise ValidationError('This transaction does not use a charge.')
    if event.kind not in ('credit_to_deposit','credit_refund','rent_refund') and event.receipt_id:raise ValidationError('This transaction does not use a rent payment.')
    event.save();amount=event.amount
    for basis in ['cash','accrual']:
        kind=event.kind
        if kind=='credit_to_deposit':lines=[(config.credits,amount),(config.deposits,-amount)]
        elif kind=='deposit_in':lines=[(bank,amount),(config.deposits,-amount)]
        elif kind=='advance_in':lines=[(bank,amount),(config.rent_income if basis=='cash' else config.advances,-amount)]
        elif kind=='deposit_refund':lines=[(config.deposits,amount),(bank,-amount)]
        elif kind=='advance_refund':lines=[(config.rent_income if basis=='cash' else config.advances,amount),(bank,-amount)]
        elif kind=='rent_refund':lines=[(config.rent_income,amount),(bank,-amount)]
        elif kind=='credit_refund':lines=[(config.credits,amount),(bank,-amount)]
        elif kind=='deposit_apply':lines=[(config.deposits,amount),(config.rent_income if basis=='cash' else config.receivable,-amount)]
        elif kind=='advance_apply':lines=[] if basis=='cash' else [(config.advances,amount),(config.receivable,-amount)]
        elif kind=='rent_credit':lines=[] if basis=='cash' else [(config.rent_income,amount),(config.receivable,-amount)]
        elif kind=='bill_credit':lines=[] if basis=='cash' else [(config.payable,amount),(event.invoice.book_details.expense_account,-amount)]
        elif kind=='bill_refund':lines=[(bank,amount),(event.invoice.book_details.expense_account if basis=='cash' else config.payable,-amount)]
        elif kind=='owner_in':lines=[(bank,amount),(config.owner_equity,-amount)]
        elif kind=='owner_out':
            from .book_reports import owner_funds
            # Evaluate before this event posts either book; cash and liability reservations are separate.
            if basis=='cash' and amount>owner_funds(config,as_of=event.date)['available']:raise ValidationError('Distribution exceeds available owner funds after client funds, bills and reserves.')
            lines=[(config.owner_equity,amount),(bank,-amount)]
        else:raise ValidationError('Unsupported funds event.')
        if lines:_book(config,basis,'funds:'+str(event.pk),event.date,lines,actor,snapshot(event,['kind','date','amount','source_id','receipt_id','charge_id']),event.reference,event.lease.unit if event.lease_id else None)
    record_event(action='ACCOUNTING_FUNDS_RECORDED',instance=event,actor=actor,property_id=config.property_id,new_values=snapshot(event,['kind','date','amount','reference']))
    return event

@transaction.atomic
def reverse_manual(posting,date,reason,actor):
    from .book_models import AccountingEntity
    staff(actor);AccountingEntity.objects.select_for_update().get(pk=posting.entity_id)
    if not posting.source_key.startswith('manual:'):raise ValidationError('Reverse the source transaction instead.')
    results=[]
    for linked in BookPosting.objects.filter(entity=posting.entity,source_key=posting.source_key).select_related('journal'):
        if BookPosting.objects.filter(entity=posting.entity,basis=linked.basis,source_key='reverse:'+linked.source_key).exists():raise ValidationError('This journal has already been reversed.')
        journal=reverse_journal(linked.journal_id,date,reason,uuid.uuid5(uuid.NAMESPACE_URL,'col360-manual-reverse:'+str(linked.pk)),actor,book_internal=True)
        BookPosting.objects.create(journal=journal,entity=posting.entity,basis=linked.basis,source_key='reverse:'+linked.source_key,snapshot={'reason':reason})
        results.append(journal)
    return results[0]

@transaction.atomic
def void_bill_payment(payment,reason,actor):
    from maintenance.models import VendorInvoice,VendorPayment
    staff(actor)
    VendorInvoice.objects.select_for_update().get(pk=payment.invoice_id)
    payment=VendorPayment.objects.select_for_update().select_related('invoice__work_order__unit').get(pk=payment.pk)
    config=books_for(payment.invoice.work_order.unit.property_id)
    if not reason.strip():raise ValidationError('Enter a correction reason.')
    from .reimbursement_models import OnBehalfSettlement
    settlement=OnBehalfSettlement.objects.select_for_update().filter(payment=payment).first()
    if settlement:
        from .reimbursements import authorize
        authorize(actor,'maintenance.change_vendorpayment')
    if settlement and settlement.reimbursements.filter(status='recorded').exists():raise ValidationError('Void the recorded reimbursements before voiding the original on-behalf payment.')
    if payment.status=='void':return payment
    if payment.invoice.fund_events.exists():raise ValidationError('Review bill credits and refunds before voiding this payment.')
    reverse_source(config,['bill-payment:'+str(payment.pk)],timezone.localdate(),reason,actor)
    payment.status='void';payment.voided_by=actor;payment.voided_at=timezone.now();payment.void_reason=reason
    payment._books_correction=True;payment.save(update_fields=['status','voided_by','voided_at','void_reason'])
    invoice=payment.invoice
    invoice.status='partially_paid' if invoice.paid_amount else 'approved';invoice.paid_at=None
    invoice.save(update_fields=['status','paid_at'])
    record_event(action='VENDOR_PAYMENT_VOIDED',instance=payment,actor=actor,property_id=config.property_id,reason=reason,new_values={'status':'void'})
    return payment

@transaction.atomic
def assign_legacy(journal_id,entity,basis,actor):
    from .journal_models import JournalEntry
    from .book_models import AccountingEntity,BankReconciliation
    staff(actor);AccountingEntity.objects.select_for_update().get(pk=entity.pk)
    if not str(journal_id).isdigit():raise ValidationError('Enter a valid journal ID.')
    journal=JournalEntry.objects.select_for_update().get(pk=journal_id)
    if basis not in ('cash','accrual') or hasattr(journal,'book_posting'):raise ValidationError('Select an unassigned journal and a single reviewed basis.')
    if journal.property_id and not PropertyBooks.objects.filter(property_id=journal.property_id,entity=entity).exists():raise ValidationError('Property belongs to another entity.')
    if hasattr(journal,'reversal') or journal.reversal_of_id:raise ValidationError('Review and assign the original and reversal together; standalone assignment is blocked.')
    lines=list(journal.lines.select_related('account'))
    if not lines or sum((line.debit-line.credit for line in lines),ZERO):raise ValidationError('Existing journal is not balanced.')
    for line in lines:
        from .models import FinancialAccount
        bank=FinancialAccount.objects.filter(ledger_account=line.account).first()
        if bank:
            mapping=EntityBank.objects.select_for_update().filter(entity=entity,bank=bank).first()
            if not mapping:raise ValidationError('Bank belongs to another or unconfigured entity.')
            if basis=='cash' and BankReconciliation.objects.filter(entity_bank=mapping,status='final',statement_end__gte=journal.date).exists():raise ValidationError('Cannot assign a journal into a finalized bank period.')
    posting=BookPosting.objects.create(journal=journal,entity=entity,basis=basis,source_key='manual:legacy-'+str(journal.pk),snapshot={'reviewed_legacy':str(journal.pk)})
    record_event(action='LEGACY_JOURNAL_ASSIGNED',instance=journal,actor=actor,new_values={'entity_id':entity.pk,'basis':basis},property_id=journal.property_id)
    return posting
