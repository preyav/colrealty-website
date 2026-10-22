import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase,Client
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from properties.models import Property,PropertyUnit
from .models import ChartAccount
from .journal_models import JournalEntry,JournalLine
from .general_ledger import post_journal,reverse_journal,ledger_report
from .journal_forms import LedgerFilter

class GeneralLedgerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for command in ['seed_accounting_workspace','seed_chart_account_details','seed_chart_account_actions','seed_rent_ledger','seed_general_ledger']:
            call_command(command,verbosity=0)
        cls.staff=get_user_model().objects.create_user(username='journal_staff',is_staff=True)
        cls.regular=get_user_model().objects.create_user(username='journal_regular')
        cls.property=Property.objects.create(street_address='Ledger test property')
        cls.other_property=Property.objects.create(street_address='Other ledger property')
        cls.unit=PropertyUnit.objects.create(property=cls.property,unit_number='1')
        cls.other_unit=PropertyUnit.objects.create(property=cls.other_property,unit_number='1')
        cls.asset=ChartAccount.objects.create(code='1000',name='Asset account',account_type='asset')
        cls.income=ChartAccount.objects.create(code='4000',name='Income account',account_type='income')

    def data(self,**kwargs):
        return {'date':timezone.localdate(),'memo':'Verified journal','property':self.property,'unit':self.unit,'fund_type':'',**kwargs}

    def lines(self,amount='100'):
        return [{'account':self.asset,'debit':Decimal(amount),'credit':0},{'account':self.income,'credit':Decimal(amount),'debit':0}]

    def post(self,**kwargs):return post_journal(kwargs.pop('data',self.data()),kwargs.pop('lines',self.lines()),kwargs.pop('token',uuid.uuid4()),self.staff,**kwargs)

    def report(self,**kwargs):return ledger_report({'start':timezone.localdate(),'end':timezone.localdate(),'scope':'all',**kwargs})

    def test_balanced_journal_reports_normal_balances_and_idempotent_token(self):
        token=uuid.uuid4();journal=self.post(token=token)
        self.assertEqual(self.post(token=token).pk,journal.pk)
        self.assertEqual(JournalEntry.objects.count(),1);self.assertEqual(JournalLine.objects.count(),2)
        report=self.report();self.assertEqual(report['debit'],Decimal('100'));self.assertEqual(report['credit'],Decimal('100'))
        self.assertEqual([group['closing'] for group in report['groups']],[Decimal('100'),Decimal('100')])

    def test_unbalanced_or_invalid_lines_leave_no_records(self):
        cases=[self.lines()[:1],[{'account':self.asset,'debit':100,'credit':10},{'account':self.income,'debit':0,'credit':90}],self.lines('-1'),self.lines('NaN')]
        for lines in cases:
            with self.assertRaises(ValidationError):self.post(lines=lines)
        with self.assertRaises(ValidationError):self.post(lines=[{'account':self.asset,'debit':100,'credit':0},{'account':self.income,'credit':99,'debit':0}])
        self.assertFalse(JournalEntry.objects.exists());self.assertFalse(JournalLine.objects.exists())

    def test_unit_fund_and_future_date_validation(self):
        for data in [self.data(unit=self.other_unit),self.data(property=None),self.data(fund_type='invalid'),self.data(date=timezone.localdate()+timedelta(days=1))]:
            with self.assertRaises(ValidationError):self.post(data=data)
        self.asset.fund_type='operating';self.asset.save()
        with self.assertRaises(ValidationError):self.post()
        self.post(data=self.data(fund_type='operating'))

    def test_inactive_accounts_and_nonstaff_rejected(self):
        self.asset.is_active=False;self.asset.save()
        with self.assertRaises(ValidationError):self.post()
        with self.assertRaises(PermissionError):post_journal(self.data(),self.lines(),uuid.uuid4(),self.regular)

    def test_audit_failure_rolls_back_entire_journal(self):
        with patch('accounting.general_ledger.record_event',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):self.post()
        self.assertFalse(JournalEntry.objects.exists());self.assertFalse(JournalLine.objects.exists())

    def test_opening_balances_and_property_unit_account_filters(self):
        self.post(data=self.data(date=timezone.localdate()-timedelta(days=1)))
        self.post(lines=self.lines('20'))
        self.post(data=self.data(property=self.other_property,unit=self.other_unit),lines=self.lines('300'))
        report=self.report(property=self.property,unit=self.unit,accounts=[self.asset])
        self.assertEqual(report['count'],1)
        self.assertEqual(report['groups'][0]['opening'],Decimal('100'))
        self.assertEqual(report['groups'][0]['closing'],Decimal('120'))
        self.assertEqual(report['debit'],Decimal('20'))

    def test_reversal_preserves_original_and_can_reverse_inactive_accounts(self):
        original=self.post();self.asset.is_active=False;self.asset.save()
        reversal=reverse_journal(original.pk,timezone.localdate(),'Correction',uuid.uuid4(),self.staff)
        self.assertEqual(reversal.reversal_of_id,original.pk)
        self.assertEqual(JournalEntry.objects.count(),2)
        self.assertTrue(all(group['closing']==0 for group in self.report()['groups']))
        with self.assertRaises(ValidationError):reverse_journal(original.pk,timezone.localdate(),'Again',uuid.uuid4(),self.staff)
        with self.assertRaises(ValidationError):reverse_journal(reversal.pk,timezone.localdate(),'Again',uuid.uuid4(),self.staff)

    def test_posted_entry_and_lines_are_immutable(self):
        journal=self.post();journal.memo='Changed'
        with self.assertRaises(ValidationError):journal.save()
        with self.assertRaises(ValidationError):journal.delete()
        line=journal.lines.first();line.debit=1
        with self.assertRaises(ValidationError):line.save()
        journal.refresh_from_db();self.assertEqual(journal.memo,'Verified journal')

    def test_all_properties_excludes_company_and_is_default(self):
        self.post()
        self.post(data=self.data(property=None,unit=None))
        result=self.report(scope='properties')
        self.assertEqual(result['count'],2)
        self.client.force_login(self.staff)
        response=self.client.get(reverse('portal:general_ledger'))
        self.assertContains(response,'value="properties" selected')

    def test_unit_multiselection_and_property_level(self):
        today=timezone.localdate()
        second=PropertyUnit.objects.create(property=self.property,unit_number='2')
        self.post()
        self.post(data=self.data(unit=second))
        self.post(data=self.data(unit=None))
        base={'scope':'property:'+str(self.property.pk),'date_range':'custom','start':today,'end':today}
        def report(values):
            form=LedgerFilter({**base,'unit':values})
            self.assertTrue(form.is_valid(),form.errors)
            return ledger_report(form.cleaned_data)
        self.assertEqual(report(['all'])['count'],6)
        self.assertEqual(report([str(self.unit.pk),str(second.pk)])['count'],4)
        self.assertEqual(report(['property_level'])['count'],2)
        self.assertEqual(report(['property_level',str(self.unit.pk)])['count'],4)
        self.assertTrue(LedgerFilter({**base,'unit':['all',str(self.unit.pk)]}).is_valid())
        aggregate=LedgerFilter({**base,'scope':'properties','unit':['all_units']})
        self.assertTrue(aggregate.is_valid(),aggregate.errors)
        self.assertEqual(ledger_report(aggregate.cleaned_data)['count'],4)
        self.assertFalse(LedgerFilter({**base,'unit':[str(self.other_unit.pk)]}).is_valid())

    def test_single_property_unit_display_labels(self):
        form=LedgerFilter()
        self.assertEqual(form.unit_labels[str(self.unit.pk)],'1')
        self.property.unit_number='1602'
        self.property.save()
        self.assertEqual(LedgerFilter().unit_labels[str(self.unit.pk)],'1602')

    def test_combined_property_selector(self):
        today=timezone.localdate()
        data={'scope':'property:'+str(self.property.pk),'unit':self.unit.pk,'start':today,'end':today,'date_range':'custom'}
        form=LedgerFilter(data)
        self.assertTrue(form.is_valid(),form.errors)
        self.assertNotIn('property',form.fields)
        self.assertEqual(form.cleaned_data['property'],self.property)
        self.assertEqual(form.cleaned_data['scope'],'property')
        company=LedgerFilter({**data,'scope':'company','unit':''})
        self.assertFalse(company.is_valid())
        self.assertFalse(LedgerFilter({**data,'scope':'all'}).is_valid())
        self.assertTrue(all(value=='properties' or value.startswith('property:') for value,label in form.fields['scope'].choices))
        self.property.property_type='quadruplex'
        self.property.save()
        self.assertIn(self.property.get_property_type_display(),LedgerFilter.property_label(self.property))
        invalid=LedgerFilter({**data,'scope':'property:99999999'})
        self.assertFalse(invalid.is_valid())

    def test_filters_reject_invalid_dates_and_mismatched_unit(self):
        today=timezone.localdate()
        form=LedgerFilter({'scope':'property','property':self.property.pk,'unit':self.other_unit.pk,'start':today,'end':today-timedelta(days=1),'date_range':'custom'})
        self.assertFalse(form.is_valid());self.assertIn('unit',form.errors);self.assertIn('end',form.errors)

    def test_staff_pages_post_and_export_and_popout_menu(self):
        self.client.force_login(self.staff)
        page=self.client.get(reverse('portal:general_ledger'));self.assertEqual(page.status_code,200)
        self.assertContains(page,'accounting-popout');self.assertContains(page,'No posted journal entries')
        url=reverse('portal:journal_create');page=self.client.get(url);self.assertEqual(page.status_code,200)
        payload={'entry_token':page.context['entry_token'],'date':str(timezone.localdate()),'memo':'Web journal','property':self.property.pk,'unit':self.unit.pk,'fund_type':'',
            'lines-TOTAL_FORMS':'2','lines-INITIAL_FORMS':'0','lines-MIN_NUM_FORMS':'2','lines-MAX_NUM_FORMS':'50',
            'lines-0-account':self.asset.pk,'lines-0-debit':'25','lines-0-credit':'','lines-1-account':self.income.pk,'lines-1-debit':'','lines-1-credit':'25'}
        response=self.client.post(url,payload);self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.post(url,payload).status_code,302)
        self.assertEqual(JournalEntry.objects.count(),1)
        detail=self.client.get(response.url);self.assertEqual(detail.status_code,200);self.assertContains(detail,'Web journal')
        report=self.client.get(reverse('portal:general_ledger'),{'scope':'property','property':self.property.pk,'unit':self.unit.pk,'start':str(timezone.localdate()),'end':str(timezone.localdate()),'date_range':'custom','export':'csv'})
        self.assertEqual(report.status_code,200);self.assertIn('Web journal',report.content.decode())

    def test_csrf_and_nonstaff_gate(self):
        self.client.force_login(self.regular)
        self.assertEqual(self.client.get(reverse('portal:general_ledger')).status_code,302)
        client=Client(enforce_csrf_checks=True);client.force_login(self.staff)
        self.assertEqual(client.post(reverse('portal:journal_create'),{}).status_code,403)

    def test_posted_account_cannot_be_reclassified(self):
        from .forms import ChartAccountForm
        self.post()
        form=ChartAccountForm(instance=self.asset)
        self.assertTrue(form.fields['account_type'].disabled)
        self.asset.account_type='income'
        with self.assertRaises(ValidationError):self.asset.full_clean()
