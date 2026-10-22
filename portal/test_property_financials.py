from django.test import TestCase
from django.urls import reverse
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from common.models import FormFieldSetting
from accounting.test_book_accounting import BookAccountingTests
from accounting.book_models import BookPosting


class PropertyFinancialPlacementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        BookAccountingTests.setUpTestData.__func__(cls)
        call_command('seed_property_financials',verbosity=0)
        cls.admin=get_user_model().objects.create_superuser(username='property_financial_admin',email='property@example.test',password='ExampleOnly2026')

    def setUp(self):self.client.force_login(self.admin)

    def test_property_statement_has_filters_and_correct_scope(self):
        before=BookPosting.objects.count()
        response=self.client.get(reverse('portal:property_financials',args=[self.property.pk]),{'income_period':'six','income_basis':'accrual','lease_financial_view':'ledger','scope':'company'})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Income Statement');self.assertContains(response,'Cash basis');self.assertContains(response,'Accrual basis')
        income=response.context['income']
        self.assertEqual(income['active'],'income');self.assertEqual(len(income['report']['months']),6)
        self.assertEqual([p['property'].pk for p in income['report']['properties']],[self.property.pk])
        self.assertTrue(income['action'].endswith('#property-financials'))
        self.assertEqual(BookPosting.objects.count(),before)

    def test_lease_panel_is_ledger_and_links_to_property_statement(self):
        html=render_to_string('portal/lease_financials.html',{'lease':self.lease,'workspace':{'financial_ui':{'ledger':'Ledger','financials':'Financials'},'timeline':{'rows':[],'balance':0},'ledger':{'receipts':[]}}})
        self.assertIn('financial-subnav',html)
        self.assertIn(reverse('portal:property_financials',args=[self.property.pk]),html)
        self.assertNotIn('lease-income-controls',html)
        self.assertNotIn('data-lease-ledger hidden',html)
        self.assertIn('data-ledger-sort',html)

    def test_seed_preserves_property_report_settings_and_access_is_staff_only(self):
        row=FormFieldSetting.objects.get(form_key='property_income_statement',field_key='ui');row.option_labels['default_period']='month';row.save()
        call_command('seed_property_financials',verbosity=0)
        row.refresh_from_db();self.assertEqual(row.option_labels['default_period'],'month')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('portal:property_financials',args=[self.property.pk])).status_code,302)

    def test_property_navigation_contains_financials(self):
        html=render_to_string('portal/property_workspace_nav.html',{'property':self.property})
        self.assertIn(reverse('portal:property_financials',args=[self.property.pk]),html)
        self.assertIn('Overview',html)
