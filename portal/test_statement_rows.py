from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.core.management import call_command
from django.contrib.auth import get_user_model
from accounting.test_book_accounting import BookAccountingTests
from accounting.statement_preferences import IncomeStatementPreference
from accounting.book_models import BookPosting
from accounting.book_services import post_rent_charge,post_rent_receipt
from accounting.models import ChartAccount


class StatementRowsTests(TestCase):
    setUpTestData=classmethod(BookAccountingTests.setUpTestData.__func__)
    charge=BookAccountingTests.charge
    receipt=BookAccountingTests.receipt

    def setUp(self):
        for cmd in ['seed_property_financials','seed_income_statement_rows']:call_command(cmd,verbosity=0)
        self.staff.is_superuser=True;self.staff.save()
        self.client.force_login(self.staff)
        self.url=reverse('portal:property_financials',args=[self.property.pk])
        self.unused=ChartAccount.objects.create(code='4900',name='Unused income',account_type='income')
        self.charge();self.receipt('100')

    def report(self):
        return self.client.get(self.url).context['income']

    def rows(self,income):
        return [row for section in income['report']['properties'][0]['sections'] for row in section['accounts']]

    def test_default_hides_only_accounts_without_activity(self):
        context=self.report();rows=self.rows(context)
        self.assertEqual([r['account'].pk for r in rows],[self.income.pk])
        self.assertGreater(context['hidden_empty'],0)
        self.assertEqual(context['report']['properties'][0]['total'],100)
        self.assertFalse(IncomeStatementPreference.objects.exists())

    def test_custom_rows_remembered_without_altering_totals_or_drilldowns(self):
        before=BookPosting.objects.count()
        response=self.client.post(self.url,{'row_action':'save','hide_empty':'on','accounts':[str(self.unused.pk)],'income_period':'six','income_basis':'cash'})
        self.assertEqual(response.status_code,302);self.assertIn('income_period=six',response.url)
        context=self.report();self.assertEqual(self.rows(context),[])
        self.assertEqual(context['hidden_activity'],1)
        item=context['report']['properties'][0]
        self.assertEqual(item['total'],100)
        self.assertIn('accounts='+str(self.income.pk),item['net_cells'][-1]['url'])
        self.assertEqual(BookPosting.objects.count(),before)
        self.assertEqual(IncomeStatementPreference.objects.get(user=self.staff).hidden_account_ids.count(self.income.pk),1)
        self.assertContains(self.client.get(self.url),'Totals and their detail links still include all applicable transactions.')

    def test_show_all_restores_and_preferences_are_user_specific(self):
        self.client.post(self.url,{'row_action':'save','hide_empty':'on','accounts':[]})
        second=get_user_model().objects.create_user(username='other_report_user',is_staff=True)
        self.client.force_login(second)
        self.assertIn(self.income.pk,[r['account'].pk for r in self.rows(self.report())])
        self.client.force_login(self.staff)
        self.client.post(self.url,{'row_action':'show_all'})
        preference=IncomeStatementPreference.objects.get(user=self.staff)
        self.assertFalse(preference.hide_empty);self.assertEqual(preference.hidden_account_ids,[])
        self.assertIn(self.unused.pk,[r['account'].pk for r in self.rows(self.report())])

    def test_invalid_ids_and_nonstaff_cannot_save_preferences(self):
        response=self.client.post(self.url,{'row_action':'save','accounts':['not-an-account']})
        self.assertEqual(response.status_code,200)
        self.assertFalse(IncomeStatementPreference.objects.exists())
        user=get_user_model().objects.create_user(username='tenant_report_user')
        self.client.force_login(user)
        self.assertEqual(self.client.post(self.url,{'row_action':'show_all'}).status_code,302)
        self.assertFalse(IncomeStatementPreference.objects.exists())

    def test_net_zero_account_with_transactions_remains_visible(self):
        from accounting.book_services import reverse_source
        from django.utils import timezone
        prefix=BookPosting.objects.filter(source_key__startswith='rent-allocation:',basis='cash').first().source_key
        reverse_source(self.config,[prefix],timezone.localdate(),'Report visibility check',self.staff)
        context=self.report()
        row=next(r for r in self.rows(context) if r['account'].pk==self.income.pk)
        self.assertEqual(row['total'],Decimal('0'))
        self.assertTrue(row['transactions'])

    def test_seed_preserves_configured_labels(self):
        from common.models import FormFieldSetting
        row=FormFieldSetting.objects.get(form_key='income_statement_rows',field_key='ui')
        row.option_labels['customize']='Choose report accounts';row.save()
        call_command('seed_income_statement_rows',verbosity=0)
        row.refresh_from_db();self.assertEqual(row.option_labels['customize'],'Choose report accounts')
