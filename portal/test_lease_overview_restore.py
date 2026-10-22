from django.core.management import call_command
from django.test import TestCase
from common.models import FormFieldSetting
from leasing.lease_sections import SECTIONS, INFORMATION_FIELDS
from leasing.lease_summary import management_summary
from portal.test_lease_overview_tabs import LeaseOverviewTabsTests


class LeaseOverviewRestoreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        LeaseOverviewTabsTests.setUpTestData.__func__(cls)

    def test_all_populated_input_fields_restored_and_document_summary_stays_hidden(self):
        values={key:'Recorded value' for section,_,_,fields in SECTIONS if section not in ('overview','documents','notes') for key,_ in fields if key not in INFORMATION_FIELDS}
        values['included_addenda_and_exhibits']='Original document reference'
        self.lease.contract_details=values;self.lease.save()
        before=dict(self.lease.contract_details)
        call_command('restore_lease_overview_fields',verbosity=0)
        summary=management_summary(self.lease)
        keys={row['key'] for row in summary['sections'][0]['rows']}
        self.assertTrue((set(values)-{'included_addenda_and_exhibits'}).issubset(keys))
        self.assertNotIn('included_addenda_and_exhibits',keys)
        self.lease.refresh_from_db();self.assertEqual(self.lease.contract_details,before)

    def test_clause_with_blank_anchor_is_accessible_from_group_icon(self):
        self.lease.contract_details={'repair_request_instructions':'Exact recorded instructions'};self.lease.save()
        call_command('restore_lease_overview_fields',verbosity=0)
        groups=management_summary(self.lease)['sections'][0]['subsections']
        self.assertIn('Exact recorded instructions',[info['text'] for group in groups for info in group.get('information',[])])

    def test_custom_labels_and_formats_preserved_and_repeat_is_safe(self):
        row=FormFieldSetting.objects.get(form_key='lease_summary',field_key='prorated_rent_amount')
        row.label='Custom prorated rent';row.help_text='Custom help';row.option_labels={**row.option_labels,'format':'money'};row.save()
        call_command('restore_lease_overview_fields',verbosity=0)
        row.refresh_from_db();expected=row.option_labels.copy()
        call_command('restore_lease_overview_fields',verbosity=0)
        row.refresh_from_db()
        self.assertEqual(row.label,'Custom prorated rent');self.assertEqual(row.help_text,'Custom help');self.assertEqual(row.option_labels,expected)
