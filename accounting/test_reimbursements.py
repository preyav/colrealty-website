import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.core.exceptions import ValidationError, PermissionDenied
from django.urls import reverse
from .test_book_accounting import BookAccountingTests
from .models import ChartAccount, FinancialAccount
from .book_models import BillAccounting, BookPosting, BankReconciliation
from .book_reports import account_balance, owner_funds
from .reimbursement_models import ReimbursementPayer, OnBehalfSettlement, BillReimbursement
from .reimbursements import record_on_behalf, reimburse, void_reimbursement
from .book_services import post_bill_payment, void_bill_payment
from maintenance.models import VendorPayment


@override_settings(COL360_FINANCIAL_PROVIDER='col360')
class ReimbursementTests(TestCase):
    setUpTestData = classmethod(BookAccountingTests.setUpTestData.__func__)

    def setUp(self):
        call_command('seed_bill_reimbursements', verbosity=0)
        self.staff.is_superuser = True; self.staff.save()
        self.invoice, self.expense = BookAccountingTests.bill(self)
        self.details = self.invoice.book_details
        self.details.service_start = self.today - timedelta(days=3)
        self.details.service_end = self.today - timedelta(days=3)
        self.details.recognition_date = self.today - timedelta(days=3)
        self.details.save()
        self.liability = ChartAccount.objects.create(code='2700', name='Due to advancing party', account_type='liability')
        self.prepaid = ChartAccount.objects.create(code='1700', name='Prepaid vendor expense', account_type='asset')
        self.payer = ReimbursementPayer.objects.create(name='Advancing company', entity=self.entity, liability_account=self.liability, prepaid_account=self.prepaid)
        self.data = dict(payer=self.payer, amount=Decimal('100'), payment_date=self.today-timedelta(days=6), payment_method='card', reference='receipt-1', notes='',
                         expense_account=self.expense, service_start=self.details.service_start, service_end=self.details.service_end, recognition_date=self.details.recognition_date)

    def balance(self, account, basis='accrual', date=None):
        return account_balance(self.entity, account, date or self.today, self.property.pk, basis)

    def settle(self, token=None):
        return record_on_behalf(self.invoice.pk, self.data, token or uuid.uuid4(), self.staff)

    def repay(self, settlement, amount='100', token=None):
        return reimburse(settlement.pk, dict(amount=Decimal(amount), date=self.today, bank=self.bank, reference='transfer-1', notes=''), token or uuid.uuid4(), self.staff)

    def test_vendor_paid_no_bank_movement_and_prepaid_accrual(self):
        token=uuid.uuid4(); settlement=self.settle(token)
        self.assertEqual(self.settle(token).pk,settlement.pk)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount,100); self.assertEqual(self.invoice.outstanding_amount,200)
        self.assertIsNone(settlement.payment.financial_account_id)
        self.assertEqual(self.balance(self.asset,'cash'),0)
        self.assertEqual(self.balance(self.expense,'cash'),100)
        self.assertEqual(self.balance(self.expense),300)
        self.assertEqual(self.balance(self.prepaid,date=self.data['payment_date']),100)
        self.assertEqual(self.balance(self.config.payable,date=self.data['payment_date']),0)
        self.assertEqual(self.balance(self.prepaid),0)
        self.assertEqual(self.balance(self.config.payable),200)
        self.assertEqual(self.balance(self.liability),100)
        self.assertEqual(owner_funds(self.config)['reimbursements'],100)
        count=BookPosting.objects.count(); post_bill_payment(settlement.payment,self.staff)
        self.assertEqual(BookPosting.objects.count(),count)
        for posting in BookPosting.objects.all():
            self.assertEqual(sum((l.debit-l.credit for l in posting.journal.lines.all()),Decimal('0')),0)

    def test_partial_reimbursements_no_duplicate_expense_and_void(self):
        settlement=self.settle(); token=uuid.uuid4()
        row=self.repay(settlement,'40',token)
        self.assertEqual(self.repay(settlement,'40',token).pk,row.pk)
        self.assertEqual(settlement.outstanding,60)
        self.assertEqual(self.balance(self.liability),60)
        self.assertEqual(self.balance(self.asset,'cash'),-40)
        self.assertEqual(self.balance(self.expense,'cash'),100)
        with self.assertRaises(ValidationError):self.repay(settlement,'61')
        with self.assertRaises(ValidationError):void_bill_payment(settlement.payment,'Correction',self.staff)
        void_reimbursement(row.pk,'Incorrect transfer',self.staff)
        self.assertEqual(settlement.outstanding,100)
        self.assertEqual(self.balance(self.asset,'cash'),0)
        void_bill_payment(settlement.payment,'Wrong source',self.staff)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.paid_amount,0)
        self.assertEqual(self.balance(self.liability),0)
        self.assertEqual(self.balance(self.expense,'cash'),0)

    def test_permissions_payer_scope_and_rollback(self):
        self.staff.is_superuser=False; self.staff.save()
        with self.assertRaises(PermissionDenied):self.settle()
        self.staff.is_superuser=True; self.staff.save()
        self.payer.is_active=False; self.payer.save()
        with self.assertRaises(ValidationError):self.settle()
        self.payer.is_active=True; self.payer.save()
        with patch('accounting.reimbursements.record_event', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):self.settle()
        self.assertEqual(VendorPayment.objects.count(),0); self.assertEqual(BookPosting.objects.count(),0)
        settlement=self.settle()
        self.payer.liability_account=self.config.payable
        with self.assertRaises(ValidationError):self.payer.full_clean()
        payment=settlement.payment; payment.amount=Decimal('10')
        with self.assertRaises(ValidationError):payment.save()

    def test_form_and_expired_cross_invoice_tokens(self):
        self.client.force_login(self.staff)
        url=reverse('portal:record_vendor_payment',args=[self.invoice.pk])+'?funding=on_behalf'
        response=self.client.get(url); self.assertEqual(response.status_code,200)
        form=response.context['form']
        self.assertIn(self.payer,list(form.fields['payer'].queryset))
        data={k:(v.pk if hasattr(v,'pk') else str(v)) for k,v in self.data.items()}
        data['version']='invalid'
        response=self.client.post(url,data)
        self.assertEqual(response.status_code,200); self.assertEqual(VendorPayment.objects.count(),0)
        data['version']=self.client.get(url).context['version']
        response=self.client.post(url,data); self.assertEqual(response.status_code,302)
        settlement=OnBehalfSettlement.objects.get()
        repayment_url=reverse('portal:bill_reimbursement',args=[settlement.pk])
        response=self.client.get(repayment_url); self.assertEqual(response.status_code,200)
        self.assertNotIn('quickbooks_account_id',response.content.decode())

    def test_final_bank_period_blocks_reimbursement_but_not_vendor_advance(self):
        BankReconciliation.objects.create(entity_bank=self.entity_bank,statement_start=self.today-timedelta(days=30),statement_end=self.today,opening_balance=0,closing_balance=0,status='final')
        settlement=self.settle()
        with self.assertRaises(ValidationError):self.repay(settlement)
        self.assertEqual(BillReimbursement.objects.count(),0)

    def test_service_dates_preserved_and_complete_bill_paid(self):
        self.data['amount']=Decimal('300')
        settlement=self.settle(); self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status,'paid'); self.assertEqual(self.invoice.outstanding_amount,0)
        self.repay(settlement,'300')
        self.assertEqual(self.balance(self.liability),0)
        self.assertEqual(self.balance(self.expense,'cash'),300)
        self.details.refresh_from_db(); self.assertEqual(self.details.recognition_date,self.today-timedelta(days=3))

    def test_native_provider_void_cannot_bypass_reimbursements(self):
        from financial.providers.col360 import COL360FinancialProvider
        from financial.providers.base import FinancialProviderError
        provider=COL360FinancialProvider()
        settlement=self.settle(); self.repay(settlement,'20')
        with self.assertRaises(FinancialProviderError):
            provider.void_payment(settlement.payment,actor=self.staff,reason='Correction')
        settlement.payment.refresh_from_db(); self.assertEqual(settlement.payment.status,'recorded')

    def test_same_day_payment_has_no_prepaid_schedule(self):
        self.data['payment_date']=self.details.recognition_date
        settlement=self.settle()
        self.assertFalse(BookPosting.objects.filter(source_key='bill-payment:'+str(settlement.payment_id)+':service').exists())
        self.assertEqual(self.balance(self.prepaid),0)

    def test_new_bill_details_are_explicit_and_roll_back_with_payment(self):
        self.details.delete()
        with patch('accounting.reimbursements.record_event',side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):self.settle()
        self.assertFalse(BillAccounting.objects.filter(invoice=self.invoice).exists())
        self.assertFalse(VendorPayment.objects.exists())
        self.settle()
        details=BillAccounting.objects.get(invoice=self.invoice)
        self.assertEqual(details.service_start,self.data['service_start'])
        self.assertEqual(details.recognition_date,self.data['recognition_date'])

    def test_void_requires_its_own_staff_permission(self):
        from django.contrib.auth.models import Permission
        settlement=self.settle()
        self.staff.is_superuser=False; self.staff.save()
        with self.assertRaises(PermissionDenied):void_bill_payment(settlement.payment,'Correction',self.staff)
        self.staff.user_permissions.add(Permission.objects.get(codename='change_vendorpayment'))
        self.staff=type(self.staff).objects.get(pk=self.staff.pk)
        void_bill_payment(settlement.payment,'Correction',self.staff)
        settlement.payment.refresh_from_db(); self.assertEqual(settlement.payment.status,'void')

    def test_cross_entity_payer_and_reimbursement_bank_rejected(self):
        from .book_models import AccountingEntity
        other=AccountingEntity.objects.create(name='Other entity')
        self.payer.entity=other; self.payer.save()
        with self.assertRaises(ValidationError):self.settle()
        self.payer.entity=self.entity; self.payer.save()
        settlement=self.settle()
        bank=FinancialAccount.objects.create(name='Unconfigured bank',ledger_account=self.prepaid)
        with self.assertRaises(ValidationError):
            reimburse(settlement.pk,dict(amount=Decimal('100'),date=self.today,bank=bank,reference='x'),uuid.uuid4(),self.staff)

    def test_native_payment_view_does_not_require_quickbooks(self):
        import ast
        from pathlib import Path
        from unittest.mock import Mock
        from django.test import RequestFactory
        from django.db.models import Sum
        from django.utils import timezone
        from financial.providers.col360 import COL360FinancialProvider
        source=Path(__file__).parents[1]/'portal'/'views.py'
        node=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='record_vendor_payment')
        node.decorator_list=[]
        connection=Mock(); connection.objects.filter.side_effect=AssertionError('Native payments must not query an external connection')
        mapping=Mock(); mapping.objects.filter.return_value.first.return_value=None
        renderer=Mock(return_value='rendered')
        namespace={'get_financial_provider':lambda:COL360FinancialProvider(),'QuickBooksConnection':connection,
                   'QuickBooksBillMapping':mapping,'timezone':timezone,'Sum':Sum,'render':renderer,
                   'reimbursement_wording':lambda:{},'FinancialProviderError':Exception,'FinancialProviderDisabled':Exception}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),namespace)
        request=RequestFactory().get('/payment/'); request.user=self.staff
        self.assertEqual(namespace['record_vendor_payment'](request,self.invoice.pk),'rendered')
        self.assertIsNone(renderer.call_args.args[2]['quickbooks_connection'])
        self.assertTrue(renderer.call_args.args[2]['native_provider'])
