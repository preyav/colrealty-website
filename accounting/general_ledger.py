import uuid
from decimal import Decimal,InvalidOperation
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from common.models import FormFieldSetting
from common.audit.services import record_event
from properties.models import Property,PropertyUnit
from .models import ChartAccount
from .journal_models import JournalEntry,JournalLine

ZERO=Decimal('0.00')


def wording():
    return FormFieldSetting.objects.get(form_key='general_ledger',field_key='ui').option_labels


def funds():
    return FormFieldSetting.objects.get(form_key='accounting_workspace',field_key='chart_fund_type').option_labels


def staff(actor):
    if not actor or not actor.is_active or not actor.is_staff:raise PermissionError


@transaction.atomic
def post_journal(data,lines,token,actor,request=None,reversal_of=None,book_internal=False):
    staff(actor);ui=wording()
    # Token retries return the already-posted journal; a refresh cannot post twice.
    previous=JournalEntry.objects.filter(entry_token=token).first()
    if previous:
        if data.get('entity') and hasattr(previous,'book_posting') and previous.book_posting.entity_id!=data['entity'].pk:raise ValidationError('Entry token belongs to another entity.')
        return previous
    if not data.get('memo','').strip():raise ValidationError(ui['memo_required'])
    if data['date']>timezone.localdate() and not book_internal:raise ValidationError(ui['future'])
    from .book_models import AccountingEntity,PropertyBooks,BookPosting,EntityBank
    entity=data.get('entity')
    if not book_internal and AccountingEntity.objects.exists() and not entity:raise ValidationError('Select an accounting entity for new journals.')
    if entity and (not entity.is_active or (data.get('property') and not PropertyBooks.objects.filter(entity=entity,property=data['property']).exists())):raise ValidationError('Property and accounting entity do not match.')
    prop=data.get('property');unit=data.get('unit');fund=data.get('fund_type','')
    if unit and (not prop or unit.property_id!=prop.pk):raise ValidationError(ui['unit_mismatch'])
    if not reversal_of and fund and fund not in funds():raise ValidationError(ui['invalid_fund'])
    if len(lines)<2:raise ValidationError(ui['balanced'])
    ids=[line['account'].pk for line in lines]
    if entity:list(EntityBank.objects.select_for_update().filter(entity=entity,bank__ledger_account_id__in=ids).order_by('pk'))
    locked={a.pk:a for a in ChartAccount.objects.select_for_update().filter(pk__in=ids).order_by('pk')}
    cleaned=[];debits=ZERO;credits=ZERO
    for line in lines:
        account=locked.get(line['account'].pk)
        if not account or (not reversal_of and not account.is_active):raise ValidationError(ui['inactive_account'])
        try:
            debit=Decimal(str(line.get('debit') or 0));credit=Decimal(str(line.get('credit') or 0))
            valid=debit.is_finite() and credit.is_finite() and debit>=0 and credit>=0 and ((debit>0) != (credit>0))
            if not valid or debit.quantize(Decimal('.01'))!=debit or credit.quantize(Decimal('.01'))!=credit:raise ValidationError(ui['line_invalid'])
        except (InvalidOperation,ValueError,TypeError):raise ValidationError(ui['line_invalid'])
        if not reversal_of and account.fund_type and fund!=account.fund_type:raise ValidationError(ui['fund_mismatch'])
        cleaned.append((account,debit,credit));debits+=debit;credits+=credit
    if debits!=credits or debits<=0:raise ValidationError(ui['balanced'])
    if entity:
        for account,debit,credit in cleaned:
            from .models import FinancialAccount
            linked=FinancialAccount.objects.filter(ledger_account=account).first()
            if linked and not EntityBank.objects.filter(entity=entity,bank=linked).exists():raise ValidationError('Bank account belongs to another accounting entity.')
            if linked and data.get('basis','both') in ('cash','both'):
                list(EntityBank.objects.select_for_update().filter(entity=entity,bank=linked))
                from .book_models import BankReconciliation
                if BankReconciliation.objects.filter(entity_bank__entity=entity,entity_bank__bank=linked,status='final',statement_end__gte=data['date']).exists():raise ValidationError('This bank period is finalized; use an open-period correction.')
    journal=JournalEntry(entry_token=token,date=data['date'],memo=data['memo'].strip(),property=prop,unit=unit,fund_type=fund,created_by=actor,reversal_of=reversal_of)
    journal.full_clean();journal.save()
    for account,debit,credit in cleaned:
        line=JournalLine(journal=journal,account=account,debit=debit,credit=credit);line.full_clean();line.save()
    record_event(action='JOURNAL_REVERSED' if reversal_of else 'JOURNAL_POSTED',instance=journal,actor=actor,request=request,
        new_values={'date':journal.date,'debit':debits,'credit':credits,'property_id':journal.property_id,'unit_id':journal.unit_id,'fund_type':fund,'reversal_of':reversal_of.pk if reversal_of else None},reason=journal.memo,property_id=journal.property_id)
    if entity:
        basis=data.get('basis') or entity.default_basis
        if basis not in ('cash','accrual','both'):raise ValidationError('Invalid reporting basis.')
        first='cash' if basis=='both' else basis
        BookPosting.objects.create(journal=journal,entity=entity,basis=first,source_key='manual:'+str(token),snapshot={'memo':journal.memo})
        if basis=='both':
            other=post_journal({**data,'entity':None},lines,uuid.uuid5(token,'accrual'),actor,request,book_internal=True)
            BookPosting.objects.create(journal=other,entity=entity,basis='accrual',source_key='manual:'+str(token),snapshot={'memo':journal.memo})
    return journal


@transaction.atomic
def reverse_journal(journal_id,date,reason,token,actor,request=None,book_internal=False):
    staff(actor);ui=wording()
    journal=JournalEntry.objects.select_for_update(of=('self',)).select_related('property','unit').get(pk=journal_id)
    if hasattr(journal,'book_posting') and not book_internal:
        from .book_services import reverse_manual
        return reverse_manual(journal.book_posting,date,reason,actor)
    if hasattr(journal,'reversal'):
        existing=journal.reversal
        if existing.entry_token==token:return existing
        raise ValidationError(ui['already_reversed'])
    if journal.reversal_of_id:raise ValidationError(ui['already_reversed'])
    if date<journal.date:raise ValidationError(ui['reversal_date'])
    if hasattr(journal,'book_posting'):
        from .book_models import BankReconciliation
        posting=journal.book_posting
        if posting.basis=='cash' and BankReconciliation.objects.filter(entity_bank__entity=posting.entity,entity_bank__bank__ledger_account__journal_lines__journal=journal,status='final',statement_end__gte=date).exists():raise ValidationError('This bank period is finalized; use an open-period correction.')
    return post_journal({'date':date,'memo':reason,'property':journal.property,'unit':journal.unit,'fund_type':journal.fund_type},
        [{'account':line.account,'debit':line.credit,'credit':line.debit} for line in journal.lines.select_related('account')],token,actor,request,reversal_of=journal,book_internal=book_internal)


def ledger_report(cleaned):
    start,end=cleaned['start'],cleaned['end'];ui=wording()
    query=JournalLine.objects.select_related('account','journal__property','journal__unit','journal__created_by').filter(journal__date__lte=end)
    basis=cleaned.get('basis','accrual')
    if basis=='cash':query=query.filter(journal__book_posting__basis='cash')
    else:query=query.filter(Q(journal__book_posting__basis='accrual')|Q(journal__book_posting__isnull=True))
    if cleaned.get('entity'):query=query.filter(journal__book_posting__entity=cleaned['entity'])
    prop=cleaned.get('property');unit=cleaned.get('unit');scope=cleaned.get('scope','all')
    if scope=='properties':query=query.filter(journal__property__isnull=False)
    elif scope=='company':query=query.filter(journal__property__isnull=True)
    elif prop:query=query.filter(journal__property=prop)
    if unit:query=query.filter(journal__unit=unit)
    if cleaned.get('unit_all') is False:
        unit_filter=Q(journal__unit_id__in=cleaned.get('unit_ids',[]))
        if cleaned.get('unit_all_units'):unit_filter |= Q(journal__unit__isnull=False)
        if cleaned.get('unit_property_level'):unit_filter |= Q(journal__unit__isnull=True)
        query=query.filter(unit_filter)
    accounts=cleaned.get('accounts')
    if accounts:query=query.filter(account__in=accounts)
    fund=cleaned.get('fund_type','')
    if fund=='__unknown__':query=query.filter(journal__fund_type='')
    elif fund:query=query.filter(journal__fund_type=fund)
    groups={};fund_labels=funds()
    for line in query.order_by('account__code','journal__date','journal_id','pk'):
        line.journal.display_fund_type=fund_labels.get(line.journal.fund_type,line.journal.fund_type or ui['unknown'])
        group=groups.setdefault(line.account_id,{'account':line.account,'opening':ZERO,'debit':ZERO,'credit':ZERO,'rows':[]})
        normal=1 if line.account.account_type in ('asset','expense') else -1
        amount=(line.debit-line.credit)*normal
        if line.journal.date<start:group['opening']+=amount
        else:
            group['debit']+=line.debit;group['credit']+=line.credit
            group['rows'].append({'line':line,'change':amount})
    for group in groups.values():
        balance=group['opening']
        for row in group['rows']:balance+=row['change'];row['balance']=balance
        group['closing']=balance
        group['change']=balance-group['opening']
    return {'groups':list(groups.values()),'debit':sum((g['debit'] for g in groups.values()),ZERO),'credit':sum((g['credit'] for g in groups.values()),ZERO),
        'count':sum(len(g['rows']) for g in groups.values())}
