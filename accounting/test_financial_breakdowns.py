from decimal import Decimal
from urllib.parse import urlsplit, parse_qs
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from common.models import FormFieldSetting
from .test_general_ledger import GeneralLedgerTests
from .financials import financial_report, FinancialFilter
from .models import ChartAccount

class FinancialBreakdownTests(TestCase):
    setUpTestData=classmethod(GeneralLedgerTests.setUpTestData.__func__)
    post=GeneralLedgerTests.post
    data=GeneralLedgerTests.data
    lines=GeneralLedgerTests.lines
    def setUp(self):call_command('seed_financials',verbosity=0)
    def report(self,**kwargs):
        return financial_report({'period':'three','scope':'property','property':self.property,**kwargs},timezone.localdate())['properties'][0]
    def classify(self,account,value):
        row=FormFieldSetting.objects.get(form_key='financial_account_classification',field_key=str(account.pk));row.option_labels={'classification':value};row.save()
    def test_empty_accounts_and_historical_inactive_accounts(self):
        unused=ChartAccount.objects.create(code='4900',name='Unused income',account_type='income')
        self.post(); self.income.is_active=False;self.income.save()
        ids=[r['account'].pk for r in self.report()['sections'][0]['accounts']]
        self.assertIn(unused.pk,ids);self.assertIn(self.income.pk,ids)
        self.assertNotIn(unused.pk,[r['account'].pk for r in self.report(show_empty=False)['sections'][0]['accounts']])
    def test_location_totals_and_operating_classification(self):
        expense=ChartAccount.objects.create(code='5700',name='Non operating test',account_type='expense')
        call_command('seed_financials',verbosity=0)
        self.post();self.post(data=self.data(unit=None))
        self.post(lines=[{'account':expense,'debit':30,'credit':0},{'account':self.asset,'debit':0,'credit':30}])
        self.assertFalse(self.report()['operating_ready'])
        self.classify(self.income,'operating');self.classify(expense,'non_operating')
        row=self.report();self.assertTrue(row['operating_ready']);self.assertEqual(row['operating_total'],200);self.assertEqual(row['total'],170)
        self.assertEqual(sum((x['total'] for x in row['net_units']),Decimal('0')),170)
        self.assertEqual({u['label'] for u in row['net_units']},{'Property level','1'})
    def test_unit_filter_and_drilldown_links(self):
        self.post(); self.client.force_login(self.staff)
        form=FinancialFilter({'scope':'property:'+str(self.property.pk),'unit':[str(self.unit.pk)],'period':'three','show_empty':'1'})
        self.assertTrue(form.is_valid(),form.errors)
        row=financial_report(form.cleaned_data,timezone.localdate())['properties'][0]
        self.assertEqual([u['label'] for u in row['net_units']],['1'])
        cell=row['sections'][0]['accounts'][0]['units'][0]['cells'][-1]
        response=self.client.get(cell['url']);self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['report']['count'],1)
        self.assertEqual(parse_qs(urlsplit(cell['url']).query)['unit'],[str(self.unit.pk)])
    def test_page_renders_rows_and_seed_preserves_classification(self):
        self.post();self.classify(self.income,'operating');call_command('seed_financials',verbosity=0)
        self.assertTrue(self.report()['operating_ready'])
        self.client.force_login(self.staff)
        response=self.client.get(reverse('portal:finance_dashboard'),{'scope':'property:'+str(self.property.pk),'period':'three','search':'1'})
        self.assertContains(response,'Net operating income');self.assertContains(response,'Property level');self.assertContains(response,'Income account')
        self.assertContains(response,'value="cash"')
        self.assertContains(response,'aria-expanded="true"')
