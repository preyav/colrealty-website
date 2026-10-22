"""Transaction tests that must execute on PostgreSQL, never an alternate backend."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DatabaseError, IntegrityError, connection, connections, transaction
from django.db.transaction import TransactionManagementError
from django.test import TransactionTestCase
from django.utils import timezone
from properties.models import Property, PropertyUnit
from leasing.models import Lease
from maintenance.models import WorkOrder
from .rent_models import RentCharge, RentReceipt
from .rent_services import post_receipt


class PostgreSQLTransactionTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        if connection.vendor != 'postgresql':
            raise RuntimeError('These tests require PostgreSQL. Refusing to skip or substitute another backend.')
        super().setUpClass()

    def setUp(self):
        call_command('seed_rent_ledger', verbosity=0)
        self.actor = get_user_model().objects.create(username='pg_validation', is_staff=True, is_active=True)
        prop = Property.objects.create(street_address='PostgreSQL test property')
        unit = PropertyUnit.objects.create(property=prop, unit_number='1')
        today = timezone.localdate()
        self.lease = Lease.objects.create(unit=unit, start_date=today-timedelta(days=1),
                                         end_date=today+timedelta(days=365), monthly_rent=Decimal('100'), status='active')
        self.receipt = RentReceipt.objects.create(lease=self.lease, received_date=today,
                        amount=Decimal('10'), payment_method='check', created_by=self.actor)

    def test_nullable_bank_join_locks_only_receipt(self):
        with transaction.atomic():
            receipt = RentReceipt.objects.select_for_update(of=('self',)).select_related('financial_account').get(pk=self.receipt.pk)
            self.assertIsNone(receipt.financial_account_id)

    def test_nullable_request_join_locks_only_work_order(self):
        wo = WorkOrder.objects.create(unit=self.lease.unit, title='Unlinked request', description='Test')
        with transaction.atomic():
            row = WorkOrder.objects.select_for_update(of=('self',)).select_related('maintenance_request__lease', 'unit__property').get(pk=wo.pk)
            self.assertIsNone(row.maintenance_request_id)

    def test_select_for_update_requires_a_real_transaction(self):
        with self.assertRaises(TransactionManagementError):
            RentReceipt.objects.select_for_update().get(pk=self.receipt.pk)

    def test_second_connection_cannot_lock_an_already_locked_receipt(self):
        pk = self.receipt.pk
        def competing_lock():
            try:
                with transaction.atomic():
                    RentReceipt.objects.select_for_update(nowait=True).get(pk=pk)
                return False
            except DatabaseError as exc:
                cause = exc.__cause__
                return getattr(cause, 'sqlstate', getattr(cause, 'pgcode', None)) == '55P03'
            finally:
                connections['default'].close()
        with transaction.atomic():
            RentReceipt.objects.select_for_update().get(pk=pk)
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.assertTrue(pool.submit(competing_lock).result(timeout=10))

    def test_live_charge_constraint_enforced_by_postgresql(self):
        today = timezone.localdate()
        values = dict(lease=self.lease, period_start=today, period_end=today,
                      due_date=today, amount=Decimal('10'), created_by=self.actor)
        RentCharge.objects.create(**values)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RentCharge.objects.create(**values)

    def test_receipt_audit_failure_rolls_back_transaction(self):
        count = RentReceipt.objects.count()
        with patch('accounting.rent_services.audit', side_effect=RuntimeError('Test audit failure')):
            with self.assertRaises(RuntimeError):
                post_receipt(self.lease.pk, self.receipt_data(), uuid.uuid4(), self.actor)
        self.assertEqual(RentReceipt.objects.count(), count)

    def receipt_data(self):
        return dict(received_date=timezone.localdate(), amount=Decimal('10'), payment_method='check',
                    reference='', financial_account=None, notes='PostgreSQL validation')

    def test_simultaneous_duplicate_receipts_produce_one_record(self):
        gate = Barrier(2)
        lease_id, actor_id, token = self.lease.pk, self.actor.pk, uuid.uuid4()
        data = self.receipt_data()
        def submit():
            try:
                with connections['default'].cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                actor = get_user_model().objects.get(pk=actor_id)
                gate.wait(timeout=5)
                return post_receipt(lease_id, data, token, actor).pk
            finally:
                connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(submit) for _ in range(2)]
            ids = [future.result(timeout=15) for future in futures]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(RentReceipt.objects.filter(entry_token=token).count(), 1)
