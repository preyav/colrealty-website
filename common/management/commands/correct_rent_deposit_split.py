"""Reviewed correction of an unposted rent charge and a mixed receipt."""
import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from django.core.exceptions import ValidationError
from django.db import transaction
from accounting.rent_models import RentCharge,RentReceipt
from accounting.book_models import FundsEvent,PropertyBooks
from accounting.book_services import source_posted,record_funds,bank_account
from accounting.rent_services import _lock,edit_entry,entry_snapshot
from common.audit.services import record_event


class Command(BaseCommand):
    help='Preview or apply an audited rent/deposit split, preserving the original bank receipt.'

    def add_arguments(self,p):
        p.add_argument('--source',required=True)
        p.add_argument('--apply',action='store_true')
        p.add_argument('--actor-id',type=int)

    @transaction.atomic
    def handle(self,*args,**o):
        try:
            plan=json.loads(Path(o['source']).read_text(encoding='utf-8'))
            expected=plan['expected'];split=plan['split'];incoming=plan['missing_deposit']
            token=uuid.UUID(plan['token']);split_token=uuid.uuid5(token,'split');new_token=uuid.uuid5(token,'missing-deposit')
            rent=Decimal(split['rent']);deposit=Decimal(split['deposit']);new_amount=Decimal(incoming['amount'])
            new_date=date.fromisoformat(incoming['date']);reason=plan['reason'].strip()
            if not reason or min(rent,deposit,new_amount)<=0:raise ValueError()
        except (OSError,ValueError,KeyError,TypeError) as exc:raise CommandError('Invalid correction plan.') from exc
        lease=_lock(expected['lease_id'])
        if (lease.unit.property_id != expected['property_id'] or lease.unit.unit_number != expected['unit_number'] or lease.unit.property.street_address != expected['street_address']):
            raise CommandError('Lease/property/unit identity changed.')
        existing=FundsEvent.objects.filter(token__in=[split_token,new_token])
        if existing.exists() and existing.exclude(lease=lease,property_id=lease.unit.property_id).exists():
            raise CommandError('Correction token belongs to a different lease/property.')
        if existing.count()==2:
            self.stdout.write('Correction already applied. Nothing changed.');return
        if existing.exists():raise CommandError('Partial correction tokens exist. Review before proceeding.')
        receipt=RentReceipt.objects.select_for_update(of=('self',)).select_related('financial_account').get(pk=expected['receipt_id'],lease=lease,status='recorded')
        charge=RentCharge.objects.select_for_update().get(pk=expected['charge_id'],lease=lease,status='posted')
        if (receipt.amount != Decimal(expected['receipt_amount']) or str(receipt.received_date)!=expected['receipt_date'] or rent+deposit!=receipt.amount or charge.amount!=Decimal(expected['charge_amount']) or str(charge.period_start)!=expected['period_start'] or str(charge.period_end)!=expected['period_end']):
            raise CommandError('Receipt or charge differs from the reviewed plan.')
        if source_posted('rent-charge:'+str(charge.pk)) or source_posted('rent-receipt:'+str(receipt.pk)):
            raise CommandError('Source has been posted since review. A reversal-based correction is required.')
        allocations=list(receipt.allocations.all())
        if len(allocations)!=1 or allocations[0].charge_id!=charge.pk or allocations[0].amount!=rent or charge.allocations.exclude(receipt=receipt).filter(receipt__status='recorded').exists():
            raise CommandError('Allocations differ from the reviewed rent/deposit split.')
        if FundsEvent.objects.filter(receipt=receipt).exists():raise CommandError('Receipt already has client-funds activity.')
        if RentReceipt.objects.filter(lease=lease,status='recorded',received_date=new_date,amount=new_amount).exists() or FundsEvent.objects.filter(lease=lease,date=new_date,amount=new_amount,kind__in=['deposit_in','credit_to_deposit']).exists():
            raise CommandError('A matching payment or deposit already exists. Review for duplication.')
        config=PropertyBooks.objects.select_for_update().filter(property_id=lease.unit.property_id).first()
        if not config:raise CommandError('Configure Property accounting before applying this correction.')
        try:bank_account(config,receipt.financial_account)
        except ValidationError as exc:raise CommandError('; '.join(exc.messages)) from exc
        self.stdout.write(f'Property: {lease.unit.property.full_address}; lease #{lease.pk}')
        self.stdout.write(f'Charge #{charge.pk}: {charge.amount} -> {rent}; period {charge.period_start} to {charge.period_end}')
        self.stdout.write(f'Retain receipt #{receipt.pk}: {receipt.received_date} / {receipt.amount} / {receipt.reference}')
        self.stdout.write(f'Classify remaining {deposit} as refundable deposit; no additional bank movement.')
        self.stdout.write(f'Record missing refundable deposit: {new_date} / {new_amount}.')
        self.stdout.write(f'REVIEW RECEIVING BANK for the missing payment: {receipt.financial_account}. This plan uses the same bank as the original payment.')
        self.stdout.write(f'Accounting enabled: {config.enabled}. Deposit account: {config.deposits}.')
        if not o['apply']:
            self.stdout.write('Preview only. Nothing saved.');return
        actor=get_user_model().objects.filter(pk=o.get('actor_id'),is_staff=True,is_active=True).first()
        if not actor or not (actor.is_superuser or all(actor.has_perm(x) for x in ['accounting.change_rentcharge','accounting.add_fundsevent'])):
            raise CommandError('Staff actor with charge change and funds-event permissions required.')
        if not config.enabled:raise CommandError('Enable automatic rent posting in Settings > Property accounting for this property before applying. No changes saved.')
        before=entry_snapshot(charge,'charge')
        data={k:getattr(charge,k) for k in ['period_start','period_end','due_date','notes']};data['amount']=rent
        data['notes']=(charge.notes+'\n'+reason).strip()
        edit_entry(lease.pk,'charge',charge.pk,data,before,reason,actor)
        split_event=record_funds({'property':lease.unit.property,'lease':lease,'kind':'credit_to_deposit','date':receipt.received_date,'amount':deposit,'receipt':receipt,'bank':None,'reference':receipt.reference,'notes':reason},split_token,actor)
        new_event=record_funds({'property':lease.unit.property,'lease':lease,'kind':'deposit_in','date':new_date,'amount':new_amount,'bank':receipt.financial_account,'reference':incoming['reference'],'notes':reason},new_token,actor)
        old_notes=receipt.notes
        receipt.notes=reason
        receipt.save(update_fields=['notes'])
        record_event(action='RENT_DEPOSIT_SPLIT_CORRECTED',instance=receipt,actor=actor,request=None,property_id=lease.unit.property_id,
            old_values={'notes':old_notes,'charge_amount':expected['charge_amount']},new_values={'notes':receipt.notes,'charge_amount':str(rent),'deposit_classification_id':split_event.pk,'missing_deposit_id':new_event.pk},reason=reason)
        self.stdout.write(f'Saved and audited: rent {rent}; deposit classified {deposit}; missing deposit recorded {new_amount}. Original receipt and application fee preserved.')
