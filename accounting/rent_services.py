"""All manual rent writes serialize on the lease and share one audit transaction."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from common.audit.services import record_event
from common.models import FormFieldSetting
from leasing.models import Lease
from .rent_models import RentCharge, RentReceipt, RentAllocation

ZERO = Decimal('0.00')


def wording():
    return FormFieldSetting.objects.get(form_key='rent_ledger', field_key='ui').option_labels


def audit(action, instance, actor, request=None, old=None, new=None, reason=''):
    record_event(action=action, instance=instance, actor=actor, request=request,
                 old_values=old or {}, new_values=new or {}, reason=reason,
                 property_id=instance.lease.unit.property_id)


def ledger_data(lease, today=None):
    today = today or timezone.localdate()
    charges = list(lease.rent_charges.prefetch_related('allocations__receipt'))
    receipts = list(lease.rent_receipts.select_related('financial_account').prefetch_related('allocations'))
    for charge in charges:
        charge.applied = sum((x.amount for x in charge.allocations.all() if x.receipt.status == 'recorded'), ZERO)
        charge.balance = charge.amount - charge.applied if charge.status == 'posted' else ZERO
        charge.overdue = charge.balance > 0 and charge.due_date < today
    from .book_models import FundsEvent
    events=FundsEvent.objects.filter(lease=lease)
    refunded=sum((e.amount for e in events if e.kind in ('credit_refund','rent_refund')),ZERO)
    credits=sum((e.amount for e in events if e.kind in ('rent_credit','rent_refund')),ZERO)
    for charge in charges:
        charge.applied-=sum((e.amount for e in events if e.charge_id==charge.pk and e.kind=='rent_refund'),ZERO)
        charge.balance=charge.amount-charge.applied if charge.status=='posted' else ZERO
        adjustments=sum((e.amount for e in events if e.charge_id==charge.pk and e.kind in ('advance_apply','deposit_apply','rent_credit','rent_refund')),ZERO)
        if charge.status=='posted':
            charge.balance-=adjustments;charge.overdue=charge.balance>0 and charge.due_date<today
    methods=FormFieldSetting.objects.get(form_key='rent_ledger',field_key='payment_method').option_labels
    for receipt in receipts:
        receipt.display_method=methods.get(receipt.payment_method,receipt.payment_method)
        receipt.applied = sum((x.amount for x in receipt.allocations.all()), ZERO) if receipt.status == 'recorded' else ZERO
        receipt.credit = receipt.amount - receipt.applied - sum((e.amount for e in events if e.receipt_id==receipt.pk and e.kind in ('credit_refund','credit_to_deposit')),ZERO) if receipt.status == 'recorded' else ZERO
    return {'charges':charges, 'receipts':receipts,'fund_events':list(events),'deposit_held':sum((e.amount if e.kind in ('deposit_in','credit_to_deposit') else -e.amount for e in events if e.kind in ('deposit_in','credit_to_deposit','deposit_refund','deposit_apply')),ZERO),'advance_held':sum((e.amount if e.kind=='advance_in' else -e.amount for e in events if e.kind in ('advance_in','advance_refund','advance_apply')),ZERO)+sum((a.amount for charge in charges if charge.period_start>today for a in charge.allocations.all() if a.receipt.status=='recorded' and a.receipt.received_date<=today),ZERO),'refunded':refunded,'charge_credits':credits,
            'charged':sum((x.amount for x in charges if x.status=='posted'),ZERO)-credits,
            'received':sum((x.amount for x in receipts if x.status=='recorded'),ZERO),
            'outstanding':sum((x.balance for x in charges),ZERO),
            'overdue':sum((x.balance for x in charges if x.overdue),ZERO),
            'credit':sum((x.credit for x in receipts),ZERO)}


def _staff(actor):
    if not actor or not actor.is_active or not actor.is_staff:
        raise PermissionError('Staff access required.')


def _lock(lease_id):
    return Lease.objects.select_for_update().select_related('unit__property').get(pk=lease_id)


@transaction.atomic
def post_charge(lease_id, data, token, actor, request=None):
    _staff(actor)
    lease = _lock(lease_id)
    previous = RentCharge.objects.filter(entry_token=token).first()
    if previous:
        if previous.lease_id != lease.pk:
            raise ValidationError(wording()['invalid_entry'])
        return previous
    ui = wording()
    if lease.status not in ('active','notice'):
        raise ValidationError(ui['lease_not_active'])
    if data['amount'] <= 0 or data['period_end'] < data['period_start']:
        raise ValidationError(ui['invalid_charge'])
    # Reject overlapping live rent periods, not merely identical submissions.
    if lease.rent_charges.filter(status='posted',period_start__lte=data['period_end'],period_end__gte=data['period_start']).exists():
        raise ValidationError(ui['overlap'])
    from .charge_items import normalize_items
    data=dict(data);data['income_items']=normalize_items(data.get('income_items'),data['amount'])
    charge = RentCharge(lease=lease, entry_token=token, created_by=actor, **data)
    charge.full_clean();charge.save()
    audit('RENT_CHARGE_POSTED',charge,actor,request,new={'amount':charge.amount,'period_start':charge.period_start,'period_end':charge.period_end,'due_date':charge.due_date})
    from .book_models import PropertyBooks
    if PropertyBooks.objects.filter(property_id=lease.unit.property_id,enabled=True).exists():
        from .book_services import post_rent_charge
        post_rent_charge(charge,actor)
    return charge


def _allocate_locked(receipt):
    if receipt.status != 'recorded':
        raise ValidationError(wording()['invalid_entry'])
    from .book_models import FundsEvent
    refunded=sum((e.amount for e in FundsEvent.objects.filter(receipt=receipt,kind__in=['credit_refund','credit_to_deposit'])),ZERO)
    remaining = receipt.amount - sum((x.amount for x in receipt.allocations.all()),ZERO)-refunded
    changes=[]
    for charge in receipt.lease.rent_charges.filter(status='posted').order_by('due_date','pk').prefetch_related('allocations__receipt'):
        if remaining <= 0:break
        balance = charge.amount - sum((x.amount for x in charge.allocations.all() if x.receipt.status=='recorded'),ZERO)-sum((e.amount for e in FundsEvent.objects.filter(charge=charge,kind__in=['advance_apply','deposit_apply','rent_credit'])),ZERO)
        amount=min(remaining,balance)
        if amount <= 0:continue
        allocation,created=RentAllocation.objects.get_or_create(receipt=receipt,charge=charge,defaults={'amount':amount})
        if not created:
            allocation.amount += amount;allocation.save(update_fields=['amount'])
        remaining -= amount;changes.append({'charge_id':charge.pk,'amount':str(amount)})
    return changes


@transaction.atomic
def post_receipt(lease_id, data, token, actor, request=None):
    _staff(actor)
    lease = _lock(lease_id)
    previous=RentReceipt.objects.filter(entry_token=token).first()
    if previous:
        if previous.lease_id!=lease.pk:raise ValidationError(wording()['invalid_entry'])
        return previous
    ui=wording()
    if lease.status not in ('active','notice','expired','terminated'):
        raise ValidationError(ui['lease_not_receivable'])
    if data['amount']<=0 or data['received_date']>timezone.localdate():
        raise ValidationError(ui['invalid_receipt'])
    account=data.get('financial_account')
    if account and (not account.is_active or account.kind=='credit_card'):
        raise ValidationError(ui['invalid_account'])
    receipt=RentReceipt(lease=lease,entry_token=token,created_by=actor,**data)
    receipt.full_clean();receipt.save()
    allocations=_allocate_locked(receipt)
    audit('RENT_RECEIPT_RECORDED',receipt,actor,request,new={'amount':receipt.amount,'received_date':receipt.received_date,'method':receipt.payment_method,'reference':receipt.reference,'financial_account_id':receipt.financial_account_id,'allocations':allocations})
    from .book_models import PropertyBooks
    if PropertyBooks.objects.filter(property_id=lease.unit.property_id,enabled=True).exists():
        from .book_services import post_rent_receipt
        post_rent_receipt(receipt,actor)
    return receipt


@transaction.atomic
def apply_credit(lease_id, receipt_id, actor, request=None):
    _staff(actor);lease=_lock(lease_id)
    receipt=lease.rent_receipts.get(pk=receipt_id)
    changes=_allocate_locked(receipt)
    if changes:audit('RENT_CREDIT_APPLIED',receipt,actor,request,new={'allocations':changes})
    from .book_services import post_rent_receipt,source_posted
    if source_posted('rent-receipt:'+str(receipt.pk)):
        post_rent_receipt(receipt,actor)
    return receipt


@transaction.atomic
def void_entry(lease_id, kind, entry_id, reason, actor, request=None):
    _staff(actor);lease=_lock(lease_id);ui=wording()
    if kind not in ('charge','receipt') or not reason.strip():raise ValidationError(ui['reason_required'])
    entry=(lease.rent_charges if kind=='charge' else lease.rent_receipts).get(pk=entry_id)
    if entry.status=='void':return entry
    if kind=='charge' and entry.allocations.filter(receipt__status='recorded').exists():
        raise ValidationError(ui['charge_allocated'])
    from .book_models import FundsEvent,PropertyBooks
    if FundsEvent.objects.filter(**({'charge':entry} if kind=='charge' else {'receipt':entry})).exists():raise ValidationError('This entry has client-funds applications or refunds. Review those before voiding it.')
    from .book_services import reverse_source,source_posted
    config=PropertyBooks.objects.filter(property_id=lease.unit.property_id).first()
    source_key=('rent-charge:' if kind=='charge' else 'rent-receipt:')+str(entry.pk)
    if source_posted(source_key):
        if not config:raise ValidationError('Restore the accounting configuration before voiding this posted entry.')
        prefixes=[('rent-charge:' if kind=='charge' else 'rent-receipt:')+str(entry.pk)]
        if kind=='receipt':prefixes += ['rent-allocation:'+str(pk) for pk in entry.allocations.values_list('pk',flat=True)]
        reverse_source(config,prefixes,timezone.localdate(),reason,actor)
    old=entry.status;entry.status='void';entry.void_reason=reason.strip();entry.voided_by=actor;entry.voided_at=timezone.now()
    entry.save(update_fields=['status','void_reason','voided_by','voided_at'])
    audit('RENT_CHARGE_VOIDED' if kind=='charge' else 'RENT_RECEIPT_VOIDED',entry,actor,request,old={'status':old},new={'status':'void'},reason=reason.strip())
    return entry


def portfolio_rent_data(today=None,managed=True):
    today=today or timezone.localdate()
    leases=Lease.objects.all()
    if managed:leases=leases.filter(unit__property__management_status='active')
    rows=[]
    for lease in leases.select_related('unit__property'):
        data=ledger_data(lease,today)
        if not data['charges'] and not data['receipts'] and not data['fund_events']:continue
        rows.append({'lease':lease,**{key:data[key] for key in ('charged','received','outstanding','overdue','credit')}})
    totals={key:sum((x[key] for x in rows),ZERO) for key in ('charged','received','outstanding','overdue','credit')}
    return {'rows':sorted(rows,key=lambda x:(-x['overdue'],x['lease'].pk)),'totals':totals,'has_entries':bool(rows)}


def entry_snapshot(entry, kind):
    fields = ('period_start','period_end','due_date','amount','notes') if kind == 'charge' else ('received_date','amount','payment_method','reference','financial_account_id','notes')
    result={name: format(entry.amount, '.2f') if name == 'amount' else str(getattr(entry, name)) for name in fields + ('status',)}
    if kind=='charge':result['income_items']=entry.income_items
    return result


@transaction.atomic
def edit_entry(lease_id, kind, entry_id, data, expected, reason, actor, request=None):
    _staff(actor)
    lease = _lock(lease_id)
    ui = wording()
    if kind not in ('charge', 'receipt') or not reason.strip():
        raise ValidationError(ui['reason_required'])
    entry = (lease.rent_charges if kind == 'charge' else lease.rent_receipts).get(pk=entry_id)
    from .book_services import source_posted
    if source_posted(('rent-charge:' if kind=='charge' else 'rent-receipt:')+str(entry.pk)):
        raise ValidationError('This entry is posted to accounting. Void and replace it to preserve both books.')
    before = entry_snapshot(entry, kind)
    if entry.status == 'void' or before != expected:
        raise ValidationError(ui['edit_stale'])
    allocated = sum((x.amount for x in entry.allocations.all() if kind == 'receipt' or x.receipt.status == 'recorded'), ZERO)
    if data['amount'] < allocated:
        raise ValidationError(ui['edit_allocated'])
    allowed = ('period_start','period_end','due_date','amount','notes') if kind == 'charge' else ('received_date','amount','payment_method','reference','financial_account','notes')
    for name in allowed:
        setattr(entry, name, data[name])
    if kind == 'charge':
        if lease.rent_charges.filter(status='posted', period_start__lte=entry.period_end, period_end__gte=entry.period_start).exclude(pk=entry.pk).exists():
            raise ValidationError(ui['overlap'])
    else:
        if entry.received_date > timezone.localdate():
            raise ValidationError(ui['invalid_receipt'])
        account = entry.financial_account
        if account and account.pk != (expected.get('financial_account_id')) and str(account.pk) != expected.get('financial_account_id') and (not account.is_active or account.kind == 'credit_card'):
            raise ValidationError(ui['invalid_account'])
    if kind=='charge':
        from .charge_items import normalize_items
        entry.income_items=normalize_items(data.get('income_items',entry.income_items),entry.amount)
    entry.full_clean()
    entry.save()
    audit('RENT_CHARGE_EDITED' if kind == 'charge' else 'RENT_RECEIPT_EDITED', entry, actor, request,
          old=before, new=entry_snapshot(entry, kind), reason=reason.strip())
    return entry
