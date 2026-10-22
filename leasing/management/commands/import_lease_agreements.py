import json
import re
from pathlib import Path
from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from common.audit.services import record_event
from leasing.models import Lease,LeaseAgreement
from leasing.agreement_forms import LeaseAgreementForm

class Command(BaseCommand):
    help='Preview/import reviewed executed agreement history without changing the original lease.'
    def add_arguments(self,p):
        p.add_argument('--lease-id',required=True,type=int);p.add_argument('--source',required=True)
        p.add_argument('--apply',action='store_true');p.add_argument('--actor-id',type=int)
    def handle(self,*args,**options):
        try:payload=json.loads(Path(options['source']).read_text(encoding='utf-8'))
        except (OSError,ValueError) as exc:raise CommandError('Cannot read agreement extraction.') from exc
        norm=lambda s:re.sub(r'[^a-z0-9]','',str(s).lower().replace(' cove',' cv'))
        with transaction.atomic():
            try:lease=Lease.objects.select_for_update().select_related('unit__property').get(pk=options['lease_id'])
            except Lease.DoesNotExist as exc:raise CommandError('Lease not found.') from exc
            if norm(lease.unit.property.street_address)!=norm(payload.get('street_address','')):
                raise CommandError('Property mismatch.')
            if str(lease.start_date)!=payload.get('base_start_date') or str(lease.end_date)!=payload.get('base_end_date'):
                raise CommandError('Base lease dates do not match the extraction.')
            prepared=[]
            for item in payload.get('agreements',[]):
                if lease.agreements.filter(source_key=item['source_key']).exists():
                    self.stdout.write('Already recorded: '+item['title']);continue
                form=LeaseAgreementForm({**item,'change_reason':'Executed document history transcription.'})
                if not form.is_valid():raise CommandError(str(form.errors))
                prepared.append((item,form))
                self.stdout.write('Ready: '+item['title'])
            if not options['apply']:
                self.stdout.write('Preview only; no changes saved.');return
            actor=get_user_model().objects.filter(pk=options.get('actor_id'),is_staff=True,is_active=True).first()
            if not actor:raise CommandError('Provide an active staff --actor-id.')
            for item,form in prepared:
                agreement=form.save(commit=False);agreement.lease=lease;agreement.recorded_by=actor;agreement.source_key=item['source_key'];agreement.save()
                record_event(action='LEASE_AGREEMENT_IMPORTED',instance=lease,actor=actor,request=None,
                    old_values={},new_values={'agreement_id':agreement.pk,'title':agreement.title},
                    reason='Executed extension transcribed; original lease preserved.',property_id=lease.unit.property_id,
                    metadata={'source':item.get('source_file','')})
            self.stdout.write(self.style.SUCCESS(f'{len(prepared)} agreements imported. Original lease unchanged.'))
