from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from common.audit.services import record_event
from .general_ledger import staff
from .book_models import EntityBank,BankReconciliation,BankClearance
from .journal_models import JournalLine
from .book_reports import account_balance,ZERO

def bank_lines(bank,end):
    return JournalLine.objects.filter(account=bank.bank.ledger_account,journal__book_posting__entity=bank.entity,journal__book_posting__basis='cash',journal__date__lte=end).select_related('journal')

@transaction.atomic
def reconcile(bank_id,start,end,opening,closing,line_ids,actor,finalize=False):
    staff(actor);bank=EntityBank.objects.select_for_update().select_related('bank','entity').get(pk=bank_id)
    if end<start or end>timezone.localdate():raise ValidationError('Select a valid completed statement period.')
    prior=BankReconciliation.objects.filter(entity_bank=bank,status='final').order_by('-statement_end').first()
    if prior and (start<=prior.statement_end or opening!=prior.closing_balance):raise ValidationError('The statement must follow the last finalized statement and use its closing balance.')
    if BankReconciliation.objects.filter(entity_bank=bank,status='final',statement_start__lte=end,statement_end__gte=start).exists():raise ValidationError('Statement overlaps a finalized reconciliation.')
    eligible=bank_lines(bank,end).filter(bank_clearance__isnull=True)
    lines=list(eligible.filter(pk__in=line_ids))
    if len(set(line_ids))!=len(lines):raise ValidationError('Select uncleared transactions belonging to this entity and bank.')
    change=sum((line.debit-line.credit for line in lines),ZERO)
    difference=closing-opening-change
    if finalize and difference:raise ValidationError('Statement difference must be zero before finalizing.')
    # A first reconciliation cannot assume an unposted opening balance.
    if not prior and opening!=account_balance(bank.entity,bank.bank.ledger_account,start-timezone.timedelta(days=1),basis='cash'):
        raise ValidationError('Opening balance must match the posted opening books. Post and review the opening balance first.')
    if not finalize:return {'difference':difference,'change':change,'lines':lines,'book_balance':account_balance(bank.entity,bank.bank.ledger_account,end,basis='cash')}
    row=BankReconciliation.objects.create(entity_bank=bank,statement_start=start,statement_end=end,opening_balance=opening,closing_balance=closing)
    for line in lines:BankClearance.objects.create(reconciliation=row,line=line)
    row.status='final';row.finalized_by=actor;row.finalized_at=timezone.now();row.save()
    record_event(action='BANK_RECONCILED',instance=row,actor=actor,new_values={'statement_end':end,'opening':opening,'closing':closing,'lines':line_ids})
    return row
