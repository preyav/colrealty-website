"""Apply a reviewed property-label / expiration transcription correction."""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from common.audit.services import record_event
from leasing.models import Lease
from properties.models import Property, PropertyUnit


class Command(BaseCommand):
    help = 'Preview or apply a reviewed label/date correction; preserve unit links and transactions.'

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--actor-id', type=int)

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            plan=json.loads(Path(options['source']).read_text(encoding='utf-8'))
            expected=plan['expected']; before=plan['before']; after=plan['after']
            new_end=date.fromisoformat(after['end_date'])
            old_end=date.fromisoformat(before['end_date'])
            reason=plan['reason'].strip()
            if not reason or not str(after['property_unit_number']).strip():
                raise ValueError('Missing reason or new unit number')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise CommandError('Invalid or unreadable correction plan.') from exc
        try:
            prop=Property.objects.select_for_update().get(pk=expected['property_id'])
            unit=PropertyUnit.objects.select_for_update().get(pk=expected['unit_id'],property=prop)
            lease=Lease.objects.select_for_update().get(pk=expected['lease_id'],unit=unit)
        except (Property.DoesNotExist, PropertyUnit.DoesNotExist, Lease.DoesNotExist) as exc:
            raise CommandError('Property/unit/lease relationship differs from the reviewed plan.') from exc
        if (prop.street_address != expected['street_address'] or unit.unit_number != expected['unit_number']
                or str(lease.start_date) != expected['start_date']
                or lease.monthly_rent != Decimal(expected['monthly_rent'])
                or lease.security_deposit != Decimal(expected['security_deposit'])
                or lease.status != expected['status']):
            raise CommandError('Record identity or core terms changed. Review before correcting.')
        if str(after['property_unit_number']) != unit.unit_number:
            raise CommandError('Corrected property label must match the existing linked unit.')
        if prop.units.exclude(pk=unit.pk).exists():
            raise CommandError('This label correction requires a single-unit property.')
        if prop.unit_number == after['property_unit_number'] and lease.end_date == new_end:
            self.stdout.write('Correction already applied. Nothing changed.')
            return
        if prop.unit_number != before['property_unit_number'] or lease.end_date != old_end:
            raise CommandError('Current values differ from the reviewed before-values. Nothing changed.')
        if new_end < lease.start_date:
            raise CommandError('Expiration cannot precede commencement.')
        if lease.agreements.filter(status='executed',expiration_date__isnull=False).exists():
            raise CommandError('An executed continuation changes expiration. Review its terms first.')
        if Lease.objects.filter(unit=unit,status__in=['draft','pending','active','notice'],start_date__lte=new_end,end_date__gte=lease.start_date).exclude(pk=lease.pk).exists():
            raise CommandError('Corrected term overlaps another lease. Review before correcting.')
        self.stdout.write(f'Lease #{lease.pk}; Property #{prop.pk}; existing Unit #{unit.pk} ({unit.unit_number})')
        self.stdout.write(f'Property unit label: {prop.unit_number} -> {after["property_unit_number"]}')
        self.stdout.write(f'Lease expiration: {lease.end_date} -> {new_end}')
        if not options['apply']:
            self.stdout.write('Preview only. Nothing saved.')
            return
        actor=get_user_model().objects.filter(pk=options.get('actor_id'),is_active=True,is_staff=True).first()
        if actor is None or not (actor.is_superuser or (actor.has_perm('leasing.change_lease') and actor.has_perm('properties.change_property'))):
            raise CommandError('An active staff actor with lease and property change permissions is required.')
        old_values={'property_unit_number':prop.unit_number,'end_date':str(lease.end_date)}
        prop.unit_number=after['property_unit_number']
        prop.save(update_fields=['unit_number'])
        lease.end_date=new_end
        lease.save(update_fields=['end_date','updated_at'])
        record_event(action='LEASE_TRANSCRIPTION_CORRECTED',instance=lease,actor=actor,request=None,
            old_values=old_values,new_values={'property_unit_number':prop.unit_number,'end_date':str(new_end)},
            reason=reason,property_id=prop.pk,metadata={'unit_id':unit.pk,'property_id':prop.pk,'source':plan.get('source',''),'unit_relationship_changed':False})
        self.stdout.write(self.style.SUCCESS('Correction saved and audited. Unit relationship and transactions unchanged.'))
