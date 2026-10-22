"""Reviewed, atomic income classification of existing unposted charges."""
import json
from decimal import Decimal
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from django.db import transaction
from accounting.rent_services import _lock,entry_snapshot,edit_entry
from accounting.book_services import source_posted
from accounting.charge_items import normalize_items

class Command(BaseCommand):
    def add_arguments(self,parser):
        parser.add_argument('--source',required=True)
        parser.add_argument('--apply',action='store_true')
        parser.add_argument('--actor-id',type=int)
    @transaction.atomic
    def handle(self,*args,**options):
        try:
            plan=json.loads(Path(options['source']).read_text(encoding='utf-8-sig'))
            lease=_lock(plan['lease_id'])
            if lease.unit.property_id!=plan['property_id'] or lease.unit.unit_number!=plan['unit_number'] or lease.unit.property.street_address!=plan['street_address']:raise CommandError('Lease/property identity differs from the reviewed plan.')
            from accounting.models import ChartAccount
            for account_id,code in plan.get('account_codes',{}).items():
                if not ChartAccount.objects.filter(pk=account_id,code=code,is_active=True,account_type='income').exists():raise CommandError('An income account differs from the reviewed plan.')
            changes=[]
            for row in plan['charges']:
                charge=lease.rent_charges.select_for_update().get(pk=row['id'],status='posted')
                if str(charge.period_start)!=row['period_start'] or str(charge.period_end)!=row['period_end'] or charge.amount!=Decimal(row['amount']):raise CommandError('Charge amount or service period changed; review again.')
                items=normalize_items(row['income_items'],charge.amount)
                if charge.income_items==items:continue
                if charge.income_items:raise CommandError('Charge already has a different classification; review again.')
                if source_posted('rent-charge:'+str(charge.pk)) or any(source_posted('rent-receipt:'+str(a.receipt_id)) or source_posted('rent-allocation:'+str(a.pk)) for a in charge.allocations.all()):raise CommandError('An affected source is posted to accounting; no records changed.')
                changes.append((charge,items))
                self.stdout.write(f'Charge #{charge.pk}: {charge.amount}; income items {items}; due date retained {charge.due_date}')
            if not changes:
                self.stdout.write('Already classified. No changes.');return
            if not options['apply']:
                self.stdout.write('Preview only. No charges, payments, allocations or journals changed.');return
            if not options['actor_id']:raise CommandError('--actor-id is required when applying.')
            actor=get_user_model().objects.get(pk=options['actor_id'],is_active=True,is_staff=True)
            if not (actor.is_superuser or actor.has_perm('accounting.change_rentcharge')):raise PermissionDenied
            for charge,items in changes:
                data={key:getattr(charge,key) for key in ('period_start','period_end','due_date','amount','notes')};data['income_items']=items
                edit_entry(lease.pk,'charge',charge.pk,data,entry_snapshot(charge,'charge'),plan['reason'],actor)
            self.stdout.write('Saved and audited income classifications. Amounts, dates, payments, allocations and posted sources preserved. No new journals posted.')
        except (ValueError,KeyError,TypeError,OSError,ValidationError) as exc:raise CommandError(str(exc)) from exc
