from decimal import Decimal
from django.db.models import Sum, Q, F, DecimalField, ExpressionWrapper
from django.utils import timezone
from .book_models import PropertyBooks,BookPosting,FundsEvent,EntityBank,BankReconciliation,BankClearance
from .journal_models import JournalLine

ZERO=Decimal('0.00')

def account_balance(entity,account,as_of,property_id=None,basis='accrual'):
    lines=JournalLine.objects.filter(journal__book_posting__entity=entity,journal__book_posting__basis=basis,journal__date__lte=as_of,account=account)
    if property_id:lines=lines.filter(journal__property_id=property_id)
    sums=lines.aggregate(debit=Sum('debit'),credit=Sum('credit'))
    value=(sums['debit'] or ZERO)-(sums['credit'] or ZERO)
    return value if account.account_type in ('asset','expense') else -value

def coverage(config):
    from .rent_models import RentCharge,RentReceipt
    from maintenance.models import VendorInvoice,VendorPayment
    posted=set(BookPosting.objects.filter(entity=config.entity,journal__property_id=config.property_id).values_list('source_key',flat=True))
    missing=[]
    for model,prefix,query in [(RentCharge,'rent-charge:',{'lease__unit__property_id':config.property_id,'status':'posted'}),(RentReceipt,'rent-receipt:',{'lease__unit__property_id':config.property_id,'status':'recorded'}),(VendorInvoice,'bill:',{'work_order__unit__property_id':config.property_id,'status__in':['approved','partially_paid','paid']}),(VendorPayment,'bill-payment:',{'invoice__work_order__unit__property_id':config.property_id,'status':'recorded'})]:
        missing.extend(prefix+str(pk) for pk in model.objects.filter(**query).values_list('pk',flat=True) if prefix+str(pk) not in posted)
    legacy=JournalLine.objects.filter(journal__property_id=config.property_id,journal__book_posting__isnull=True).exists()
    return {'missing':missing,'legacy':legacy,'complete':not missing and not legacy}

def owner_funds(config,as_of=None):
    as_of=as_of or timezone.localdate()
    banks=EntityBank.objects.filter(entity=config.entity).select_related('bank__ledger_account')
    cash=sum((account_balance(config.entity,b.bank.ledger_account,as_of,config.property_id,'cash') for b in banks),ZERO)
    balances={role:account_balance(config.entity,getattr(config,role),as_of,config.property_id) for role in ['deposits','advances','credits','payable']}
    from .reimbursement_models import ReimbursementPayer
    reimbursement_accounts=ReimbursementPayer.objects.filter(entity=config.entity).values_list('liability_account_id',flat=True).distinct()
    from .models import ChartAccount
    balances['reimbursements']=sum((max(ZERO,account_balance(config.entity,a,as_of,config.property_id)) for a in ChartAccount.objects.filter(pk__in=reimbursement_accounts)),ZERO)
    held=sum((max(ZERO,balances[role]) for role in balances),ZERO)
    available=max(ZERO,cash-held-config.reserve)
    status=coverage(config)
    # Reconciled operational records are required before declaring funds distributable.
    reconciled=banks.exists()
    for bank in banks:
        if not BankReconciliation.objects.filter(entity_bank=bank,status='final').exists() or JournalLine.objects.filter(account=bank.bank.ledger_account,journal__book_posting__entity=config.entity,journal__book_posting__basis='cash',journal__date__lte=as_of,bank_clearance__isnull=True).exists():reconciled=False
    return {'config':config,'cash':cash,**balances,'reserve':config.reserve,'available':available if status['complete'] and reconciled and config.enabled else ZERO,'provisional':available,'coverage':status,'reconciled':reconciled}

def operational_balances(entity=None):
    from leasing.models import Lease
    from maintenance.models import VendorInvoice
    from .rent_services import ledger_data
    configs=PropertyBooks.objects.all()
    if entity:configs=configs.filter(entity=entity)
    ids=list(configs.values_list('property_id',flat=True));tenants=[]
    for lease in Lease.objects.filter(unit__property_id__in=ids).select_related('unit__property'):
        ledger=ledger_data(lease)
        tenants.append({'lease':lease,'charges':ledger['charged'],'payments':ledger['received'],'outstanding':ledger['outstanding'],'overdue':ledger['overdue'],'credit':ledger['credit'],'deposits':ledger['deposit_held'],'advances':ledger['advance_held']})
    invoices=list(VendorInvoice.objects.filter(work_order__unit__property_id__in=ids).exclude(status__in=['void','disputed']).select_related('work_order__unit__property','vendor').prefetch_related('payments'))
    bills=[invoice for invoice in invoices if invoice.outstanding_amount>0]
    vendor_credits=[invoice for invoice in invoices if invoice.outstanding_amount<0]
    return {'tenants':tenants,'bills':bills,'vendor_credits':vendor_credits,'owners':[owner_funds(c) for c in configs.select_related('entity','property')]}
