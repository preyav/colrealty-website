"""Read-only reconciliation of the current rent subledger; never posts or fixes data."""
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from django.utils import timezone
from leasing.models import Lease
from accounting.rent_models import RentAllocation

ZERO=Decimal('0.00')


def reconcile(lease,as_of):
    charges=list(lease.rent_charges.all().order_by('period_start','due_date','pk'))
    receipts=list(lease.rent_receipts.select_related('financial_account').all().order_by('received_date','pk'))
    allocations=list(RentAllocation.objects.filter(charge__lease=lease).select_related('receipt','charge') | RentAllocation.objects.filter(receipt__lease=lease).select_related('receipt','charge'))
    from accounting.book_models import FundsEvent
    fund_events=list(FundsEvent.objects.filter(lease=lease))
    events=[event for event in fund_events if event.date<=as_of]
    issues=[];charge_applied=defaultdict(lambda:ZERO);receipt_applied=defaultdict(lambda:ZERO)
    for allocation in allocations:
        if allocation.charge.lease_id!=allocation.receipt.lease_id:issues.append(f'Allocation {allocation.pk}: charge and receipt belong to different leases.')
        if allocation.charge.status!='posted' or allocation.receipt.status!='recorded':
            issues.append(f'Allocation {allocation.pk}: linked to a void entry.');continue
        if allocation.receipt.received_date<=as_of:
            charge_applied[allocation.charge_id]+=allocation.amount
            receipt_applied[allocation.receipt_id]+=allocation.amount
    totals={key:ZERO for key in ['posted_charges_all_dates','recorded_payments_all_dates','payments_through_date','overdue_unpaid','due_today_unpaid','future_due_unpaid','unallocated_credit_through_date','charge_balance_through_date','future_dated_payments']}
    charge_rows=[];payment_rows=[];months={}
    def month(key):return months.setdefault(key,{'charged':ZERO,'payments_received':ZERO})
    live=[c for c in charges if c.status=='posted']
    for previous,current in zip(sorted(live,key=lambda c:(c.period_start,c.pk)),sorted(live,key=lambda c:(c.period_start,c.pk))[1:]):
        if current.period_start<=previous.period_end:issues.append(f'Overlapping rent periods: charges {previous.pk} and {current.pk}.')
    for charge in charges:
        applied=charge_applied[charge.pk]-sum((e.amount for e in events if e.charge_id==charge.pk and e.kind=='rent_refund'),ZERO)
        adjustments=sum((e.amount for e in events if e.charge_id==charge.pk and e.kind in ('advance_apply','deposit_apply','rent_credit','rent_refund')),ZERO)
        balance=charge.amount-applied-adjustments if charge.status=='posted' else ZERO
        category='void' if charge.status!='posted' else ('overdue' if charge.due_date<as_of else 'due_today' if charge.due_date==as_of else 'future_due')
        if charge.status=='posted':
            totals['posted_charges_all_dates']+=charge.amount
            totals[{'overdue':'overdue_unpaid','due_today':'due_today_unpaid','future_due':'future_due_unpaid'}[category]]+=balance
            if charge.due_date<=as_of:totals['charge_balance_through_date']+=balance
            month(charge.period_start.strftime('%Y-%m'))['charged']+=charge.amount
            if applied>charge.amount:issues.append(f'Charge {charge.pk}: allocations exceed charge amount.')
        charge_rows.append({'id':charge.pk,'period_start':charge.period_start,'period_end':charge.period_end,'due_date':charge.due_date,'amount':charge.amount,'status':charge.status,'applied_from_payments_through_date':applied,'unpaid_using_current_allocations':balance,'category':category,'notes':charge.notes,'created_at':charge.created_at,'voided_at':charge.voided_at,'void_reason':charge.void_reason})
    for receipt in receipts:
        applied=receipt_applied[receipt.pk];credit=receipt.amount-applied-sum((e.amount for e in events if e.receipt_id==receipt.pk and e.kind in ('credit_refund','credit_to_deposit')),ZERO) if receipt.status=='recorded' and receipt.received_date<=as_of else ZERO
        if receipt.status=='recorded':
            totals['recorded_payments_all_dates']+=receipt.amount
            if receipt.received_date<=as_of:
                totals['payments_through_date']+=receipt.amount;totals['unallocated_credit_through_date']+=credit
                month(receipt.received_date.strftime('%Y-%m'))['payments_received']+=receipt.amount
            else:totals['future_dated_payments']+=receipt.amount
            if applied>receipt.amount:issues.append(f'Receipt {receipt.pk}: allocations exceed payment amount.')
            if not receipt.financial_account_id:issues.append(f'Receipt {receipt.pk}: no receiving bank/account recorded.')
        payment_rows.append({'id':receipt.pk,'received_date':receipt.received_date,'amount':receipt.amount,'status':receipt.status,'applied_through_date':applied,'unallocated_credit_through_date':credit,'payment_method':receipt.payment_method,'reference':receipt.reference,'financial_account_id':receipt.financial_account_id,'financial_account':str(receipt.financial_account) if receipt.financial_account else None,'notes':receipt.notes,'created_at':receipt.created_at,'voided_at':receipt.voided_at,'void_reason':receipt.void_reason})
    totals['current_screen_net_all_dates']=totals['posted_charges_all_dates']-totals['recorded_payments_all_dates']-sum((e.amount for e in fund_events if e.kind in ('advance_apply','deposit_apply','rent_credit')),ZERO)+sum((e.amount for e in fund_events if e.kind in ('credit_refund','credit_to_deposit')),ZERO)
    totals['net_due_through_date']=totals['charge_balance_through_date']-totals['unallocated_credit_through_date']
    totals['refunds_through_date']=sum((e.amount for e in events if e.kind in ('credit_refund','rent_refund')),ZERO)
    totals['charge_credits_through_date']=sum((e.amount for e in events if e.kind in ('rent_credit','rent_refund')),ZERO)
    totals['client_funds_applied_through_date']=sum((e.amount for e in events if e.kind in ('advance_apply','deposit_apply')),ZERO)
    return {'fund_events':[{'id':e.pk,'kind':e.kind,'date':e.date,'amount':e.amount,'charge_id':e.charge_id,'receipt_id':e.receipt_id,'source_id':e.source_id} for e in fund_events],'lease_id':lease.pk,'property_id':lease.unit.property_id,'property_address':lease.unit.property.full_address,'unit_id':lease.unit_id,'unit_number':lease.unit.unit_number,'as_of':as_of,'generated_at':timezone.now(),'basis':'Current entry statuses and current allocations, with payment dates cut off at as_of. This is not a reconstruction of historical statuses or allocation changes. No bank or signed-lease verification has been performed.','summary':totals,'issues':issues,'months':[{'month':key,**value} for key,value in sorted(months.items())],'month_note':'Gross charges grouped by period start; gross payments grouped by receipt date. Credits, refunds and client-funds applications are listed separately in fund_events. This comparison does not imply a payment was allocated to that same month.','charges':charge_rows,'payments':payment_rows,'allocations':[{'id':a.pk,'charge_id':a.charge_id,'receipt_id':a.receipt_id,'amount':a.amount,'created_at':a.created_at} for a in allocations]}


class Command(BaseCommand):
    help='Export a read-only lease rent reconciliation. Does not change entries or allocations.'
    def add_arguments(self,parser):
        parser.add_argument('--lease',type=int,required=True)
        parser.add_argument('--as-of',type=date.fromisoformat,default=None)
        parser.add_argument('--output',required=True)
    def handle(self,*args,**options):
        try:lease=Lease.objects.select_related('unit__property').get(pk=options['lease'])
        except Lease.DoesNotExist:raise CommandError('Lease does not exist.')
        report=reconcile(lease,options['as_of'] or timezone.localdate())
        path=Path(options['output'])
        try:
            with path.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2,default=str)
        except OSError as exc:raise CommandError(f'Cannot create output file: {exc}')
        self.stdout.write(f'Lease #{lease.pk}: {report["property_address"]}')
        for key,value in report['summary'].items():self.stdout.write(f'{key}: {value:.2f}')
        self.stdout.write(f'Review flags: {len(report["issues"])}')
        self.stdout.write(self.style.SUCCESS(f'Read-only report saved to {path}. No database records changed.'))
