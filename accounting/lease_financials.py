"""Read-only rent transaction timeline, including explicit void reversals."""
from decimal import Decimal
from django.utils import timezone


def financial_timeline(ledger):
    rows=[]
    for kind,entries in [('charge',ledger['charges']),('receipt',ledger['receipts'])]:
        for entry in entries:
            amount=entry.amount if kind=='charge' else -entry.amount
            date=entry.due_date if kind=='charge' else entry.received_date
            rows.append({'entry':entry,'kind':kind,'date':date,'amount':amount,'reversal':False,'order':entry.created_at})
            if entry.status=='void' and entry.voided_at:
                rows.append({'entry':entry,'kind':kind,'date':max(date,timezone.localtime(entry.voided_at).date()),'amount':-amount,'reversal':True,'order':entry.voided_at})
    for event in ledger.get('fund_events',[]):
        if event.kind in ('deposit_in','deposit_refund'):
            rows.append({'entry':event,'kind':'funds','date':event.date,'amount':-event.amount if event.kind=='deposit_in' else event.amount,'balance_effect':Decimal('0.00'),'reversal':False,'order':event.created_at})
            continue
        if event.kind=='rent_refund':
            rows.append({'entry':event,'kind':'funds','date':event.date,'amount':event.amount,'reversal':False,'order':event.created_at})
            rows.append({'entry':event,'kind':'funds','date':event.date,'amount':-event.amount,'reversal':False,'order':event.created_at})
            continue
        if event.kind not in ('credit_to_deposit','credit_refund','advance_apply','deposit_apply','rent_credit'):continue
        rows.append({'entry':event,'kind':'funds','date':event.date,'amount':event.amount if event.kind in ('credit_refund','credit_to_deposit') else -event.amount,'reversal':False,'order':event.created_at})
    rows.sort(key=lambda x:(x['date'],x['order'],x['kind'],x['entry'].pk))
    balance=Decimal('0.00')
    for row in rows:
        balance+=row.get('balance_effect',row['amount']);row['balance']=balance
    return {'rows':list(reversed(rows)),'balance':balance}


def ledger_display_metadata(lease,timeline):
    """Read-only display labels; never turn a receipt reference into an invoice."""
    from .book_models import PropertyBooks,BookPosting
    config=PropertyBooks.objects.select_related('rent_income','credits','deposits','advances').filter(property_id=lease.unit.property_id).first()
    keys=set();row_keys={}
    for row in timeline['rows']:
        entry=row['entry'];kind=row['kind']
        sources=['rent-charge:'+str(entry.pk)] if kind=='charge' else ['funds:'+str(entry.pk)] if kind=='funds' else ['rent-allocation:'+str(a.pk) for a in entry.allocations.all()]
        row_keys[(kind,entry.pk)]=sources;keys.update(sources)
    posted={}
    for posting in BookPosting.objects.filter(source_key__in=keys,journal__property_id=lease.unit.property_id).prefetch_related('journal__lines__account'):
        names=posted.setdefault(posting.source_key,set())
        names.update(line.account.name for line in posting.journal.lines.all() if line.account.account_type=='income')
    for row in timeline['rows']:
        entry=row['entry'];kind=row['kind']
        names=set().union(*(posted.get(key,set()) for key in row_keys[(kind,entry.pk)]))
        if not names and config:
            role={'deposit_in':'deposits','deposit_refund':'deposits','credit_to_deposit':'deposits','credit_refund':'credits','advance_apply':'advances','deposit_apply':'deposits'}.get(getattr(entry,'kind',''),'rent_income') if kind=='funds' else 'rent_income'
            names={getattr(config,role).name}
        if kind=='receipt' and config and entry.fund_events.filter(kind='credit_to_deposit').exists():
            names.add(config.deposits.name)
        if kind=='charge' and entry.income_items:
            from .models import ChartAccount
            accounts={a.pk:a.name for a in ChartAccount.objects.filter(pk__in=[x['account_id'] for x in entry.income_items])}
            names=set(accounts.values());row['income_items']=[{**x,'account_name':accounts[x['account_id']]} for x in entry.income_items]
        elif kind=='receipt':
            allocations=list(entry.allocations.select_related('charge'))
            if config and any(a.charge.income_items for a in allocations):
                from .charge_items import income_lines
                from django.db.models import Sum
                if not any(posted.get(key) for key in row_keys[(kind,entry.pk)]):
                    names=set()
                    for allocation in allocations:
                        prior=allocation.charge.allocations.filter(pk__lt=allocation.pk,receipt__status='recorded').aggregate(total=Sum('amount'))['total'] or Decimal('0')
                        names.update(a.name for a,value in income_lines(allocation.charge,config,allocation.amount,prior) if value)
                    if entry.fund_events.filter(kind='credit_to_deposit').exists():names.add(config.deposits.name)
        row['account_label']=', '.join(sorted(names))
        row['invoice_label']=getattr(entry,'invoice_number','') or ''
    return timeline
