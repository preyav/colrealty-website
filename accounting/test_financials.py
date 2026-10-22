from decimal import Decimal
import uuid
from django.test import TestCase
from django.urls import reverse
from django.core.management import call_command
from django.utils import timezone
from .test_general_ledger import GeneralLedgerTests
from .financials import FinancialFilter,financial_report,month_start
from .general_ledger import post_journal

class FinancialsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        GeneralLedgerTests.setUpTestData.__func__(cls)
        call_command('seed_financials',verbosity=0)

    def test_monthly_totals_use_income_expenses_and_reversals(self):
        from .models import ChartAccount
        today=timezone.localdate()
        expense=ChartAccount.objects.create(code='5009',name='Verified repairs',account_type='expense')
        def post(date,lines):
            post_journal({'date':date,'memo':'Verified test entry','property':self.property,'unit':self.unit,'fund_type':''},lines,uuid.uuid4(),self.staff)
        post(month_start(today,-1),[{'account':self.asset,'debit':100,'credit':0},{'account':self.income,'debit':0,'credit':100}])
        post(today,[{'account':expense,'debit':30,'credit':0},{'account':self.asset,'debit':0,'credit':30}])
        post(today,[{'account':self.income,'debit':10,'credit':0},{'account':self.asset,'debit':0,'credit':10}])
        report=financial_report({'scope':'property','property':self.property,'period':'three'},today)
        row=report['properties'][0]
        self.assertEqual(row['net'],[Decimal('0'),Decimal('100'),Decimal('-40')])
        self.assertEqual(row['total'],Decimal('60'))
        self.assertEqual(len(row['sections'][0]['accounts']),1)
        self.assertEqual(len(report['months']),3)
        self.assertEqual(month_start(today.replace(year=2026,month=1),-2).isoformat(),'2025-11-01')

    def test_initial_page_search_and_validation(self):
        call_command('seed_financials',verbosity=0)
        self.client.force_login(self.staff)
        url=reverse('portal:finance_dashboard')
        response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertIsNone(response.context['report'])
        self.assertContains(response,'value="three" selected')
        response=self.client.get(url,{'search':'1','scope':'property:'+str(self.property.pk),'period':'three'})
        self.assertEqual(response.context['report']['count'],1)
        self.assertContains(response,'financial-property-')
        self.assertContains(response,'No posted income or expense')
        invalid=self.client.get(url,{'search':'1','scope':'property:999999','period':'invalid'})
        self.assertIsNone(invalid.context['report'])
        self.assertTrue(invalid.context['form'].errors)

    def test_unit_filters_and_seed_preserves_edits(self):
        today=timezone.localdate()
        form=FinancialFilter({'scope':'property:'+str(self.property.pk),'unit':[str(self.other_unit.pk)],'period':'three'})
        self.assertFalse(form.is_valid())
        from common.models import FormFieldSetting
        row=FormFieldSetting.objects.get(form_key='financials',field_key='ui')
        row.option_labels['title']='Custom finance';row.save()
        call_command('seed_financials',verbosity=0);row.refresh_from_db()
        self.assertEqual(row.option_labels['title'],'Custom finance')
        self.assertEqual(financial_report({'period':'month','scope':'properties'},today)['start'],today.replace(day=1))

    def test_staff_and_method_restrictions(self):
        url=reverse('portal:finance_dashboard')
        self.client.force_login(self.regular)
        self.assertEqual(self.client.get(url).status_code,302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(url).status_code,405)
