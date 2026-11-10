from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone
from accounting.test_general_ledger import GeneralLedgerTests
from accounting.models import ChartAccount
from accounting.book_models import BillAccounting
from common.models import FormFieldSetting
from maintenance.models import WorkOrder, VendorInvoice
from vendors.models import Vendor
from financial.providers.col360 import COL360FinancialProvider
from financial.providers.base import FinancialProviderError
from portal.invoice_accounting import NativeVendorInvoiceForm


class InvoiceAccountingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        GeneralLedgerTests.setUpTestData.__func__(cls)
        call_command('seed_invoice_accounting_fields', verbosity=0)
        cls.vendor = Vendor.objects.create(name='Invoice test vendor')
        cls.expense = ChartAccount.objects.create(code='5991', name='Invoice test expense', account_type='expense')
        cls.work = WorkOrder.objects.create(unit=cls.unit, title='Invoice test work', description='Test work', status='completed', actual_cost='150')

    def form(self, instance=None, **changes):
        today = timezone.localdate()
        data = {'vendor': self.vendor.pk, 'invoice_number': 'TEST-ACCOUNTING', 'amount': '150', 'invoice_date': today, 'due_date': today + timedelta(days=30), 'service_start': today, 'service_end': today, 'recognition_date': today, 'expense_account': self.expense.pk, 'notes': ''}
        data.update(changes)
        return NativeVendorInvoiceForm(data, instance=instance)

    def create(self):
        form = self.form()
        self.assertTrue(form.is_valid(), form.errors)
        return COL360FinancialProvider().create_invoice(form, work_order=self.work)

    def test_invoice_and_metadata_created_and_reloaded(self):
        invoice = self.create()
        self.assertEqual(invoice.book_details.expense_account, self.expense)
        form = NativeVendorInvoiceForm(instance=invoice)
        self.assertEqual(form.initial['service_start'], timezone.localdate())
        self.assertEqual(form.initial['expense_account'], self.expense.pk)

    def test_missing_metadata_and_reversed_period_rejected(self):
        for name in ['service_start', 'service_end', 'recognition_date', 'expense_account']:
            self.assertIn(name, self.form(**{name: ''}).errors)
        self.assertIn('service_end', self.form(service_end=timezone.localdate()-timedelta(days=1)).errors)

    def test_nonexpense_and_inactive_account_rejected(self):
        self.assertIn('expense_account', self.form(expense_account=self.income.pk).errors)
        ChartAccount.objects.filter(pk=self.expense.pk).update(is_active=False)
        self.assertIn('expense_account', self.form().errors)

    def test_metadata_failure_rolls_back_invoice(self):
        form = self.form()
        self.assertTrue(form.is_valid(), form.errors)
        with patch.object(NativeVendorInvoiceForm, 'save_accounting', side_effect=ValidationError('Metadata failed')):
            with self.assertRaises(FinancialProviderError):
                COL360FinancialProvider().create_invoice(form, work_order=self.work)
        self.assertFalse(VendorInvoice.objects.filter(invoice_number='TEST-ACCOUNTING').exists())

    def test_update_changes_existing_metadata_without_duplicate(self):
        invoice = self.create()
        form = self.form(instance=invoice, service_start=timezone.localdate()-timedelta(days=2))
        self.assertTrue(form.is_valid(), form.errors)
        COL360FinancialProvider().update_invoice(form, invoice=invoice)
        self.assertEqual(BillAccounting.objects.filter(invoice=invoice).count(), 1)
        self.assertEqual(BillAccounting.objects.get(invoice=invoice).service_start, timezone.localdate()-timedelta(days=2))

    def test_posting_appears_after_validation_save_rejected(self):
        invoice = self.create()
        form = self.form(instance=invoice, amount='175')
        self.assertTrue(form.is_valid(), form.errors)
        with patch('financial.providers.col360.BookPosting.objects.filter') as query:
            query.return_value.exists.return_value = True
            with self.assertRaises(FinancialProviderError):
                COL360FinancialProvider().update_invoice(form, invoice=invoice)
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount, 150)

    def test_approval_requires_metadata_and_locks_edit(self):
        invoice = self.create()
        provider = COL360FinancialProvider()
        invoice, result = provider.approve_invoice(invoice, actor=self.staff)
        self.assertEqual(result, 'approved')
        self.assertFalse(self.form(instance=invoice).is_valid())
        other_work = WorkOrder.objects.create(
            unit=self.unit,
            title='Legacy invoice test work',
            description='Test work',
            status='completed',
            actual_cost='10',
        )
        other = VendorInvoice.objects.create(
            work_order=other_work,
            vendor=self.vendor,
            invoice_number='LEGACY',
            amount='10',
            status='submitted',
        )
        with self.assertRaises(FinancialProviderError):
            provider.approve_invoice(other, actor=self.staff)

    def test_custom_labels_preserved_on_reseed(self):
        row = FormFieldSetting.objects.get(form_key='vendor_invoice_accounting', field_key='service_start')
        row.label = 'Custom start label'
        row.save()
        call_command('seed_invoice_accounting_fields', verbosity=0)
        self.assertEqual(NativeVendorInvoiceForm().fields['service_start'].label, 'Custom start label')
