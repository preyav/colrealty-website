from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from .forms import FinancialAccountForm
from vendors.models import Vendor

from .models import (
    ChartAccount,
    FinancialAccount,
    QuickBooksConnection,
    QuickBooksVendorMapping,
)
from .quickbooks import (
    decrypt_token,
    encrypt_token,
    list_expense_accounts,
    list_payment_accounts,
    refresh_connection,
    sync_vendor,
)


QB_SETTINGS = {
    "QUICKBOOKS_CLIENT_ID": "test-client",
    "QUICKBOOKS_CLIENT_SECRET": "test-secret",
    "QUICKBOOKS_REDIRECT_URI": "http://localhost:8000/portal/finance/quickbooks/callback/",
    "QUICKBOOKS_ENVIRONMENT": "sandbox",
}


class AccountingFoundationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="finance_manager", password="test-password", is_staff=True
        )
        self.asset = ChartAccount.objects.create(
            code="1010", name="Operating Cash", account_type="asset"
        )
        self.liability = ChartAccount.objects.create(
            code="2010", name="Credit Card Payable", account_type="liability"
        )
        self.client.force_login(self.user)

    def test_accounts_workspace_is_staff_accessible(self):
        response = self.client.get(reverse("portal:finance_accounts"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chart of Accounts")

    def test_staff_can_create_chart_account_with_audit_snapshot(self):
        response = self.client.post(reverse("portal:finance_chart_account_add"), {
            "code": "1020",
            "name": "Maintenance Reserve",
            "account_type": "asset",
            "description": "Funds reserved for property maintenance.",
            "is_active": True,
        })
        self.assertRedirects(response, reverse("portal:finance_accounts"))
        self.assertTrue(ChartAccount.objects.filter(code="1020").exists())

    def test_staff_can_create_financial_account_with_audit_snapshot(self):
        response = self.client.post(reverse("portal:finance_financial_account_add"), {
            "name": "Operating Bank",
            "kind": "bank",
            "ledger_account": self.asset.pk,
            "institution_name": "Test Bank",
            "account_last_four": "1234",
            "opening_balance": "1000.00",
            "opening_balance_date": "2026-09-28",
            "notes": "Primary operating account.",
            "is_active": True,
        })
        self.assertRedirects(response, reverse("portal:finance_accounts"))
        self.assertTrue(FinancialAccount.objects.filter(name="Operating Bank").exists())

    def test_bank_account_requires_asset_ledger(self):
        form = FinancialAccountForm(data={
            "name": "Operating Bank",
            "kind": "bank",
            "ledger_account": self.liability.pk,
            "opening_balance": "0.00",
            "is_active": True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("ledger_account", form.errors)

    def test_credit_card_requires_liability_ledger(self):
        account = FinancialAccount(
            name="Company Card", kind="credit_card", ledger_account=self.asset
        )
        with self.assertRaises(ValidationError):
            account.full_clean()

    def test_financial_account_can_be_deactivated_without_deletion(self):
        account = FinancialAccount.objects.create(
            name="Operating Bank", kind="bank", ledger_account=self.asset
        )
        account.is_active = False
        account.save(update_fields=["is_active"])
        self.assertFalse(FinancialAccount.objects.get(pk=account.pk).is_active)


@override_settings(**QB_SETTINGS)
class QuickBooksConnectionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="qb_admin", password="test-password", is_staff=True
        )
        self.client.force_login(self.user)

    def test_connection_page_is_staff_only_and_configured(self):
        response = self.client.get(reverse("portal:finance_quickbooks"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Connect to QuickBooks")

    def test_connect_creates_state_and_redirects_to_intuit(self):
        response = self.client.post(reverse("portal:finance_quickbooks_connect"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("https://appcenter.intuit.com/connect/oauth2?"))
        self.assertTrue(self.client.session.get("quickbooks_oauth_state"))

    @patch("portal.views.company_info")
    @patch("portal.views.exchange_authorization_code")
    def test_callback_saves_encrypted_connection(self, exchange, company):
        exchange.return_value = {
            "access_token": "access-secret",
            "refresh_token": "refresh-secret",
            "expires_in": 3600,
            "x_refresh_token_expires_in": 8726400,
        }
        company.return_value = {"CompanyName": "COL360 Sandbox"}
        session = self.client.session
        session["quickbooks_oauth_state"] = "safe-state"
        session.save()
        response = self.client.get(reverse("portal:finance_quickbooks_callback"), {
            "state": "safe-state", "code": "code", "realmId": "123456789"
        })
        self.assertRedirects(response, reverse("portal:finance_quickbooks"))
        connection = QuickBooksConnection.objects.get(realm_id="123456789")
        self.assertNotIn("access-secret", connection.access_token_encrypted)
        self.assertNotIn("refresh-secret", connection.refresh_token_encrypted)
        self.assertEqual(connection.company_name, "COL360 Sandbox")

    def test_callback_rejects_invalid_state(self):
        session = self.client.session
        session["quickbooks_oauth_state"] = "expected"
        session.save()
        response = self.client.get(reverse("portal:finance_quickbooks_callback"), {
            "state": "wrong", "code": "code", "realmId": "123"
        })
        self.assertRedirects(response, reverse("portal:finance_quickbooks"))
        self.assertFalse(QuickBooksConnection.objects.exists())

    @patch("portal.views.revoke_token")
    def test_disconnect_revokes_and_clears_local_tokens(self, revoke):
        connection = QuickBooksConnection.objects.create(
            realm_id="123",
            company_name="COL360 Sandbox",
            environment="sandbox",
            access_token_encrypted="encrypted-access",
            refresh_token_encrypted="encrypted-refresh",
            access_token_expires_at=timezone.now(),
            connected_by=self.user,
        )
        with patch("portal.views.decrypt_token", return_value="refresh-secret"):
            response = self.client.post(reverse("portal:finance_quickbooks_disconnect"))
        self.assertRedirects(response, reverse("portal:finance_quickbooks"))
        connection.refresh_from_db()
        self.assertFalse(connection.is_active)
        self.assertEqual(connection.access_token_encrypted, "")
        self.assertEqual(connection.refresh_token_encrypted, "")
        revoke.assert_called_once_with("refresh-secret")

    def _connection(self, *, expired=False):
        return QuickBooksConnection.objects.create(
            realm_id="123456789",
            company_name="COL360 Sandbox",
            environment="sandbox",
            access_token_encrypted=encrypt_token("old-access"),
            refresh_token_encrypted=encrypt_token("old-refresh"),
            access_token_expires_at=timezone.now() + (
                timedelta(minutes=-1) if expired else timedelta(hours=1)
            ),
            connected_by=self.user,
        )

    @patch("accounting.quickbooks.refresh_access_token")
    def test_expired_access_token_is_refreshed_and_rotated(self, refresh):
        connection = self._connection(expired=True)
        refresh.return_value = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
            "x_refresh_token_expires_in": 8726400,
        }
        refreshed = refresh_connection(connection)
        self.assertEqual(decrypt_token(refreshed.access_token_encrypted), "new-access")
        self.assertEqual(decrypt_token(refreshed.refresh_token_encrypted), "new-refresh")
        refresh.assert_called_once_with("old-refresh")

    @patch("portal.views.test_connection")
    def test_staff_can_run_connection_health_check(self, health_check):
        self._connection()
        health_check.return_value = {"CompanyName": "COL360 Sandbox"}
        response = self.client.post(reverse("portal:finance_quickbooks_test"))
        self.assertRedirects(response, reverse("portal:finance_quickbooks"))
        health_check.assert_called_once()

    @patch("accounting.quickbooks.quickbooks_request")
    def test_vendor_sync_creates_one_remote_vendor_and_mapping(self, request):
        connection = self._connection()
        vendor = Vendor.objects.create(
            name="Pat Smith",
            company_name="Reliable Plumbing",
            email="vendor@example.com",
            phone="555-0100",
            status="active",
        )
        request.side_effect = [
            {"QueryResponse": {}},
            {"Vendor": {"Id": "42", "SyncToken": "0", "DisplayName": "Reliable Plumbing"}},
        ]
        mapping = sync_vendor(connection, vendor)
        self.assertEqual(mapping.quickbooks_vendor_id, "42")
        self.assertEqual(QuickBooksVendorMapping.objects.count(), 1)
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args_list[1].args[1], "POST")

    @patch("accounting.quickbooks.quickbooks_request")
    def test_repeated_vendor_sync_verifies_existing_mapping_without_duplicate(self, request):
        connection = self._connection()
        vendor = Vendor.objects.create(name="Pat Smith", company_name="Reliable Plumbing")
        QuickBooksVendorMapping.objects.create(
            connection=connection,
            vendor=vendor,
            quickbooks_vendor_id="42",
            display_name="Reliable Plumbing",
        )
        request.return_value = {
            "Vendor": {"Id": "42", "SyncToken": "1", "DisplayName": "Reliable Plumbing"}
        }
        sync_vendor(connection, vendor)
        self.assertEqual(QuickBooksVendorMapping.objects.count(), 1)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[1], "GET")

    @patch("accounting.quickbooks.quickbooks_request")
    def test_existing_quickbooks_vendor_is_linked_instead_of_created(self, request):
        connection = self._connection()
        vendor = Vendor.objects.create(name="Pat Smith", company_name="Reliable Plumbing")
        request.return_value = {
            "QueryResponse": {
                "Vendor": [{"Id": "84", "SyncToken": "2", "DisplayName": "Reliable Plumbing"}]
            }
        }
        mapping = sync_vendor(connection, vendor)
        self.assertEqual(mapping.quickbooks_vendor_id, "84")
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.args[1], "GET")

    @patch("accounting.quickbooks.quickbooks_request")
    def test_expense_account_list_excludes_nonexpense_and_inactive_accounts(self, request):
        connection = self._connection()
        request.return_value = {"QueryResponse": {"Account": [
            {"Id": "1", "Name": "Repairs", "AccountType": "Expense", "Active": True},
            {"Id": "2", "Name": "COGS", "AccountType": "Cost of Goods Sold", "Active": True},
            {"Id": "3", "Name": "Bank", "AccountType": "Bank", "Active": True},
            {"Id": "4", "Name": "Old Repairs", "AccountType": "Expense", "Active": False},
        ]}}
        accounts = list_expense_accounts(connection)
        self.assertEqual([account["Id"] for account in accounts], ["2", "1"])

    @patch("accounting.quickbooks.quickbooks_request")
    def test_payment_account_list_only_includes_bank_and_credit_card(self, request):
        connection = self._connection()
        request.return_value = {"QueryResponse": {"Account": [
            {"Id": "1", "Name": "Operating", "AccountType": "Bank", "Active": True},
            {"Id": "2", "Name": "Company Card", "AccountType": "Credit Card", "Active": True},
            {"Id": "3", "Name": "Repairs", "AccountType": "Expense", "Active": True},
            {"Id": "4", "Name": "Closed", "AccountType": "Bank", "Active": False},
        ]}}
        accounts = list_payment_accounts(connection)
        self.assertEqual({account["Id"] for account in accounts}, {"1", "2"})
