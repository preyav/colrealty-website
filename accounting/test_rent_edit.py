from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.urls import reverse
from common.audit.models import AuditEvent
from .test_rent_phase1 import RentPhase1Tests
from .rent_services import edit_entry, entry_snapshot, ledger_data

class RentEditTests(TestCase):
    setUpTestData = classmethod(RentPhase1Tests.setUpTestData.__func__)
    charge = RentPhase1Tests.charge
    receipt = RentPhase1Tests.receipt
    def setUp(self):
        call_command('seed_rent_entry_actions', verbosity=0)
    def test_date_edit_preserves_allocation_and_audits(self):
        self.charge(); entry=self.receipt()
        old=entry_snapshot(entry,'receipt'); data={k:getattr(entry,k) for k in ('received_date','amount','payment_method','reference','financial_account','notes')}
        data['received_date']-=timedelta(days=1)
        edit_entry(self.lease.pk,'receipt',entry.pk,data,old,'Correct date',self.actor)
        self.assertEqual(ledger_data(self.lease)['received'],Decimal('1000'))
        self.assertEqual(entry.allocations.count(),1)
        self.assertTrue(AuditEvent.objects.filter(action='RENT_RECEIPT_EDITED').exists())
        with self.assertRaises(ValidationError):
            edit_entry(self.lease.pk,'receipt',entry.pk,data,old,'Stale',self.actor)
    def test_cannot_reduce_below_allocated(self):
        self.charge(); entry=self.receipt()
        old=entry_snapshot(entry,'receipt'); data={k:getattr(entry,k) for k in ('received_date','amount','payment_method','reference','financial_account','notes')};data['amount']=Decimal('1')
        with self.assertRaises(ValidationError):edit_entry(self.lease.pk,'receipt',entry.pk,data,old,'Correction',self.actor)
        entry.refresh_from_db();self.assertEqual(entry.amount,Decimal('1000'))
    def test_edit_view_and_submit(self):
        entry=self.receipt();self.client.force_login(self.actor)
        url=reverse('portal:rent_edit',args=[self.lease.pk,'receipt',entry.pk])
        response=self.client.get(url);self.assertEqual(response.status_code,200)
        response=self.client.post(url,{'received_date':str(entry.received_date),'amount':'1000','payment_method':'check','reference':'Corrected','financial_account':'','notes':'','reason':'Reference correction','entry_token':response.context['entry_token']})
        self.assertEqual(response.status_code,302);entry.refresh_from_db();self.assertEqual(entry.reference,'Corrected')
