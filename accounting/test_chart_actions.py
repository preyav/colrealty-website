from unittest.mock import patch
from django.test import TestCase,RequestFactory
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from common.audit.models import AuditEvent
from .models import ChartAccount,FinancialAccount
from .chart_actions import change_account,chart_account_action

class ChartAccountActionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for command in ['seed_accounting_workspace','seed_chart_account_details','seed_chart_account_actions','seed_rent_ledger']:
            call_command(command,verbosity=0)
        cls.staff=get_user_model().objects.create_user(username='chart_action_staff',is_staff=True)
        cls.regular=get_user_model().objects.create_user(username='chart_action_regular')
        cls.account=ChartAccount.objects.create(code='1100',name='Unused cash',account_type='asset')

    def test_inactivate_and_reactivate_preserve_account_and_audit(self):
        change_account(self.account.pk,'inactivate',self.staff)
        self.account.refresh_from_db();self.assertFalse(self.account.is_active)
        change_account(self.account.pk,'activate',self.staff)
        self.account.refresh_from_db();self.assertTrue(self.account.is_active)
        self.assertEqual(AuditEvent.objects.filter(action__in=['CHART_ACCOUNT_ACTIVATED','CHART_ACCOUNT_INACTIVATED']).count(),2)

    def test_linked_bank_and_active_children_block_inactivation(self):
        FinancialAccount.objects.create(name='Linked bank',kind='bank',ledger_account=self.account)
        with self.assertRaises(ValidationError):change_account(self.account.pk,'inactivate',self.staff)
        FinancialAccount.objects.all().delete()
        ChartAccount.objects.create(code='1101',name='Subaccount',account_type='asset',parent=self.account)
        with self.assertRaises(ValidationError):change_account(self.account.pk,'inactivate',self.staff)

    def test_delete_unused_and_block_linked_account(self):
        account_id=self.account.pk
        FinancialAccount.objects.create(name='Linked bank',kind='bank',ledger_account=self.account)
        with self.assertRaises(ValidationError):change_account(account_id,'delete',self.staff)
        FinancialAccount.objects.all().delete()
        change_account(account_id,'delete',self.staff)
        self.assertFalse(ChartAccount.objects.filter(pk=account_id).exists())
        self.assertTrue(AuditEvent.objects.filter(action='CHART_ACCOUNT_DELETED').exists())

    def test_audit_failure_rolls_back_action(self):
        with patch('accounting.chart_actions.record_event',side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):change_account(self.account.pk,'inactivate',self.staff)
        self.account.refresh_from_db();self.assertTrue(self.account.is_active)

    def test_get_confirmation_does_not_mutate_and_nonstaff_cannot_write(self):
        request=RequestFactory().get('/confirmation/');request.user=self.staff
        response=chart_account_action(request,self.account.pk,'delete')
        self.assertEqual(response.status_code,200)
        self.assertTrue(ChartAccount.objects.filter(pk=self.account.pk).exists())
        with self.assertRaises(PermissionError):change_account(self.account.pk,'delete',self.regular)

    def test_inactive_account_leaves_active_view_and_offers_only_reactivate(self):
        from .workspace_views import accounts,chart_data
        from django.http import QueryDict
        change_account(self.account.pk,'inactivate',self.staff)
        active=chart_data(QueryDict('status=active'))
        inactive=chart_data(QueryDict('status=inactive'))
        self.assertNotIn(self.account.pk,[account.pk for account in active['accounts']])
        self.assertIn(self.account.pk,[account.pk for account in inactive['accounts']])
        request=RequestFactory().get('/portal/finance/accounts/?status=inactive');request.user=self.staff
        response=accounts(request)
        self.assertContains(response,'Reactivate account')
        self.assertNotContains(response,'Move transactions')
        self.assertNotContains(response,'Delete account')
        self.assertContains(response,'(Inactive)')
        change_account(self.account.pk,'activate',self.staff)
        self.assertIn(self.account.pk,[account.pk for account in chart_data(QueryDict('status=active'))['accounts']])
        self.assertNotIn(self.account.pk,[account.pk for account in chart_data(QueryDict('status=inactive'))['accounts']])
