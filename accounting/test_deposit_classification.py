from decimal import Decimal
from datetime import timedelta
from io import StringIO
from pathlib import Path
import json,tempfile,uuid
from django.test import TestCase
from django.core.management import call_command,CommandError
from django.core.exceptions import ValidationError
from .test_book_accounting import BookAccountingTests as Fixtures
from .rent_models import RentCharge,RentReceipt,RentAllocation
from .book_models import FundsEvent
from .book_services import record_funds
from .book_reports import account_balance
from .rent_services import ledger_data,apply_credit,void_entry
from .lease_financials import financial_timeline


class DepositClassificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Fixtures.setUpTestData.__func__(cls)
        cls.staff.is_superuser=True;cls.staff.save()
        call_command('seed_deposit_classification',verbosity=0)

    def prepare(self):
        date=self.today-timedelta(days=30)
        charge=RentCharge.objects.create(lease=self.lease,period_start=date+timedelta(days=1),period_end=date+timedelta(days=17),due_date=date+timedelta(days=1),amount='1120',created_by=self.staff)
        receipt=RentReceipt.objects.create(lease=self.lease,received_date=date,amount='1700',payment_method='zelle',reference='original-bank-reference',financial_account=self.bank,created_by=self.staff)
        RentAllocation.objects.create(receipt=receipt,charge=charge,amount='1020')
        plan={'token':str(uuid.uuid4()),'expected':{'lease_id':self.lease.pk,'property_id':self.property.pk,'unit_number':self.unit.unit_number,'street_address':self.property.street_address,'receipt_id':receipt.pk,'receipt_amount':'1700','receipt_date':str(date),'charge_id':charge.pk,'charge_amount':'1120','period_start':str(charge.period_start),'period_end':str(charge.period_end)},'split':{'rent':'1020','deposit':'680'},'missing_deposit':{'amount':'1120','date':str(date+timedelta(days=1)),'reference':'missing-deposit-reference'},'reason':'Reviewed combined payment for rent and refundable deposit.'}
        return charge,receipt,plan

    def run_plan(self,plan,apply=True):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'plan.json';path.write_text(json.dumps(plan));out=StringIO()
            call_command('correct_rent_deposit_split',source=str(path),apply=apply,actor_id=self.staff.pk,stdout=out)
            return out.getvalue()

    def test_split_preserves_receipt_and_posts_only_real_cash(self):
        charge,receipt,plan=self.prepare();self.run_plan(plan)
        receipt.refresh_from_db();self.assertEqual(receipt.amount,Decimal('1700'));self.assertEqual(receipt.reference,'original-bank-reference')
        ledger=ledger_data(self.lease);self.assertEqual(ledger['outstanding'],0);self.assertEqual(ledger['credit'],0);self.assertEqual(ledger['deposit_held'],Decimal('1800'))
        self.assertEqual(RentReceipt.objects.filter(lease=self.lease).count(),1)
        for basis in ('cash','accrual'):
            self.assertEqual(account_balance(self.entity,self.asset,self.today,self.property.pk,basis),Decimal('2820'))
            self.assertEqual(account_balance(self.entity,self.config.deposits,self.today,self.property.pk,basis),Decimal('1800'))
            self.assertEqual(account_balance(self.entity,self.income,self.today,self.property.pk,basis),Decimal('1020'))
        timeline=financial_timeline(ledger);self.assertEqual(timeline['balance'],0)
        from .lease_financials import ledger_display_metadata
        display=ledger_display_metadata(self.lease,timeline)
        receipt_row=next(row for row in display['rows'] if row['kind']=='receipt')
        self.assertIn(self.config.deposits.name,receipt_row['account_label'])
        self.assertTrue(any(row['entry'].pk and row['kind']=='funds' and row['amount']==Decimal('-1120') for row in timeline['rows']))
        before=FundsEvent.objects.count();self.assertIn('already applied',self.run_plan(plan));self.assertEqual(FundsEvent.objects.count(),before)
        apply_credit(self.lease.pk,receipt.pk,self.staff);self.assertEqual(ledger_data(self.lease)['credit'],0)
        with self.assertRaises(ValidationError):void_entry(self.lease.pk,'receipt',receipt.pk,'No',self.staff)

    def test_preview_and_disabled_accounting_do_not_mutate(self):
        charge,receipt,plan=self.prepare();self.config.enabled=False;self.config.save()
        self.run_plan(plan,False);self.assertEqual(FundsEvent.objects.count(),0)
        with self.assertRaises(CommandError):self.run_plan(plan)
        charge.refresh_from_db();self.assertEqual(charge.amount,1120)

    def test_duplicate_missing_payment_is_rejected(self):
        charge,receipt,plan=self.prepare()
        RentReceipt.objects.create(lease=self.lease,received_date=plan['missing_deposit']['date'],amount='1120',payment_method='zelle',financial_account=self.bank,created_by=self.staff)
        with self.assertRaises(CommandError):self.run_plan(plan)
        charge.refresh_from_db();self.assertEqual(charge.amount,1120)

    def test_cannot_classify_more_than_credit(self):
        charge,receipt,plan=self.prepare();charge.amount=1020;charge.save()
        with self.assertRaises(ValidationError):
            record_funds({'property':self.property,'lease':self.lease,'kind':'credit_to_deposit','date':receipt.received_date,'amount':Decimal('681'),'receipt':receipt,'reference':'too-much'},uuid.uuid4(),self.staff)
        self.assertFalse(FundsEvent.objects.exists())

    def test_deposit_can_be_refunded_without_becoming_rental_income(self):
        charge,receipt,plan=self.prepare();self.run_plan(plan)
        source=FundsEvent.objects.get(kind='credit_to_deposit',receipt=receipt)
        record_funds({'property':self.property,'lease':self.lease,'kind':'deposit_refund','date':self.today,'amount':Decimal('100'),'bank':self.bank,'source':source,'reference':'deposit-refund'},uuid.uuid4(),self.staff)
        self.assertEqual(ledger_data(self.lease)['deposit_held'],1700)
        self.assertEqual(ledger_data(self.lease)['credit'],0)
        self.assertEqual(financial_timeline(ledger_data(self.lease))['balance'],0)

    def test_whole_correction_rolls_back_on_funds_failure(self):
        from unittest.mock import patch
        charge,receipt,plan=self.prepare()
        with patch('common.management.commands.correct_rent_deposit_split.record_funds',side_effect=ValidationError('Posting failed')):
            with self.assertRaises(ValidationError):self.run_plan(plan)
        charge.refresh_from_db();self.assertEqual(charge.amount,1120)
        self.assertFalse(FundsEvent.objects.exists())

    def test_reconciliation_excludes_deposit_from_unapplied_credit(self):
        from common.management.commands.reconcile_lease_rent import reconcile
        charge,receipt,plan=self.prepare();self.run_plan(plan)
        report=reconcile(self.lease,self.today)
        self.assertEqual(report['summary']['unallocated_credit_through_date'],0)
        self.assertEqual(report['summary']['current_screen_net_all_dates'],0)
        self.assertEqual(report['summary']['net_due_through_date'],0)

    def test_stale_receipt_rejects_before_any_writes(self):
        charge,receipt,plan=self.prepare();receipt.amount=1701;receipt.save()
        with self.assertRaises(CommandError):self.run_plan(plan)
        charge.refresh_from_db();self.assertEqual(charge.amount,1120)
        self.assertFalse(FundsEvent.objects.exists())

    def test_classification_rejects_a_finalized_bank_period(self):
        from .book_models import BankReconciliation
        charge,receipt,plan=self.prepare()
        BankReconciliation.objects.create(entity_bank=self.entity_bank,statement_start=receipt.received_date-timedelta(days=1),statement_end=self.today,opening_balance=0,closing_balance=0,status='final',finalized_by=self.staff)
        with self.assertRaises(ValidationError):
            record_funds({'property':self.property,'lease':self.lease,'kind':'credit_to_deposit','date':receipt.received_date,'amount':Decimal('680'),'receipt':receipt,'reference':'closed-period'},uuid.uuid4(),self.staff)
        self.assertFalse(FundsEvent.objects.exists())
