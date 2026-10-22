from types import SimpleNamespace
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils import timezone
from django.urls import reverse
from accounting.test_book_accounting import BookAccountingTests
from accounting.book_models import AccountingEntity, EntityBank, BookPosting
from accounting.models import FinancialAccount, ChartAccount
from accounting.book_reports import owner_funds
from properties.models import PropertyUnit
from maintenance.models import MaintenanceRequest, WorkOrder
from portal.property_overview import build_overview
from portal.settings_forms import PropertyAccountingForm


class PropertyOverviewTests(TestCase):
    setUpTestData=classmethod(BookAccountingTests.setUpTestData.__func__)

    def setUp(self):
        call_command('seed_property_overview',verbosity=0)

    def overview(self,unit=None,current=None,requests=(),work=()):
        unit=unit or self.unit
        return build_overview(self.property,[{'unit':unit,'current_lease':self.lease if current else None,'upcoming_lease':None}], [self.lease] if current else [],requests,work)

    def test_single_unit_summary_and_empty_cash_is_provisional(self):
        context=self.overview(current=True)
        self.assertFalse(context['show_units']);self.assertEqual(context['single_unit'],self.unit)
        self.assertEqual(context['current_count'],1);self.assertEqual(context['occupancy'],'Occupied')
        self.assertEqual(context['funds']['cash'],0);self.assertFalse(context['funds']['reconciled'])
        html=render_to_string('portal/property_cash_banking.html',{'overview':context,'property':self.property})
        self.assertIn('Pending review',html);self.assertIn('Not configured',html)

    def test_multiple_units_keep_unit_access_and_review_unconfirmed_occupancy(self):
        other=PropertyUnit.objects.create(property=self.property,unit_number='2',status='vacant')
        rows=[{'unit':self.unit,'current_lease':self.lease,'upcoming_lease':None},{'unit':other,'current_lease':None,'upcoming_lease':None}]
        result=build_overview(self.property,rows,[self.lease],[],[])
        self.assertTrue(result['show_units']);self.assertEqual(result['occupancy'],'1 / 2 Occupied')
        other.status='occupied'
        self.assertEqual(build_overview(self.property,rows,[self.lease],[],[])['occupancy'],'Occupancy needs review')

    def test_image_existing_field_and_unsafe_url_fallback(self):
        self.property.main_image_url='https://example.test/property.jpg'
        self.assertEqual(self.overview()['image'],self.property.main_image_url)
        self.property.main_image_url='javascript:alert(1)'
        self.assertEqual(self.overview()['image'],'')

    def test_bank_roles_validate_entity_and_remain_editable_after_posting(self):
        self.config.operating_bank=self.bank;self.config.full_clean();self.config.save()
        self.assertEqual(self.overview()['banking'][0]['bank'],self.bank)
        entity=AccountingEntity.objects.create(name='Unrelated entity')
        account=ChartAccount.objects.create(code='1099',name='Other bank asset',account_type='asset')
        bank=FinancialAccount.objects.create(name='Other bank',ledger_account=account)
        EntityBank.objects.create(entity=entity,bank=bank)
        self.config.deposit_bank=bank
        with self.assertRaises(ValidationError):self.config.full_clean()
        form=PropertyAccountingForm(instance=self.config)
        self.assertNotIn(bank,list(form.fields['deposit_bank'].queryset))
        self.assertFalse(form.fields['operating_bank'].disabled)

    def test_cash_is_property_scoped_and_not_bank_opening_balance(self):
        self.bank.opening_balance=Decimal('999999');self.bank.save()
        context=self.overview()
        self.assertEqual(context['funds']['cash'],0)
        self.assertEqual(BookPosting.objects.count(),0)

    def test_work_orders_grouped_without_losing_direct_work(self):
        request=MaintenanceRequest.objects.create(unit=self.unit,title='Repair request',description='Repair')
        linked=WorkOrder.objects.create(unit=self.unit,title='Linked repair',description='Repair',maintenance_request=request)
        direct=WorkOrder.objects.create(unit=self.unit,title='Direct repair',description='Repair')
        result=self.overview(requests=[request],work=[linked,direct])
        self.assertEqual(result['maintenance'][0]['work_orders'],[linked])
        self.assertEqual(result['standalone_work_orders'],[direct])

    def test_template_omits_duplicate_sections_and_retains_actions(self):
        result=self.overview(current=True)
        from django.test import RequestFactory
        request=RequestFactory().get('/portal/properties/1/');request.user=self.staff;request.resolver_match=SimpleNamespace(url_name='property_detail')
        html=render_to_string('portal/property_detail.html',{'request':request,'property':self.property,'overview':result,'current_leases':[self.lease],'units':[self.unit],'unit_rows':[{'unit':self.unit,'current_lease':self.lease}],'open_maintenance_count':0})
        self.assertIn('Property Management Status',html);self.assertIn('Cash &amp; Banking',html)
        self.assertNotIn('More Details',html);self.assertNotIn('Work Orders &amp; Costs',html)
        self.assertNotIn('Independently rentable units',html)
        self.assertIn(reverse('portal:edit_property_unit',args=[self.property.pk,self.unit.pk]),html)
        self.assertIn('property360-overview',html)

    def test_seed_preserves_custom_labels_and_no_business_records(self):
        from common.models import FormFieldSetting
        row=FormFieldSetting.objects.get(form_key='property_overview',field_key='ui')
        row.option_labels['cash_banking']='Property funds';row.save()
        call_command('seed_property_overview',verbosity=0)
        row.refresh_from_db();self.assertEqual(row.option_labels['cash_banking'],'Property funds')
        self.config.refresh_from_db();self.assertIsNone(self.config.operating_bank_id)

    def test_executed_extension_supplies_current_rent_and_expiration(self):
        from leasing.models import LeaseAgreement
        LeaseAgreement.objects.create(lease=self.lease,title='Executed continuation',status='executed',effective_date=self.today-timedelta(days=1),expiration_date=self.today+timedelta(days=700),rent_action='changed',monthly_rent=Decimal('2500'),recorded_by=self.staff)
        self.overview(current=True)
        self.assertEqual(self.lease.overview_terms['monthly_rent'],2500)
        self.assertEqual(self.lease.overview_terms['expiration_date'],self.today+timedelta(days=700))

    def test_actual_property_view_counts_one_request_once_after_conversion(self):
        import ast
        from pathlib import Path
        from unittest.mock import Mock
        from django.test import RequestFactory
        from django.shortcuts import get_object_or_404
        from common.audit.models import AuditEvent
        from properties.models import Property
        from leasing.models import Lease
        request=MaintenanceRequest.objects.create(unit=self.unit,title='Converted repair',description='Repair',status='converted')
        WorkOrder.objects.create(unit=self.unit,title='First task',description='Repair',maintenance_request=request,status='assigned')
        WorkOrder.objects.create(unit=self.unit,title='Previous task',description='Repair',maintenance_request=request,status='cancelled')
        WorkOrder.objects.create(unit=self.unit,title='Independent task',description='Repair',status='assigned')
        path=Path(__file__).with_name('views.py')
        node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='property_detail')
        node.decorator_list=[]
        renderer=Mock(return_value='rendered')
        namespace={'__package__':'portal','get_object_or_404':get_object_or_404,'Property':Property,'Lease':Lease,'MaintenanceRequest':MaintenanceRequest,'WorkOrder':WorkOrder,'AuditEvent':AuditEvent,'timezone':timezone,'_prepare_audit_events':list,'render':renderer}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
        http=RequestFactory().get('/property/');http.user=self.staff
        self.assertEqual(namespace['property_detail'](http,self.property.pk),'rendered')
        context=renderer.call_args.args[2]
        self.assertEqual(context['open_maintenance_count'],2)
        self.assertEqual(context['overview']['current_count'],1)
        self.assertNotIn('property_profile_sections',context)
