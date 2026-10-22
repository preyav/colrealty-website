from django.test import TestCase,RequestFactory
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.urls import resolve,reverse
from django.template.loader import render_to_string
from common.models import FormFieldSetting
from .models import ChartAccount,FinancialAccount
from .workspace_views import accounts,chart_data
from .workspace import navigation,configure_form
from .forms import ChartAccountForm

class AccountingWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_accounting_workspace',verbosity=0)
        call_command('seed_chart_account_details',verbosity=0)
        call_command('seed_chart_account_actions',verbosity=0)
        call_command('seed_rent_ledger',verbosity=0)
        cls.staff=get_user_model().objects.create_user(username='accounts_staff',is_staff=True)
        cls.regular=get_user_model().objects.create_user(username='accounts_regular')
        cls.asset=ChartAccount.objects.create(code='1010',name='Operating bank',account_type='asset')
        cls.income=ChartAccount.objects.create(code='4000',name='Rent income',account_type='income')
        cls.inactive=ChartAccount.objects.create(code='5000',name='Legacy expense',account_type='expense',is_active=False)
        FinancialAccount.objects.create(name='Operating account',kind='bank',ledger_account=cls.asset)

    def request(self,query='',staff=True):
        request=RequestFactory().get(reverse('portal:finance_accounts')+query)
        request.user=self.staff if staff else self.regular
        request.resolver_match=resolve(request.path)
        return request

    def test_filters_and_account_numbers_search(self):
        data=chart_data(self.request().GET)
        self.assertEqual(data['count'],2)
        data=chart_data(self.request('?type=income&q=4000').GET)
        self.assertEqual([a.pk for a in data['accounts']],[self.income.pk])
        self.assertEqual(chart_data(self.request('?status=inactive').GET)['count'],1)
        self.assertEqual(chart_data(self.request('?status=all&type=asset&type=income').GET)['count'],2)

    def test_chart_and_banking_render_separately(self):
        response=accounts(self.request())
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Chart of accounts')
        self.assertContains(response,'data-show-codes')
        self.assertNotContains(response,'Operating account')
        response=accounts(self.request('?view=banking'))
        self.assertContains(response,'Operating account')
        self.assertNotContains(response,'Rent income')

    def test_csv_filters_and_formula_protection(self):
        ChartAccount.objects.create(code='7000',name='=Danger',account_type='expense')
        response=accounts(self.request('?type=expense&export=csv'))
        self.assertIn("'=Danger",response.content.decode())
        self.assertNotIn('Rent income',response.content.decode())
        self.assertEqual(ChartAccount.objects.count(),4)

    def test_navigation_and_staff_gate(self):
        items={item['key']:item for item in navigation()}
        self.assertIn('?view=banking',items['banking']['url'])
        self.assertTrue(items['bills']['url'])
        self.assertIn('general-ledger',items['general_ledger']['url'])
        self.assertEqual(accounts(self.request(staff=False)).status_code,302)

    def test_editable_labels_and_form_rendering(self):
        row=FormFieldSetting.objects.get(form_key='accounting_workspace',field_key='chart_name')
        row.label='Account display name';row.save()
        form=ChartAccountForm();configure_form(form,'chart')
        self.assertEqual(form.fields['name'].label,'Account display name')
        html=render_to_string('portal/finance_account_form.html',{'form':form,'account_kind':'chart','section':'finance','finance_subsection':'accounts'},request=self.request())
        self.assertIn('Account display name',html)
        self.assertIn('accounting-form-card',html)

    def test_seed_preserves_user_edits_and_accounts(self):
        row=FormFieldSetting.objects.get(form_key='accounting_workspace',field_key='chart_account_type')
        row.option_labels['income']='Revenue';row.save()
        call_command('seed_accounting_workspace',verbosity=0)
        row.refresh_from_db()
        self.assertEqual(row.option_labels['income'],'Revenue')
        self.assertEqual(ChartAccount.objects.count(),3)

    def test_all_data_columns_sort_in_both_directions(self):
        from django.http import QueryDict
        self.asset.cash_asset=True;self.asset.fund_type='reserve';self.asset.description='Zebra';self.asset.save()
        self.income.fund_type='operating';self.income.description='alpha';self.income.save()
        expected={
            'name':[self.inactive.pk,self.asset.pk,self.income.pk],
            'type':[self.asset.pk,self.inactive.pk,self.income.pk],
            'cash_asset':[self.inactive.pk,self.income.pk,self.asset.pk],
            'fund_type':[self.inactive.pk,self.income.pk,self.asset.pk],
            'notes':[self.inactive.pk,self.income.pk,self.asset.pk],
            'status':[self.asset.pk,self.income.pk,self.inactive.pk],
            'code':[self.asset.pk,self.income.pk,self.inactive.pk]}
        for column,ids in expected.items():
            asc=chart_data(QueryDict('status=all&sort='+column+'&direction=asc'))
            desc=chart_data(QueryDict('status=all&sort='+column+'&direction=desc'))
            self.assertEqual([a.pk for a in asc['accounts']],ids,column)
            self.assertEqual(desc['accounts'][0].pk,ids[-1],column)

    def test_sort_links_preserve_filters_and_csv_order(self):
        data=chart_data(self.request('?type=asset&status=all&q=bank&sort=name&direction=asc&show_codes=1').GET)
        header=next(h for h in data['headers'] if h['key']=='name')
        self.assertIn('type=asset',header['url']);self.assertIn('show_codes=1',header['url'])
        self.assertIn('direction=desc',header['url'])
        response=accounts(self.request('?status=all&sort=name&direction=desc&export=csv'))
        text=response.content.decode()
        self.assertLess(text.index('Rent income'),text.index('Operating bank'))

    def test_account_numbers_sort_numerically_and_invalid_sort_is_safe(self):
        ChartAccount.objects.create(code='20',name='Twenty',account_type='asset')
        ChartAccount.objects.create(code='100',name='One hundred',account_type='asset')
        data=chart_data(self.request('?sort=code').GET)
        codes=[a.code for a in data['accounts']]
        self.assertLess(codes.index('20'),codes.index('100'))
        data=chart_data(self.request('?sort=invalid&direction=invalid').GET)
        self.assertEqual(data['sort'],'name');self.assertEqual(data['direction'],'asc')
