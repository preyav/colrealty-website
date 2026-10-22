import uuid
from django.test import TestCase,RequestFactory
from django.core.management import call_command
from django.template.loader import render_to_string
from django.utils import timezone
from common.models import FormFieldSetting
from accounting.test_book_accounting import BookAccountingTests
from accounting.financials import month_start
from accounting.models import ChartAccount
from accounting.book_models import BookPosting
from accounting.general_ledger import post_journal
from portal.templatetags.lease_income import lease_income_statement


class LeaseIncomeTests(TestCase):
    charge=BookAccountingTests.charge
    receipt=BookAccountingTests.receipt
    @classmethod
    def setUpTestData(cls):
        BookAccountingTests.setUpTestData.__func__(cls)
        call_command('seed_lease_income_statement',verbosity=0)

    def report(self,**params):
        request=RequestFactory().get('/portal/leases/1/',params);request.user=self.staff
        return lease_income_statement({'request':request},self.lease)

    def test_default_cash_and_separate_month_recognition(self):
        self.charge(month_start(self.today,-1));self.receipt()
        cash=self.report();accrual=self.report(income_basis='accrual')
        self.assertEqual(cash['form'].cleaned_data['income_basis'],'cash')
        self.assertEqual(cash['report']['properties'][0]['net'],[0,0,2400])
        self.assertEqual(accrual['report']['properties'][0]['net'],[0,2400,0])
        self.assertEqual(len(cash['report']['months']),3)

    def test_entity_default_and_period_validation(self):
        self.entity.default_basis='accrual';self.entity.save()
        result=self.report(income_period='six')
        self.assertEqual(result['form'].cleaned_data['income_basis'],'accrual')
        self.assertEqual(len(result['report']['months']),6)
        invalid=self.report(income_period='invalid',income_basis='both')
        self.assertIsNone(invalid['report']);self.assertIn('income_period',invalid['form'].errors)

    def test_income_expense_net_and_operating_totals(self):
        expense=ChartAccount.objects.create(code='5999',name='Report repair',account_type='expense')
        for account in [self.income,expense]:
            FormFieldSetting.objects.update_or_create(form_key='financial_account_classification',field_key=str(account.pk),defaults={'label':account.name,'option_labels':{'classification':'operating'}})
        for amount,account,income in [(100,self.income,True),(30,expense,False)]:
            lines=[{'account':self.asset,'debit':amount if income else 0,'credit':0 if income else amount},{'account':account,'credit':amount if income else 0,'debit':0 if income else amount}]
            post_journal({'date':self.today,'memo':'Report test','property':self.property,'unit':self.unit,'entity':self.entity,'basis':'both'},lines,uuid.uuid4(),self.staff)
        before=BookPosting.objects.count();item=self.report()['report']['properties'][0]
        self.assertEqual(item['sections'][0]['total'],100);self.assertEqual(item['sections'][1]['total'],30)
        self.assertEqual(item['total'],70);self.assertEqual(item['operating_total'],70);self.assertTrue(item['operating_ready'])
        self.assertEqual(BookPosting.objects.count(),before)

    def test_missing_configuration_and_unposted_coverage_not_silently_complete(self):
        self.config.enabled=False;self.config.save()
        self.charge()
        self.assertTrue(self.report()['incomplete'])
        self.config.delete()
        result=self.report();self.assertIsNone(result['report']);self.assertIsNone(result['config'])
        html=render_to_string('portal/lease_income_statement.html',{'income':result})
        self.assertIn('Assign this property to an accounting entity',html)

    def test_scope_is_fixed_and_ledger_available(self):
        result=self.report(scope='company',entity='9999',income_period='month')
        self.assertEqual([r['property'].pk for r in result['report']['properties']],[self.property.pk])
        ledger=self.report(lease_financial_view='ledger')
        self.assertEqual(ledger['active'],'ledger');self.assertIsNone(ledger['report'])
        self.assertIn('#lease-financials',ledger['income_url'])

    def test_template_controls_totals_and_editable_labels(self):
        result=self.report()
        html=render_to_string('portal/lease_income_statement.html',{'income':result})
        for label in ['Cash basis','Accrual basis','Total income','Total expenses','Net operating income','Net income','Three months to date']:
            self.assertIn(label,html)
        self.assertIn('income_period',html);self.assertIn('income_basis',html)
        setting=FormFieldSetting.objects.get(form_key='lease_income_statement',field_key='ui')
        setting.option_labels['income_statement']='Property statement';setting.save()
        call_command('seed_lease_income_statement',verbosity=0)
        self.assertEqual(self.report()['ui']['income_statement'],'Property statement')
