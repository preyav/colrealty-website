from django.test import TestCase
from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import RequestFactory
from accounting.test_book_accounting import BookAccountingTests
from accounting.rent_services import ledger_data
from accounting.lease_financials import financial_timeline,ledger_display_metadata
from portal.templatetags.lease_income import statement_context
from common.models import FormFieldSetting


class FinancialPresentationTests(TestCase):
    charge=BookAccountingTests.charge
    receipt=BookAccountingTests.receipt
    @classmethod
    def setUpTestData(cls):
        BookAccountingTests.setUpTestData.__func__(cls)
        call_command('seed_financial_presentation',verbosity=0)

    def test_income_accounts_itemized_even_with_no_posted_activity(self):
        req=RequestFactory().get('/portal/properties/1/financials/')
        context=statement_context({'request':req},self.property)
        accounts=context['report']['properties'][0]['sections'][0]['accounts']
        self.assertIn(self.income.pk,[row['account'].pk for row in accounts])
        html=render_to_string('portal/lease_income_statement.html',{'income':context})
        self.assertIn(self.income.name,html)
        self.assertNotIn('class="financial-property"',html)
        self.assertIn('Expand all rows',html);self.assertIn('data-expand-icon',html)
        self.assertTrue(all(row['total']==0 for row in accounts))

    def test_ledger_metadata_uses_income_account_and_no_fake_invoice(self):
        self.charge();self.receipt()
        timeline=ledger_display_metadata(self.lease,financial_timeline(ledger_data(self.lease)))
        self.assertTrue(timeline['rows'])
        for row in timeline['rows']:
            self.assertEqual(row['account_label'],self.income.name)
            self.assertEqual(row['invoice_label'],'')
        self.assertEqual(timeline['balance'],0)

    def test_invoice_account_headers_and_sort_indexes(self):
        self.charge()
        ledger=ledger_data(self.lease)
        ui=FormFieldSetting.objects.get(form_key='lease_financials',field_key='ui').option_labels
        html=render_to_string('portal/lease_financials.html',{'lease':self.lease,'workspace':{'financial_ui':ui,'timeline':ledger_display_metadata(self.lease,financial_timeline(ledger)),'ledger':ledger}})
        self.assertIn('data-ledger-sort="invoice"',html);self.assertIn('data-ledger-sort="account"',html)
        self.assertIn('Invoice',html);self.assertIn(self.income.name,html)
        self.assertIn('transaction:3,reference:4',html)

    def test_seed_preserves_custom_column_labels(self):
        row=FormFieldSetting.objects.get(form_key='lease_financials',field_key='ui');row.option_labels['invoice']='Invoice number';row.save()
        call_command('seed_financial_presentation',verbosity=0)
        row.refresh_from_db();self.assertEqual(row.option_labels['invoice'],'Invoice number')
