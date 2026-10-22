"""Fill missing supplemental fields from a reviewed executed-lease extraction."""
import json
import re
from decimal import Decimal
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from common.audit.services import record_event
from leasing.models import Lease
from portal.forms import LeaseForm

def normalized(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())

class Command(BaseCommand):
    help = 'Preview or fill missing supplemental lease fields. Core terms and existing values are preserved.'

    def add_arguments(self, parser):
        parser.add_argument('--lease-id', type=int, required=True)
        parser.add_argument('--source', required=True)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--actor-id', type=int)

    def handle(self, *args, **options):
        try:
            payload = json.loads(Path(options['source']).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise CommandError('Cannot read extraction file.') from exc
        expected = payload.get('expected', {})
        required = ('street_address','start_date','end_date','monthly_rent','security_deposit')
        if not all(expected.get(k) for k in required):
            raise CommandError('Extraction must identify the property and original core lease terms.')
        with transaction.atomic():
            try:
                lease = Lease.objects.select_for_update().select_related('unit__property').get(pk=options['lease_id'])
            except Lease.DoesNotExist as exc:
                raise CommandError('Lease record not found.') from exc
            address = lease.unit.property.street_address
            if normalized(address) != normalized(expected['street_address']):
                raise CommandError('Property mismatch. This extraction belongs to ' + expected['street_address'])
            for field in ('start_date','end_date'):
                if str(getattr(lease, field)) != expected[field]:
                    raise CommandError(field + ' does not match the supplied executed lease. Review the record and any amendments first.')
            for field in ('monthly_rent','security_deposit'):
                try:
                    matches = getattr(lease, field) == Decimal(expected[field])
                except Exception as exc:
                    raise CommandError('Invalid expected amount.') from exc
                if not matches:
                    raise CommandError(field + ' does not match the supplied executed lease. Review amendments first.')
            form = LeaseForm(instance=lease, locked_unit=lease.unit)
            current = dict(lease.contract_details or {})
            incoming = payload.get('contract_details')
            if not isinstance(incoming, dict):
                raise CommandError('Missing contract_details dictionary.')
            additions = {}
            conflicts = []
            for key, value in incoming.items():
                field = form.fields.get('contract_' + key)
                if field is None:
                    raise CommandError('Unknown supplemental field: ' + key)
                try:
                    cleaned = field.clean(value)
                except Exception as exc:
                    raise CommandError('Invalid extraction value for ' + key + ': ' + str(exc)) from exc
                candidate = '' if cleaned is None else str(cleaned)
                if current.get(key) not in (None, ''):
                    if str(current[key]) != candidate:
                        conflicts.append(key)
                elif candidate:
                    additions[key] = candidate
            self.stdout.write(f'Lease #{lease.pk}: {address}; {len(additions)} missing fields can be filled.')
            for key in additions:
                self.stdout.write('  ' + key)
            if conflicts:
                self.stdout.write('Existing values preserved: ' + ', '.join(conflicts))
            for note in payload.get('review_notes', []):
                self.stdout.write('Review: ' + note)
            if not options['apply']:
                self.stdout.write('Preview only. Nothing saved.')
                return
            if not options.get('actor_id'):
                raise CommandError('--actor-id is required when applying the import.')
            actor = get_user_model().objects.filter(pk=options['actor_id'], is_active=True, is_staff=True).first()
            if actor is None:
                raise CommandError('Actor must be an active staff user.')
            if not additions:
                self.stdout.write('No missing values to import.')
                return
            lease.contract_details = {**current, **additions}
            lease.save(update_fields=['contract_details','updated_at'])
            record_event(action='LEASE_EXECUTED_DETAILS_IMPORTED', instance=lease, actor=actor, request=None,
                old_values={key:current.get(key) for key in additions}, new_values=additions,
                reason='Missing fields transcribed from the existing executed agreement; contract terms not amended.',
                property_id=lease.unit.property_id,
                metadata={'source':payload.get('source',''), 'review_notes':payload.get('review_notes',[])})
            self.stdout.write(self.style.SUCCESS('Missing details saved. Core terms and existing values unchanged.'))
