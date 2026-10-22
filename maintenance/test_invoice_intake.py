from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from financial.services import get_financial_provider
from maintenance.models import VendorAssignment, VendorInvoice, VendorPayment, WorkOrder
from portal.forms import VendorInvoiceForm, VendorPaymentForm
from properties.models import Property, PropertyUnit
from vendors.models import Vendor
from accounting.models import (
    ChartAccount,
    FinancialAccount,
    QuickBooksBillMapping,
    QuickBooksConnection,
    QuickBooksPaymentMapping,
    QuickBooksVendorMapping,
)
from accounting.quickbooks import delete_bill_payment, sync_bill, sync_bill_payment


@override_settings(COL360_FINANCIAL_PROVIDER="col360")
class VendorInvoiceIntakeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="invoice_manager",
            password="test-password",
            is_staff=True,
        )
        property_record = Property.objects.create(
            street_address="900 Invoice Lane",
            city="Austin",
            state="TX",
            zip_code="78701",
            county="Travis",
            subdivision="Test",
            property_type="single_family_residential",
            management_status="active",
            is_multi_unit=False,
        )
        unit = PropertyUnit.objects.create(property=property_record, unit_number="")
        self.completed_at = timezone.now() - timedelta(days=1)
        self.work_order = WorkOrder.objects.create(
            unit=unit,
            title="Repair air conditioner",
            description="Restore cooling.",
            status="completed",
            completed_at=self.completed_at,
            actual_cost=Decimal("750.00"),
        )
        self.vendor = Vendor.objects.create(
            name="Alex Vendor",
            company_name="Austin Repair Company",
            email="invoice@example.com",
            status="active",
        )
        VendorAssignment.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            status="completed",
            completed_at=self.completed_at,
        )
        self.cash_ledger = ChartAccount.objects.create(
            code="1010",
            name="Test Operating Cash",
            account_type="asset",
        )
        self.financial_account = FinancialAccount.objects.create(
            name="Test Operating Account",
            kind="bank",
            ledger_account=self.cash_ledger,
            account_last_four="1000",
        )
        self.client.force_login(self.user)

    def test_invoice_screen_prefills_known_work_order_values(self):
        response = self.client.get(
            reverse("portal:add_vendor_invoice", args=[self.work_order.pk])
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        invoice_date = timezone.localtime(self.completed_at).date()
        self.assertEqual(form.initial["vendor"], self.vendor)
        self.assertEqual(form.initial["amount"], Decimal("750.00"))
        self.assertEqual(form.initial["invoice_date"], invoice_date)
        self.assertEqual(form.initial["due_date"], invoice_date + timedelta(days=30))
        self.assertIn("Thank you", form.initial["notes"])
        self.assertFalse(form.initial.get("invoice_number"))

    def test_invoice_form_rejects_nonpositive_amount_and_invalid_dates(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        form = VendorInvoiceForm(
            data={
                "vendor": self.vendor.pk,
                "invoice_number": "INV-100",
                "amount": "0.00",
                "invoice_date": tomorrow.isoformat(),
                "due_date": timezone.localdate().isoformat(),
                "notes": "Thank you.",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("amount", form.errors)
        self.assertIn("invoice_date", form.errors)

    def test_incomplete_work_order_cannot_accept_invoice(self):
        self.work_order.status = "in_progress"
        self.work_order.save(update_fields=["status"])

        response = self.client.get(
            reverse("portal:add_vendor_invoice", args=[self.work_order.pk])
        )

        self.assertRedirects(
            response,
            reverse("portal:finance_vendor_invoices"),
        )

    def create_invoice(self, **overrides):
        values = {
            "work_order": self.work_order,
            "vendor": self.vendor,
            "invoice_number": "INV-001",
            "amount": Decimal("750.00"),
            "status": "submitted",
            "invoice_date": timezone.localdate(),
            "due_date": timezone.localdate() + timedelta(days=30),
            "notes": "Original invoice.",
        }
        values.update(overrides)
        return VendorInvoice.objects.create(**values)

    def test_existing_submitted_invoice_redirects_add_to_edit(self):
        invoice = self.create_invoice()

        response = self.client.get(
            reverse("portal:add_vendor_invoice", args=[self.work_order.pk])
        )

        self.assertRedirects(
            response,
            reverse("portal:edit_vendor_invoice", args=[invoice.pk]),
        )

    def test_edit_updates_existing_invoice_without_creating_another(self):
        invoice = self.create_invoice()

        response = self.client.post(
            reverse("portal:edit_vendor_invoice", args=[invoice.pk]),
            {
                "vendor": self.vendor.pk,
                "invoice_number": "INV-001-REVISED",
                "amount": "725.00",
                "invoice_date": timezone.localdate().isoformat(),
                "due_date": (timezone.localdate() + timedelta(days=30)).isoformat(),
                "notes": "Corrected amount.",
            },
        )

        self.assertRedirects(
            response,
            reverse("portal:finance_vendor_invoice_detail", args=[invoice.pk]),
        )
        self.assertEqual(VendorInvoice.objects.count(), 1)
        invoice.refresh_from_db()
        self.assertEqual(invoice.invoice_number, "INV-001-REVISED")
        self.assertEqual(invoice.amount, Decimal("725.00"))

    def test_approved_invoice_cannot_be_edited(self):
        invoice = self.create_invoice(status="approved")

        response = self.client.get(
            reverse("portal:edit_vendor_invoice", args=[invoice.pk])
        )

        self.assertRedirects(
            response,
            reverse("portal:finance_vendor_invoice_detail", args=[invoice.pk]),
        )

    def test_database_rejects_second_current_invoice(self):
        self.create_invoice()

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_invoice(invoice_number="INV-002")

    def payment_data(self, **overrides):
        values = {
            "amount": "750.00",
            "payment_date": timezone.localdate().isoformat(),
            "payment_method": "ach",
            "reference_number": "ACH-1001",
            "financial_account": self.financial_account.pk,
            "notes": "Vendor payment.",
        }
        values.update(overrides)
        return values

    def test_partial_then_final_payment_updates_invoice_status_and_totals(self):
        invoice = self.create_invoice(status="approved")

        response = self.client.post(
            reverse("portal:record_vendor_payment", args=[invoice.pk]),
            self.payment_data(amount="300.00"),
        )
        self.assertRedirects(
            response, reverse("portal:finance_vendor_invoice_detail", args=[invoice.pk])
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "partially_paid")
        self.assertEqual(invoice.paid_amount, Decimal("300.00"))
        self.assertEqual(invoice.outstanding_amount, Decimal("450.00"))

        response = self.client.post(
            reverse("portal:record_vendor_payment", args=[invoice.pk]),
            self.payment_data(amount="450.00", reference_number="ACH-1002"),
        )
        self.assertRedirects(
            response, reverse("portal:finance_vendor_invoice_detail", args=[invoice.pk])
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")
        self.assertIsNotNone(invoice.paid_at)
        self.assertEqual(invoice.paid_amount, Decimal("750.00"))

    def test_payment_form_rejects_overpayment_and_future_date(self):
        invoice = self.create_invoice(status="approved")
        form = VendorPaymentForm(
            self.payment_data(
                amount="751.00",
                payment_date=(timezone.localdate() + timedelta(days=1)).isoformat(),
            ),
            invoice=invoice,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("amount", form.errors)
        self.assertIn("payment_date", form.errors)

    def test_submitted_invoice_cannot_accept_payment(self):
        invoice = self.create_invoice(status="submitted")
        response = self.client.get(
            reverse("portal:record_vendor_payment", args=[invoice.pk])
        )
        self.assertRedirects(
            response, reverse("portal:finance_vendor_invoice_detail", args=[invoice.pk])
        )
        self.assertFalse(VendorPayment.objects.exists())

    def test_void_payment_restores_invoice_balance_and_preserves_record(self):
        invoice = self.create_invoice(status="approved")
        self.client.post(
            reverse("portal:record_vendor_payment", args=[invoice.pk]),
            self.payment_data(),
        )
        payment = VendorPayment.objects.get()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")

        response = self.client.post(
            reverse("portal:void_vendor_payment", args=[payment.pk]),
            {"reason": "Payment was entered against the wrong bank transaction."},
        )
        self.assertRedirects(
            response, reverse("portal:finance_vendor_invoice_detail", args=[invoice.pk])
        )
        payment.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(payment.status, "void")
        self.assertEqual(invoice.status, "approved")
        self.assertEqual(invoice.paid_amount, Decimal("0.00"))
        self.assertIsNone(invoice.paid_at)

    def test_void_requires_reason(self):
        invoice = self.create_invoice(status="approved")
        payment = VendorPayment.objects.create(
            invoice=invoice,
            amount=Decimal("100.00"),
            payment_date=timezone.localdate(),
            payment_method="check",
            status="recorded",
        )
        response = self.client.post(
            reverse("portal:void_vendor_payment", args=[payment.pk]), {"reason": ""}
        )
        self.assertEqual(response.status_code, 302)
        payment.refresh_from_db()
        self.assertEqual(payment.status, "recorded")

    def test_financial_provider_cache_respects_setting_changes(self):
        with override_settings(COL360_FINANCIAL_PROVIDER="disabled"):
            self.assertEqual(get_financial_provider().key, "disabled")
        with override_settings(COL360_FINANCIAL_PROVIDER="col360"):
            self.assertEqual(get_financial_provider().key, "col360")

    def test_finance_workspace_owns_invoice_and_payment_actions(self):
        invoice = self.create_invoice(status="approved")
        finance_response = self.client.get(reverse("portal:finance_dashboard"))
        bills_response = self.client.get(reverse("portal:finance_vendor_invoices"))
        detail_response = self.client.get(
            reverse("portal:finance_vendor_invoice_detail", args=[invoice.pk])
        )
        work_order_response = self.client.get(
            reverse("portal:work_order_detail", args=[self.work_order.pk])
        )

        self.assertEqual(finance_response.status_code, 200)
        self.assertEqual(bills_response.status_code, 200)
        self.assertContains(detail_response, "Record Payment")
        self.assertContains(work_order_response, "View in Finance")
        self.assertNotContains(work_order_response, "Record Payment")

    def test_payment_screen_does_not_prefill_full_balance(self):
        invoice = self.create_invoice(status="approved")
        response = self.client.get(
            reverse("portal:record_vendor_payment", args=[invoice.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["form"].initial.get("amount"))

    def test_payment_form_uses_active_configured_financial_accounts(self):
        invoice = self.create_invoice(status="approved")
        inactive_ledger = ChartAccount.objects.create(
            code="1020", name="Inactive Cash", account_type="asset"
        )
        inactive = FinancialAccount.objects.create(
            name="Inactive Bank", kind="bank", ledger_account=inactive_ledger,
            is_active=False,
        )
        response = self.client.get(
            reverse("portal:record_vendor_payment", args=[invoice.pk])
        )
        queryset = response.context["form"].fields["financial_account"].queryset
        self.assertIn(self.financial_account, queryset)
        self.assertNotIn(inactive, queryset)

    def quickbooks_connection(self):
        return QuickBooksConnection.objects.create(
            realm_id="123456789",
            company_name="COL360 Sandbox",
            environment="sandbox",
            access_token_encrypted="encrypted-access",
            refresh_token_encrypted="encrypted-refresh",
            access_token_expires_at=timezone.now() + timedelta(hours=1),
            connected_by=self.user,
        )

    def test_approved_invoice_displays_quickbooks_sync_action(self):
        self.quickbooks_connection()
        invoice = self.create_invoice(status="approved")
        response = self.client.get(
            reverse("portal:finance_vendor_invoice_detail", args=[invoice.pk])
        )
        self.assertContains(response, "Sync to QuickBooks")
        self.assertContains(response, "Not Synchronized")

    def test_submitted_invoice_cannot_open_quickbooks_sync(self):
        self.quickbooks_connection()
        invoice = self.create_invoice(status="submitted")
        response = self.client.get(
            reverse("portal:finance_vendor_invoice_quickbooks_sync", args=[invoice.pk])
        )
        self.assertRedirects(
            response, reverse("portal:finance_vendor_invoice_detail", args=[invoice.pk])
        )

    @patch("portal.views.list_expense_accounts")
    def test_quickbooks_sync_screen_lists_expense_accounts(self, accounts):
        self.quickbooks_connection()
        invoice = self.create_invoice(status="approved")
        accounts.return_value = [{
            "Id": "88",
            "Name": "Repairs and Maintenance",
            "FullyQualifiedName": "Repairs and Maintenance",
            "AccountType": "Expense",
            "Active": True,
        }]
        response = self.client.get(
            reverse("portal:finance_vendor_invoice_quickbooks_sync", args=[invoice.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Repairs and Maintenance")

    @patch("portal.views.sync_bill")
    @patch("portal.views.list_expense_accounts")
    def test_staff_can_sync_approved_invoice_from_finance(self, accounts, synchronize):
        self.quickbooks_connection()
        invoice = self.create_invoice(status="approved")
        accounts.return_value = [{
            "Id": "88", "Name": "Repairs and Maintenance", "AccountType": "Expense"
        }]
        synchronize.return_value = SimpleNamespace(
            quickbooks_bill_id="501",
            document_number="INV-001",
            expense_account_name="Repairs and Maintenance",
        )
        response = self.client.post(
            reverse("portal:finance_vendor_invoice_quickbooks_sync", args=[invoice.pk]),
            {"expense_account_id": "88"},
        )
        self.assertRedirects(
            response, reverse("portal:finance_vendor_invoice_detail", args=[invoice.pk])
        )
        synchronize.assert_called_once()
        self.assertEqual(synchronize.call_args.args[2], "88")

    @patch("accounting.quickbooks.quickbooks_request")
    def test_bill_sync_creates_one_quickbooks_bill_and_mapping(self, request):
        connection = self.quickbooks_connection()
        invoice = self.create_invoice(status="approved")
        QuickBooksVendorMapping.objects.create(
            connection=connection,
            vendor=self.vendor,
            quickbooks_vendor_id="42",
            display_name="Austin Repair Company",
        )
        request.side_effect = [
            {"Account": {"Id": "88", "Name": "Repairs and Maintenance", "AccountType": "Expense", "Active": True}},
            {"Vendor": {"Id": "42", "SyncToken": "1", "DisplayName": "Austin Repair Company"}},
            {"QueryResponse": {}},
            {"Bill": {"Id": "501", "SyncToken": "0", "DocNumber": "INV-001"}},
        ]
        mapping = sync_bill(connection, invoice, "88")
        self.assertEqual(mapping.quickbooks_bill_id, "501")
        self.assertEqual(mapping.expense_account_id, "88")
        self.assertEqual(QuickBooksBillMapping.objects.count(), 1)
        self.assertEqual(request.call_args_list[-1].args[1], "POST")

    @patch("accounting.quickbooks.quickbooks_request")
    def test_repeated_bill_sync_only_verifies_existing_bill(self, request):
        connection = self.quickbooks_connection()
        invoice = self.create_invoice(status="approved")
        QuickBooksBillMapping.objects.create(
            connection=connection,
            invoice=invoice,
            quickbooks_bill_id="501",
            document_number="INV-001",
            expense_account_id="88",
            expense_account_name="Repairs and Maintenance",
        )
        request.return_value = {"Bill": {"Id": "501", "SyncToken": "1"}}
        mapping = sync_bill(connection, invoice, "88")
        self.assertEqual(mapping.quickbooks_bill_id, "501")
        self.assertEqual(QuickBooksBillMapping.objects.count(), 1)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[1], "GET")

    @patch("accounting.quickbooks.quickbooks_request")
    def test_existing_remote_bill_is_linked_instead_of_duplicated(self, request):
        connection = self.quickbooks_connection()
        invoice = self.create_invoice(status="approved")
        QuickBooksVendorMapping.objects.create(
            connection=connection,
            vendor=self.vendor,
            quickbooks_vendor_id="42",
            display_name="Austin Repair Company",
        )
        request.side_effect = [
            {"Account": {"Id": "88", "Name": "Repairs and Maintenance", "AccountType": "Expense", "Active": True}},
            {"Vendor": {"Id": "42", "SyncToken": "1", "DisplayName": "Austin Repair Company"}},
            {"QueryResponse": {"Bill": [{
                "Id": "777", "SyncToken": "2", "DocNumber": "INV-001",
                "VendorRef": {"value": "42"},
            }]}},
        ]
        mapping = sync_bill(connection, invoice, "88")
        self.assertEqual(mapping.quickbooks_bill_id, "777")
        self.assertEqual(request.call_count, 3)
        self.assertNotIn("POST", [call.args[1] for call in request.call_args_list])

    @patch("accounting.quickbooks.quickbooks_request")
    def test_payment_sync_creates_one_linked_quickbooks_bill_payment(self, request):
        connection = self.quickbooks_connection()
        invoice = self.create_invoice(status="partially_paid")
        bill_mapping = QuickBooksBillMapping.objects.create(
            connection=connection,
            invoice=invoice,
            quickbooks_bill_id="501",
            document_number="INV-001",
            expense_account_id="88",
            expense_account_name="Repairs and Maintenance",
        )
        QuickBooksVendorMapping.objects.create(
            connection=connection,
            vendor=self.vendor,
            quickbooks_vendor_id="42",
            display_name="Austin Repair Company",
        )
        payment = VendorPayment.objects.create(
            invoice=invoice,
            amount=Decimal("300.00"),
            payment_date=timezone.localdate(),
            payment_method="ach",
            reference_number="ACH-1001",
            financial_account=self.financial_account,
            recorded_by=self.user,
        )
        request.side_effect = [
            {"Account": {"Id": "10", "Name": "Checking", "AccountType": "Bank", "Active": True}},
            {"Vendor": {"Id": "42", "SyncToken": "1", "DisplayName": "Austin Repair Company"}},
            {"QueryResponse": {}},
            {"BillPayment": {"Id": "601", "SyncToken": "0"}},
        ]
        mapping = sync_bill_payment(connection, payment, "10")
        self.assertEqual(mapping.quickbooks_payment_id, "601")
        self.assertEqual(mapping.status, "synced")
        payload = request.call_args_list[-1].kwargs["json"]
        self.assertEqual(payload["Line"][0]["LinkedTxn"][0]["TxnId"], bill_mapping.quickbooks_bill_id)
        self.assertEqual(payload["CheckPayment"]["BankAccountRef"]["value"], "10")

    @patch("accounting.quickbooks.quickbooks_request")
    def test_repeated_payment_sync_verifies_without_duplicate(self, request):
        connection = self.quickbooks_connection()
        invoice = self.create_invoice(status="paid")
        bill_mapping = QuickBooksBillMapping.objects.create(
            connection=connection,
            invoice=invoice,
            quickbooks_bill_id="501",
            document_number="INV-001",
            expense_account_id="88",
            expense_account_name="Repairs and Maintenance",
        )
        payment = VendorPayment.objects.create(
            invoice=invoice,
            amount=Decimal("750.00"),
            payment_date=timezone.localdate(),
            payment_method="ach",
            reference_number="ACH-1001",
            financial_account=self.financial_account,
        )
        QuickBooksPaymentMapping.objects.create(
            connection=connection,
            payment=payment,
            bill_mapping=bill_mapping,
            quickbooks_payment_id="601",
            sync_token="0",
            document_number=f"COL360-PAY-{payment.pk}",
            payment_account_id="10",
            payment_account_name="Checking",
            payment_account_type="Bank",
            status="synced",
        )
        request.side_effect = [
            {"Account": {"Id": "10", "Name": "Checking", "AccountType": "Bank", "Active": True}},
            {"BillPayment": {"Id": "601", "SyncToken": "1"}},
        ]
        mapping = sync_bill_payment(connection, payment, "10")
        self.assertEqual(mapping.quickbooks_payment_id, "601")
        self.assertNotIn("POST", [call.args[1] for call in request.call_args_list])

    @patch("accounting.quickbooks.quickbooks_request")
    def test_quickbooks_payment_is_deleted_before_local_void(self, request):
        connection = self.quickbooks_connection()
        invoice = self.create_invoice(status="paid")
        bill_mapping = QuickBooksBillMapping.objects.create(
            connection=connection,
            invoice=invoice,
            quickbooks_bill_id="501",
            document_number="INV-001",
            expense_account_id="88",
            expense_account_name="Repairs and Maintenance",
        )
        payment = VendorPayment.objects.create(
            invoice=invoice,
            amount=Decimal("750.00"),
            payment_date=timezone.localdate(),
            payment_method="ach",
            financial_account=self.financial_account,
        )
        mapping = QuickBooksPaymentMapping.objects.create(
            connection=connection,
            payment=payment,
            bill_mapping=bill_mapping,
            quickbooks_payment_id="601",
            sync_token="0",
            document_number=f"COL360-PAY-{payment.pk}",
            payment_account_id="10",
            payment_account_name="Checking",
            payment_account_type="Bank",
            status="synced",
        )
        request.side_effect = [
            {"BillPayment": {"Id": "601", "SyncToken": "2"}},
            {"BillPayment": {"Id": "601", "SyncToken": "2", "status": "Deleted"}},
        ]
        delete_bill_payment(connection, payment)
        mapping.refresh_from_db()
        self.assertEqual(mapping.status, "deleted")
        delete_call = request.call_args_list[-1]
        self.assertEqual(delete_call.args[1], "POST")
        self.assertEqual(
            delete_call.args[2],
            f"/v3/company/{connection.realm_id}/billpayment",
        )
        self.assertEqual(delete_call.kwargs["params"]["operation"], "delete")
        self.assertEqual(
            delete_call.kwargs["json"],
            {"Id": "601", "SyncToken": "2"},
        )
