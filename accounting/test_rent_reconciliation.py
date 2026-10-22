from datetime import timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory
from pathlib import Path
from django.test import TestCase
from django.utils import timezone
from django.core.management import call_command,CommandError
from .test_rent_phase1 import RentPhase1Tests
from .rent_models import RentCharge,RentReceipt,RentAllocation
from common.management.commands.reconcile_lease_rent import reconcile

class RentReconciliationTests(TestCase):
    @classmethod
    def setUpTestData(cls):RentPhase1Tests.setUpTestData.__func__(cls)

    def test_due_future_and_credit_are_separate_without_writes(self):
        today=timezone.localdate()
        def charge(day):return RentCharge.objects.create(lease=self.lease,period_start=day,period_end=day, due_date=day,amount='2400',created_by=self.actor)
        overdue=charge(today-timedelta(days=30));due=charge(today);future=charge(today+timedelta(days=30))
        receipt=RentReceipt.objects.create(lease=self.lease,received_date=today,amount='2600',payment_method='check',created_by=self.actor)
        RentAllocation.objects.create(receipt=receipt,charge=overdue,amount='2400')
        before=list(RentCharge.objects.values()),list(RentReceipt.objects.values()),list(RentAllocation.objects.values())
        report=reconcile(self.lease,today);s=report['summary']
        self.assertEqual(s['current_screen_net_all_dates'],Decimal('4600'))
        self.assertEqual(s['overdue_unpaid'],0)
        self.assertEqual(s['due_today_unpaid'],Decimal('2400'))
        self.assertEqual(s['future_due_unpaid'],Decimal('2400'))
        self.assertEqual(s['unallocated_credit_through_date'],Decimal('200'))
        self.assertEqual(s['net_due_through_date'],Decimal('2200'))
        self.assertEqual(before,(list(RentCharge.objects.values()),list(RentReceipt.objects.values()),list(RentAllocation.objects.values())))

    def test_void_future_payments_and_existing_output(self):
        today=timezone.localdate()
        RentCharge.objects.create(lease=self.lease,period_start=today,period_end=today,due_date=today,amount='1000',status='void',created_by=self.actor)
        RentReceipt.objects.create(lease=self.lease,received_date=today+timedelta(days=10),amount='50',payment_method='check',created_by=self.actor)
        summary=reconcile(self.lease,today)['summary']
        self.assertEqual(summary['posted_charges_all_dates'],0)
        self.assertEqual(summary['future_dated_payments'],Decimal('50'))
        self.assertEqual(summary['payments_through_date'],0)
        with TemporaryDirectory() as folder:
            path=Path(folder)/'report.json'
            call_command('reconcile_lease_rent',lease=self.lease.pk,output=str(path),verbosity=0)
            self.assertTrue(path.exists())
            with self.assertRaises(CommandError):call_command('reconcile_lease_rent',lease=self.lease.pk,output=str(path),verbosity=0)
