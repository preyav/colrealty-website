import json
import tempfile
from pathlib import Path
from io import StringIO
from datetime import timedelta
from django.test import TestCase
from django.core.management import call_command, CommandError
from accounting.test_book_accounting import BookAccountingTests as Fixtures
from common.audit.models import AuditEvent


class TranscriptionCorrectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Fixtures.setUpTestData.__func__(cls)
        cls.staff.is_superuser=True;cls.staff.save()
        cls.unit.unit_number='1602';cls.unit.save()
        cls.property.unit_number='1607';cls.property.save()

    def plan(self):
        return {'expected':{'lease_id':self.lease.pk,'property_id':self.property.pk,'unit_id':self.unit.pk,'street_address':self.property.street_address,'unit_number':'1602','start_date':str(self.lease.start_date),'monthly_rent':str(self.lease.monthly_rent),'security_deposit':str(self.lease.security_deposit),'status':'active'},'before':{'property_unit_number':'1607','end_date':str(self.lease.end_date)},'after':{'property_unit_number':'1602','end_date':str(self.lease.end_date+timedelta(days=1))},'reason':'Reviewed signed lease transcription correction'}

    def run_plan(self, plan, apply=False):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'plan.json';p.write_text(json.dumps(plan))
            out=StringIO();call_command('correct_lease_transcription',source=str(p),apply=apply,actor_id=self.staff.pk,stdout=out)
            return out.getvalue()

    def test_preview_does_not_mutate(self):
        end=self.lease.end_date
        self.run_plan(self.plan())
        self.property.refresh_from_db();self.lease.refresh_from_db()
        self.assertEqual(self.property.unit_number,'1607');self.assertEqual(self.lease.end_date,end)

    def test_apply_is_audited_preserves_unit_and_is_repeatable(self):
        plan=self.plan();unit=self.lease.unit_id
        self.run_plan(plan,True)
        self.property.refresh_from_db();self.lease.refresh_from_db()
        self.assertEqual(self.property.unit_number,'1602');self.assertEqual(str(self.lease.end_date),plan['after']['end_date']);self.assertEqual(self.lease.unit_id,unit)
        self.assertTrue(AuditEvent.objects.filter(action='LEASE_TRANSCRIPTION_CORRECTED').exists())
        self.assertIn('already applied',self.run_plan(plan,True))

    def test_stale_before_values_rejected(self):
        plan=self.plan();plan['before']['property_unit_number']='wrong'
        with self.assertRaises(CommandError):self.run_plan(plan,True)
        self.lease.refresh_from_db();self.property.refresh_from_db();self.assertEqual(self.property.unit_number,'1607')

    def test_unauthorized_actor_does_not_change_records(self):
        self.staff.is_superuser=False;self.staff.save()
        with self.assertRaises(CommandError):self.run_plan(self.plan(),True)
        self.property.refresh_from_db();self.assertEqual(self.property.unit_number,'1607')
