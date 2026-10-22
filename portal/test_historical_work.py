from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
from accounting.test_rent_phase1 import RentPhase1Tests
from maintenance.models import WorkOrder,VendorAssignment
from vendors.models import Vendor
from portal.historical_work import record_completion,snapshot,canonical
from common.audit.models import AuditEvent

class HistoricalWorkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        RentPhase1Tests.setUpTestData.__func__(cls)
        call_command('seed_work_completion',verbosity=0)
    def setUp(self):
        self.actor.is_superuser=True;self.actor.save()
        self.wo=WorkOrder.objects.create(unit=self.lease.unit,title='Repair',description='Repair',status='assigned')
        self.vendor=Vendor.objects.create(name='Actual technician')
        self.assignment=VendorAssignment.objects.create(work_order=self.wo,vendor=self.vendor,status='assigned')
        self.when=timezone.now()-timedelta(days=10)
    def save_completion(self):
        return record_completion(self.wo.pk,self.when,None,'Historical repair confirmed',canonical(snapshot(self.wo)),self.actor)
    def test_actual_date_preserved_and_audited_without_bill(self):
        self.save_completion();self.wo.refresh_from_db();self.assignment.refresh_from_db()
        self.assertEqual(self.wo.completed_at,self.when)
        self.assertIsNone(self.wo.started_at);self.assertIsNone(self.wo.actual_cost)
        self.assertEqual(self.assignment.status,'completed')
        self.assertEqual(self.wo.vendor_invoices.count(),0)
        self.assertEqual(self.wo.status_history.get().from_status,'assigned')
        self.assertTrue(AuditEvent.objects.filter(action='WORK_ORDER_COMPLETED').exists())
    def test_future_stale_cancelled_and_rollback(self):
        before=canonical(snapshot(self.wo))
        with self.assertRaises(ValidationError):record_completion(self.wo.pk,timezone.now()+timedelta(days=1),None,'Reason',before,self.actor)
        with patch('portal.historical_work.record_event',side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):self.save_completion()
        self.wo.refresh_from_db();self.assignment.refresh_from_db()
        self.assertEqual(self.wo.status,'assigned');self.assertEqual(self.assignment.status,'assigned')
        self.wo.status='cancelled';self.wo.save()
        with self.assertRaises(ValidationError):self.save_completion()
        with self.assertRaises(ValidationError):record_completion(self.wo.pk,self.when,None,'Reason',before,self.actor)
    def test_form_and_permissions(self):
        self.client.force_login(self.actor)
        url=reverse('portal:record_work_completion',args=[self.wo.pk])
        response=self.client.get(url);self.assertEqual(response.status_code,200)
        response=self.client.post(url,{'version':response.context['version'],'completed_at':timezone.localtime(self.when).strftime('%Y-%m-%dT%H:%M'),'actual_cost':'','notes':'Repair performed before entry'})
        self.assertEqual(response.status_code,302)
        self.wo.refresh_from_db();self.assertEqual(self.wo.status,'completed')
        self.actor.is_superuser=False;self.actor.save();self.client.force_login(self.actor)
        self.assertEqual(self.client.get(url).status_code,403)
