from unittest.mock import patch
from datetime import date
from django.test import TestCase, RequestFactory, Client
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.urls import reverse, resolve
from common.audit.models import AuditEvent
from .models import ChartAccount, FinancialAccount
from .book_models import AccountingEntity, EntityBank
from .bank_actions import change_bank_account, bank_account_action


class BankActionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for command in ['seed_accounting_workspace','seed_chart_account_details','seed_chart_account_actions','seed_rent_ledger','seed_bank_account_actions']:
            call_command(command,verbosity=0)
        cls.actor=get_user_model().objects.create_superuser(username='bank_admin',email='bank@example.com',password='example-only')
        cls.staff=get_user_model().objects.create_user(username='bank_staff',is_staff=True)
        cls.ledger=ChartAccount.objects.create(code='9901',name='Test bank ledger',account_type='asset')
        cls.bank=FinancialAccount.objects.create(name='Test bank',kind='bank',ledger_account=cls.ledger)

    def test_unused_delete_preserves_chart_and_audit(self):
        pk=self.bank.pk
        change_bank_account(pk,'delete',self.actor)
        self.assertFalse(FinancialAccount.objects.filter(pk=pk).exists())
        self.assertTrue(ChartAccount.objects.filter(pk=self.ledger.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(action='FINANCIAL_ACCOUNT_DELETED').exists())

    def test_opening_balance_can_inactivate_and_reactivate(self):
        self.bank.opening_balance=100;self.bank.save()
        change_bank_account(self.bank.pk,'inactivate',self.actor)
        self.bank.refresh_from_db();self.assertFalse(self.bank.is_active);self.assertEqual(self.bank.opening_balance,100)
        change_bank_account(self.bank.pk,'activate',self.actor)
        self.bank.refresh_from_db();self.assertTrue(self.bank.is_active)

    def test_unused_ownership_mapping_is_audited_and_removed(self):
        entity=AccountingEntity.objects.create(name='Test entity')
        EntityBank.objects.create(entity=entity,bank=self.bank)
        change_bank_account(self.bank.pk,'delete',self.actor)
        self.assertFalse(EntityBank.objects.filter(bank_id=self.bank.pk).exists())
        self.assertTrue(AccountingEntity.objects.filter(pk=entity.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(action='ENTITY_BANK_DELETED').exists())

    def test_journal_blocks_delete(self):
        from .journal_models import JournalEntry,JournalLine
        journal=JournalEntry.objects.create(date=date.today(),memo='Existing history',created_by=self.actor)
        JournalLine.objects.create(journal=journal,account=self.ledger,debit=10)
        with self.assertRaises(ValidationError):change_bank_account(self.bank.pk,'delete',self.actor)

    def test_permission_and_get_confirmation(self):
        with self.assertRaises(PermissionDenied):change_bank_account(self.bank.pk,'delete',self.staff)
        request=RequestFactory().get('/');request.user=self.actor
        self.assertEqual(bank_account_action(request,self.bank.pk,'delete').status_code,200)
        self.assertTrue(FinancialAccount.objects.filter(pk=self.bank.pk).exists())

    def test_post_redirect_csrf_and_action_route(self):
        url=reverse('portal:finance_bank_account_action',args=[self.bank.pk,'delete'])
        self.assertIn('/actions/delete/',url)
        self.client.force_login(self.actor)
        response=self.client.post(url)
        self.assertRedirects(response,reverse('portal:finance_accounts')+'?view=banking',fetch_redirect_response=False)
        client=Client(enforce_csrf_checks=True);client.force_login(self.actor)
        self.assertEqual(client.post(url).status_code,403)

    def test_audit_failure_rolls_back_delete(self):
        with patch('accounting.bank_actions.record_event',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):change_bank_account(self.bank.pk,'delete',self.actor)
        self.assertTrue(FinancialAccount.objects.filter(pk=self.bank.pk).exists())

    def test_banking_list_actions_render(self):
        from .workspace_views import accounts
        request=RequestFactory().get('/?view=banking');request.user=self.actor
        response=accounts(request)
        self.assertContains(response,reverse('portal:finance_bank_account_action',args=[self.bank.pk,'delete']))
        self.assertContains(response,reverse('portal:finance_bank_account_action',args=[self.bank.pk,'inactivate']))

    def test_nonzero_opening_balance_delete_keeps_audit(self):
        self.bank.opening_balance='24448.07';self.bank.save()
        change_bank_account(self.bank.pk,'delete',self.actor)
        event=AuditEvent.objects.get(action='FINANCIAL_ACCOUNT_DELETED')
        self.assertEqual(event.old_values['opening_balance'],'24448.07')
        self.assertTrue(ChartAccount.objects.filter(pk=self.ledger.pk).exists())

    def test_reconciliation_blocks_mapping_cleanup(self):
        from .book_models import BankReconciliation
        entity=AccountingEntity.objects.create(name='Reconciled entity')
        mapping=EntityBank.objects.create(entity=entity,bank=self.bank)
        BankReconciliation.objects.create(entity_bank=mapping,statement_start=date(2026,1,1),statement_end=date(2026,1,31),opening_balance=0,closing_balance=0)
        with self.assertRaises(ValidationError):change_bank_account(self.bank.pk,'delete',self.actor)
        self.assertTrue(EntityBank.objects.filter(pk=mapping.pk).exists())

    def test_mapping_cleanup_rolls_back_if_bank_audit_fails(self):
        entity=AccountingEntity.objects.create(name='Rollback entity')
        mapping=EntityBank.objects.create(entity=entity,bank=self.bank)
        from .bank_actions import record_event as real_event
        def audited(**kwargs):
            if kwargs['action']=='FINANCIAL_ACCOUNT_DELETED':raise RuntimeError('audit failed')
            return real_event(**kwargs)
        with patch('accounting.bank_actions.record_event',side_effect=audited):
            with self.assertRaises(RuntimeError):change_bank_account(self.bank.pk,'delete',self.actor)
        self.assertTrue(EntityBank.objects.filter(pk=mapping.pk).exists())
        self.assertTrue(FinancialAccount.objects.filter(pk=self.bank.pk).exists())
