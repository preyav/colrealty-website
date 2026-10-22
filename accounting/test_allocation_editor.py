from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from .test_rent_phase1 import RentPhase1Tests
from .allocation_editor import replace_allocations,snapshot
from .rent_services import void_entry
from .rent_models import RentAllocation
from common.audit.models import AuditEvent

class AllocationEditorTests(TestCase):
    setUpTestData=classmethod(RentPhase1Tests.setUpTestData.__func__)
    charge=RentPhase1Tests.charge
    receipt=RentPhase1Tests.receipt
    def setUp(self):
        call_command('seed_rent_allocations',verbosity=0)
        self.actor.is_superuser=True;self.actor.save()
    def test_swap_and_preserve_void_history(self):
        import uuid
        c1=self.charge('1000');c2=self.charge('1000',offset=30)
        r1=self.receipt();r1.reference='one';r1.save()
        r2=self.receipt();r2.reference='two';r2.save()
        void_entry(self.lease.pk,'receipt',r2.pk,'Test',self.actor)
        oldid=r2.allocations.get().pk
        r3=self.receipt()
        before=snapshot(self.lease)
        replace_allocations(self.lease.pk,{(r1.pk,c2.pk):'1000',(r3.pk,c1.pk):'1000'},before,'Correct periods',self.actor)
        self.assertEqual(r1.allocations.get().charge_id,c2.pk)
        self.assertTrue(RentAllocation.objects.filter(pk=oldid).exists())
        self.assertTrue(AuditEvent.objects.filter(action='RENT_ALLOCATIONS_CORRECTED').exists())
        with self.assertRaises(ValidationError):replace_allocations(self.lease.pk,{},before,'Stale',self.actor)
    def test_overallocation_and_audit_failure_rollback(self):
        c=self.charge();r=self.receipt();before=snapshot(self.lease)
        with self.assertRaises(ValidationError):replace_allocations(self.lease.pk,{(r.pk,c.pk):'1001'},before,'Oops',self.actor)
        with patch('accounting.allocation_editor.audit',side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):replace_allocations(self.lease.pk,{},before,'Clear',self.actor)
        self.assertEqual(snapshot(self.lease),before)
    def test_view_post_and_permissions(self):
        c=self.charge();r=self.receipt();self.client.force_login(self.actor)
        url=reverse('portal:rent_allocations',args=[self.lease.pk])
        response=self.client.get(url);self.assertEqual(response.status_code,200)
        response=self.client.post(url,{'entry_token':response.context['entry_token'],'reason':'Partial','a_%s_%s'%(r.pk,c.pk):'500'})
        self.assertEqual(response.status_code,302);self.assertEqual(r.allocations.get().amount,Decimal('500'))
        self.actor.is_superuser=False;self.actor.save();self.client.force_login(self.actor)
        self.assertEqual(self.client.get(url).status_code,403)
    def test_posted_property_blocked(self):
        from .journal_models import JournalEntry
        from django.utils import timezone
        c=self.charge();r=self.receipt();before=snapshot(self.lease)
        JournalEntry.objects.create(property=self.lease.unit.property,date=timezone.localdate(),memo='Existing',created_by=self.actor)
        with self.assertRaises(ValidationError):replace_allocations(self.lease.pk,{},before,'Clear',self.actor)
        self.assertEqual(snapshot(self.lease),before)
