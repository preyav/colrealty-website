from datetime import timedelta
from django.test import TestCase
from django.core.management import call_command
from django.template.loader import get_template, render_to_string
from accounting.test_book_accounting import BookAccountingTests
from common.models import FormFieldSetting
from leasing.models import LeaseAgreement
from leasing.lease_summary import management_summary
from portal.templatetags.lease_agreements import lease_agreement_history


class LeaseOverviewTabsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        BookAccountingTests.setUpTestData.__func__(cls)
        call_command('seed_lease_summary', verbosity=0)
        call_command('seed_lease_overview_tabs', verbosity=0)
        for key, group in [('included_addenda_and_exhibits', 'documents'), ('pet_name', 'pets')]:
            row=FormFieldSetting.objects.get(form_key='lease_summary',field_key=key)
            row.option_labels={**row.option_labels,'subsection':group}
            row.save()
        FormFieldSetting.objects.get_or_create(form_key='lease_summary',field_key='group-additional',defaults={'label':'Additional Information'})
        FormFieldSetting.objects.get_or_create(form_key='lease_summary',field_key='group-pets',defaults={'label':'Pets'})
        cls.lease.contract_details={'pet_name':'Spot','included_addenda_and_exhibits':'Redundant document summary'}
        cls.lease.save()

    def test_merge_preserves_populated_operations_and_removes_document_summary(self):
        data=management_summary(self.lease)
        self.assertEqual(len(data['sections']),1)
        self.assertEqual(data['sections'][0]['title'],'Lease Overview')
        keys={row['key'] for row in data['sections'][0]['rows']}
        self.assertIn('monthly_rent',keys)
        self.assertIn('pet_name',keys)
        self.assertNotIn('included_addenda_and_exhibits',keys)
        self.assertEqual([row['title'] for row in data['navigation']][:3],['Lease Overview','Documents','Requests & Maintenance'])
        self.lease.refresh_from_db()
        self.assertIn('included_addenda_and_exhibits',self.lease.contract_details)

    def test_seed_preserves_custom_labels(self):
        row=FormFieldSetting.objects.get(form_key='lease_summary',field_key='documents')
        row.label='Custom documents';row.save()
        call_command('seed_lease_overview_tabs',verbosity=0)
        row.refresh_from_db();self.assertEqual(row.label,'Custom documents')

    def test_newest_first_display_keeps_latest_terms(self):
        # Supply other pre-existing document configuration required by the inclusion tag.
        FormFieldSetting.objects.get_or_create(form_key='lease_agreement',field_key='amendment_text',defaults={'label':'Amendments'})
        for i in range(2):
            LeaseAgreement.objects.create(lease=self.lease,title='Extension '+str(i),effective_date=self.today-timedelta(days=20-i),status='executed',rent_action='changed',monthly_rent=2500+i*100,recorded_by=self.staff)
        data=lease_agreement_history({},self.lease,compact=True)
        self.assertEqual([x['agreement'].title for x in data['history_items']],['Extension 1','Extension 0'])
        self.assertEqual(data['recorded_terms']['monthly_rent'],2600)
        # Compile the complete page and tabs, and render chronology without document widgets.
        get_template('portal/lease_detail.html');get_template('portal/lease_workspace_tabs.html')
        from django.template import engines
        source=get_template('portal/lease_agreement_history.html').template.source.replace('{% lease_document_panel lease a %}','').replace('{% lease_document_panel lease %}','')
        html=engines['django'].from_string(source).render(data)
        self.assertLess(html.index('Extension 1'),html.index('Extension 0'))
        self.assertLess(html.index('Extension 0'),html.index('<b>Original lease</b>'))
