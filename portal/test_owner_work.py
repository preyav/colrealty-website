from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError,transaction
from django.utils import timezone
from django.template.loader import render_to_string
from django.template import Context
from accounting import test_rent_phase1
from accounting.rent_models import RentReceipt
from portal import test_tenant_work
from portal.tenant_work import save_arrangement,snapshot,eligible_owners
from portal.historical_work import record_completion,snapshot as completion_snapshot,canonical
from portal.templatetags.tenant_work import tenant_work_panel
from owners.models import OwnerProfile,PropertyOwnership
from maintenance.models import WorkOrder
from common.audit.models import AuditEvent

class OwnerWorkTests(TestCase):
    setUpTestData=classmethod(test_rent_phase1.RentPhase1Tests.setUpTestData.__func__)
    def setUp(self):
        test_tenant_work.TenantWorkTests.setUp(self)
        self.owner=OwnerProfile.objects.create(first_name='Owner',last_name='Test')
        self.ownership=PropertyOwnership.objects.create(owner=self.owner,property=self.lease.unit.property)
        self.data={'performer_kind':'owner','owner':self.owner.pk,'agreed_cost':'','terms':'Owner replacing components; no labor charge. Retain receipts.'}
    def save(self):
        self.wo.refresh_from_db()
        return save_arrangement(self.wo.pk,self.data,snapshot(self.wo),self.actor)
    def test_owner_assignment_optional_cost_no_vendor_and_original_approval(self):
        wo=self.save()
        self.assertEqual(wo.performer_owner,self.owner);self.assertIsNone(wo.performer_tenant_id)
        self.assertIsNone(wo.estimated_cost);self.assertIsNone(wo.actual_cost)
        self.assertIsNone(wo.scheduled_for);self.assertEqual(wo.status,'assigned')
        self.assertEqual(wo.approved_at,self.approved_at)
        self.assertFalse(wo.vendor_assignments.exists());self.assertFalse(wo.vendor_invoices.exists())
        self.assertFalse(RentReceipt.objects.exists())
        self.assertTrue(AuditEvent.objects.filter(action='OWNER_WORK_ARRANGED').exists())
    def test_completion_without_cost_and_zero_cost_both_supported(self):
        self.wo=self.save()
        record_completion(self.wo.pk,timezone.now(),None,'Owner completion verified',canonical(completion_snapshot(self.wo)),self.actor)
        self.wo.refresh_from_db();self.mr.refresh_from_db()
        self.assertEqual(self.wo.status,'completed');self.assertIsNone(self.wo.actual_cost)
        self.assertEqual(self.mr.status,'completed');self.assertFalse(self.wo.vendor_invoices.exists())
    def test_zero_cost_renders_as_zero_not_missing(self):
        self.data['agreed_cost']='0.00';self.wo=self.save()
        context=tenant_work_panel(Context(),self.wo)
        html=render_to_string('portal/tenant_work_panel.html',context)
        self.assertIn('$0.00',html);self.assertIn('Owner Test',html)
        self.assertIn('data-work-field="owner"',html)
        record_completion(self.wo.pk,timezone.now(),Decimal('0.00'),'Owner completed at no charge',canonical(completion_snapshot(self.wo)),self.actor)
        self.wo.refresh_from_db();self.assertEqual(self.wo.actual_cost,Decimal('0'))
    def test_other_inactive_future_and_former_owners_rejected(self):
        other=OwnerProfile.objects.create(first_name='Unlinked')
        self.data['owner']=other.pk
        with self.assertRaises(ValidationError):self.save()
        self.data['owner']=self.owner.pk
        for start,end in [(None,timezone.localdate()-timedelta(days=1)),(timezone.localdate()+timedelta(days=1),None)]:
            self.ownership.start_date=start;self.ownership.end_date=end;self.ownership.save()
            with self.assertRaises(ValidationError):self.save()
        self.ownership.start_date=None;self.ownership.end_date=None;self.ownership.save()
        self.owner.is_active=False;self.owner.save()
        with self.assertRaises(ValidationError):self.save()
    def test_active_ownership_elsewhere_does_not_make_former_owner_eligible(self):
        from properties.models import Property
        other=Property.objects.create(street_address='Another property')
        PropertyOwnership.objects.create(property=other,owner=self.owner)
        self.ownership.end_date=timezone.localdate()-timedelta(days=1);self.ownership.save()
        self.assertFalse(eligible_owners(self.wo).filter(pk=self.owner.pk).exists())
        with self.assertRaises(ValidationError):self.save()
    def test_unapproved_work_rejected_and_approved_standalone_allowed(self):
        self.wo.maintenance_request=None;self.wo.save()
        with self.assertRaises(ValidationError):self.save()
        self.wo.approved_by=self.actor;self.wo.approved_at=self.approved_at;self.wo.save()
        self.assertEqual(self.save().performer_owner,self.owner)
    def test_tenant_switch_preserves_audit_and_never_sets_both(self):
        self.wo=self.save()
        self.data={'tenant':self.tenant.pk,'agreed_cost':'300','terms':'Tenant agreement approved'}
        self.wo=self.save()
        self.assertIsNone(self.wo.performer_owner_id);self.assertEqual(self.wo.performer_tenant,self.tenant)
        with self.assertRaises(IntegrityError),transaction.atomic():
            WorkOrder.objects.filter(pk=self.wo.pk).update(performer_owner=self.owner)
        self.assertTrue(AuditEvent.objects.filter(action='OWNER_WORK_ARRANGED').exists())
        self.assertTrue(AuditEvent.objects.filter(action='TENANT_WORK_ARRANGED').exists())
    def test_audit_failure_rolls_back_owner_assignment(self):
        with patch('portal.tenant_work.record_event',side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):self.save()
        self.wo.refresh_from_db();self.assertIsNone(self.wo.performer_owner_id)
    def test_in_progress_arrangement_cannot_be_reassigned(self):
        self.wo=self.save();self.wo.status='in_progress';self.wo.save()
        with self.assertRaises(ValidationError):self.save()
