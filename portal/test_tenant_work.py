from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, RequestFactory
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.management import call_command
from django.core import signing
from django.template.loader import render_to_string
from django.utils import timezone
from django.urls import reverse
from accounting import test_rent_phase1
from accounting.rent_models import RentReceipt
from maintenance.models import MaintenanceRequest, WorkOrder, VendorAssignment
from tenants.models import TenantProfile
from leasing.models import LeaseTenant
from vendors.models import Vendor
from common.audit.models import AuditEvent
from portal.tenant_work import save_arrangement, snapshot, vendor_work_only
from portal.historical_work import record_completion, snapshot as completion_snapshot, canonical

class TenantWorkTests(TestCase):
    setUpTestData=classmethod(test_rent_phase1.RentPhase1Tests.setUpTestData.__func__)
    def setUp(self):
        call_command('seed_tenant_work',verbosity=0)
        call_command('seed_work_completion',verbosity=0)
        self.actor.is_superuser=True; self.actor.save()
        self.tenant=TenantProfile.objects.create(first_name='Dirk',last_name='Test')
        LeaseTenant.objects.create(lease=self.lease,tenant=self.tenant)
        self.approved_at=timezone.now()-timedelta(days=2)
        self.mr=MaintenanceRequest.objects.create(unit=self.lease.unit,lease=self.lease,reported_by_tenant=self.tenant,title='Toilets',description='Tenant offer',status='converted',reviewed_by=self.actor,reviewed_at=self.approved_at)
        self.wo=WorkOrder.objects.create(unit=self.lease.unit,maintenance_request=self.mr,title='Repair',description='Repair',estimated_cost=300,scheduled_for=timezone.now()+timedelta(days=4))
        self.wo.refresh_from_db()
        self.data={'tenant':self.tenant.pk,'agreed_cost':'300.00','terms':'Agreed $300 including time and materials. Reimbursement after review.'}
    def save(self):
        self.wo.refresh_from_db()
        return save_arrangement(self.wo.pk,self.data,snapshot(self.wo),self.actor)
    def test_save_clears_unconfirmed_schedule_preserves_approval_no_financial_records(self):
        previous=self.wo.scheduled_for
        self.assertEqual(self.wo.approval_actor,self.actor)
        self.assertEqual(self.wo.approval_time,self.approved_at)
        wo=self.save()
        self.assertEqual(wo.performer_tenant,self.tenant)
        self.assertEqual(wo.estimated_cost,Decimal('300'))
        self.assertIsNone(wo.scheduled_for);self.assertIsNone(wo.tenant_expected_completion)
        self.assertEqual(wo.status,'assigned');self.assertEqual(wo.approved_at,self.approved_at)
        self.assertFalse(wo.vendor_assignments.exists());self.assertFalse(wo.vendor_invoices.exists())
        self.assertFalse(RentReceipt.objects.exists());self.assertIsNone(wo.actual_cost)
        event=AuditEvent.objects.get(action='TENANT_WORK_ARRANGED')
        self.assertIn(str(previous),str(event.old_values))
    def test_confirmed_schedule_and_end_order(self):
        start=timezone.now()+timedelta(days=5)
        self.data.update(schedule_confirmed='on',scheduled_for=start.strftime('%Y-%m-%dT%H:%M'),expected_completion=(start-timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'))
        with self.assertRaises(ValidationError):self.save()
        self.data['expected_completion']=(start+timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M')
        self.assertEqual(self.save().status,'scheduled')
    def test_foreign_tenant_unapproved_request_and_vendor_conflict_rejected(self):
        other=TenantProfile.objects.create(first_name='Other',last_name='Tenant')
        self.data['tenant']=other.pk
        with self.assertRaises(ValidationError):self.save()
        self.data['tenant']=self.tenant.pk
        self.mr.reviewed_at=None;self.mr.save()
        with self.assertRaises(ValidationError):self.save()
        self.mr.reviewed_at=self.approved_at;self.mr.save()
        vendor=Vendor.objects.create(name='Vendor')
        VendorAssignment.objects.create(work_order=self.wo,vendor=vendor)
        with self.assertRaises(ValidationError):self.save()
    def test_permissions_stale_and_audit_rollback(self):
        with self.assertRaises(PermissionDenied):save_arrangement(self.wo.pk,self.data,snapshot(self.wo),self.other)
        old=snapshot(self.wo);self.wo.notes='Changed';self.wo.save()
        with self.assertRaises(ValidationError):save_arrangement(self.wo.pk,self.data,old,self.actor)
        with patch('portal.tenant_work.record_event',side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):self.save()
        self.wo.refresh_from_db();self.assertIsNone(self.wo.performer_tenant_id)
    def test_tenant_completion_without_vendor_closes_request_no_bill(self):
        self.wo=self.save()
        when=timezone.now()-timedelta(minutes=1)
        record_completion(self.wo.pk,when,Decimal('300'),'Tenant work verified',canonical(completion_snapshot(self.wo)),self.actor)
        self.wo.refresh_from_db();self.mr.refresh_from_db()
        self.assertEqual(self.wo.status,'completed');self.assertEqual(self.mr.status,'completed')
        self.assertFalse(self.wo.vendor_invoices.exists());self.assertFalse(RentReceipt.objects.exists())
    def test_completion_requires_actual_cost_within_agreed_total(self):
        self.wo=self.save()
        for cost in (None,Decimal('301')):
            with self.assertRaises(ValidationError):record_completion(self.wo.pk,timezone.now(),cost,'Verified',canonical(completion_snapshot(self.wo)),self.actor)
    def test_post_and_panel_keep_schedule_unconfirmed(self):
        self.client.force_login(self.actor)
        stamp=signing.dumps({'id':self.wo.pk,'values':snapshot(self.wo)},salt='tenant-work')
        response=self.client.post(reverse('portal:save_tenant_work',args=[self.wo.pk]),{**self.data,'version':stamp})
        self.assertEqual(response.status_code,302)
        self.assertFalse([str(m) for m in response.wsgi_request._messages if m.level_tag == 'error'])
        self.wo.refresh_from_db()
        html=render_to_string('portal/tenant_work_panel.html',{'work_order':self.wo,'ui':__import__('portal.tenant_work',fromlist=['wording']).wording()})
        self.assertIn('Schedule not yet confirmed',html)
        self.assertIn('300.00',html)
        self.assertIn('No reimbursement, invoice, payment or rent credit',html)
    def test_seed_preserves_custom_labels(self):
        from common.models import FormFieldSetting
        setting=FormFieldSetting.objects.get(form_key='tenant_work',field_key='ui')
        setting.option_labels['title']='Tenant repair arrangement';setting.save()
        call_command('seed_tenant_work',verbosity=0);setting.refresh_from_db()
        self.assertEqual(setting.option_labels['title'],'Tenant repair arrangement')

    def test_vendor_action_rejected_for_tenant_work(self):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.http import HttpResponse
        request=RequestFactory().post('/vendor/')
        request.session={};request._messages=FallbackStorage(request)
        called=[]
        @vendor_work_only
        def vendor_action(request,work_order_id):
            called.append(work_order_id)
            return HttpResponse('Vendor path')
        self.assertEqual(vendor_action(request,self.wo.pk).status_code,200)
        self.save();called.clear()
        self.assertEqual(vendor_action(request,self.wo.pk).status_code,302)
        self.assertEqual(called,[])
