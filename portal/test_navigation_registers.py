from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase,Client
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from common.models import FormFieldSetting
from common.audit.models import AuditEvent
from properties.models import Property,PropertyUnit
from maintenance.models import PropertyInspection,PropertyAsset
from portal.property_registers import InspectionForm,AssetForm
from accounting.test_rent_phase1 import RentPhase1Tests
from accounting.rent_models import RentCharge,RentReceipt


class NavigationRegisterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        RentPhase1Tests.setUpTestData.__func__(cls)
        for cmd in ['seed_accounting_workspace','seed_chart_account_details','seed_chart_account_actions','seed_portal_settings','seed_portal_navigation']:
            call_command(cmd,verbosity=0)
        cls.unit=cls.lease.unit
        cls.admin=get_user_model().objects.create_superuser(username='register_admin',email='register@example.test',password='ExampleRegisterPassword2026')
        cls.other=Property.objects.create(street_address='Other property',city='Austin',state='TX',zip_code='78701',county='Travis',subdivision='Test',property_type='single_family')
        cls.other_unit=PropertyUnit.objects.create(property=cls.other,unit_number='2')

    def setUp(self):self.client.force_login(self.admin)
    def url(self,kind='inspections',pk=None):
        return reverse('portal:property_register_edit',args=[kind,pk]) if pk else reverse('portal:property_register',args=[kind])
    def data(self,kind='inspections',version=None,**changes):
        data={'property':str(self.unit.property_id),'unit':str(self.unit.pk),'title':'Routine review','status':'scheduled','inspection_type':'routine','scheduled_on':str(timezone.localdate()),'version':version or ''}
        if kind=='assets':data={'property':str(self.unit.property_id),'unit':str(self.unit.pk),'title':'Water heater','status':'in_service','quantity':1,'version':version or ''}
        data.update(changes);return data

    def test_flyout_links_and_renamed_leasing(self):
        response=self.client.get(self.url())
        self.assertContains(response,'id="rentals-popout"')
        self.assertContains(response,'id="maintenance-popout"')
        for name in ['properties','leases','tenants','owners','vendors','work_orders','outstanding_balances']:
            self.assertContains(response,reverse('portal:'+name))
        self.assertContains(response,'Leasing')
        self.assertNotContains(response,'Property editor sections')

    def test_labels_are_editable_and_seed_preserves_changes(self):
        row=FormFieldSetting.objects.get(form_key='portal_navigation',field_key='ui');row.option_labels['assets']='Equipment register';row.save()
        call_command('seed_portal_navigation',verbosity=0)
        self.assertContains(self.client.get(self.url('assets')),'Equipment register')

    def test_inspection_create_edit_audited_and_stale_rejected(self):
        response=self.client.get(self.url()+'?add=1');token=response.context['version']
        response=self.client.post(self.url()+'?add=1',self.data(version=token))
        self.assertEqual(response.status_code,302)
        obj=PropertyInspection.objects.get();url=self.url(pk=obj.pk)
        response=self.client.get(url);token=response.context['version']
        response=self.client.post(url,self.data(version=token,title='Updated inspection'))
        self.assertEqual(response.status_code,302)
        response=self.client.post(url,self.data(version=token,title='Stale edit'))
        self.assertContains(response,'This record changed.')
        obj.refresh_from_db();self.assertEqual(obj.title,'Updated inspection')
        self.assertEqual(AuditEvent.objects.filter(action='PROPERTY_REGISTER_SAVED').count(),2)

    def test_completed_inspection_requires_actual_date_and_unit_matches_property(self):
        form=InspectionForm(self.data(status='completed',unit=self.other_unit.pk))
        self.assertFalse(form.is_valid());self.assertIn('unit',form.errors);self.assertIn('completed_on',form.errors)

    def test_asset_create_and_invalid_quantity_or_unsafe_link(self):
        response=self.client.get(self.url('assets')+'?add=1')
        response=self.client.post(self.url('assets')+'?add=1',self.data('assets',response.context['version'],serial_number='TEST-100'))
        self.assertEqual(response.status_code,302);self.assertEqual(PropertyAsset.objects.get().serial_number,'TEST-100')
        form=AssetForm(self.data('assets',quantity=0,document_link='javascript:alert(1)'))
        self.assertFalse(form.is_valid());self.assertIn('quantity',form.errors);self.assertIn('document_link',form.errors)

    def test_unit_endpoint_limits_options_to_property_and_filters_work(self):
        response=self.client.get(self.url(),{'units_for':self.unit.property_id})
        self.assertIn(self.unit.pk,[r['id'] for r in response.json()['units']])
        self.assertNotIn(self.other_unit.pk,[r['id'] for r in response.json()['units']])
        PropertyAsset.objects.create(property=self.unit.property,title='Boiler',status='in_service',created_by=self.admin)
        PropertyAsset.objects.create(property=self.other,title='Fan',status='retired',created_by=self.admin)
        response=self.client.get(self.url('assets'),{'property':self.unit.property_id,'status':'in_service','q':'Boiler'})
        self.assertEqual(len(response.context['rows']),1)

    def test_access_csrf_and_invalid_kind(self):
        self.client.force_login(self.actor)
        self.assertEqual(self.client.get(self.url()).status_code,403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url('unknown')).status_code,404)
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post(self.url()+'?add=1',{}).status_code,403)

    def test_audit_failure_rolls_back_save(self):
        token=self.client.get(self.url('assets')+'?add=1').context['version']
        with patch('portal.property_registers.record_event',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):self.client.post(self.url('assets')+'?add=1',self.data('assets',token))
        self.assertFalse(PropertyAsset.objects.exists())

    def test_outstanding_separates_future_charges_and_credit(self):
        today=timezone.localdate()
        for day,amount in [(today-timedelta(days=3),'2400'),(today+timedelta(days=30),'2400')]:
            RentCharge.objects.create(lease=self.lease,period_start=day,period_end=day,due_date=day,amount=amount,created_by=self.admin)
        RentReceipt.objects.create(lease=self.lease,received_date=today,amount='2500',payment_method='check',created_by=self.admin)
        response=self.client.get(reverse('portal:outstanding_balances'))
        self.assertEqual(response.status_code,200)
        row=response.context['rows'][0]
        self.assertEqual(row['due'],2400);self.assertEqual(row['future'],2400);self.assertEqual(row['credit'],2500);self.assertEqual(row['net'],0)
        self.assertEqual(RentCharge.objects.count(),2)

    def test_view_only_staff_can_read_details_but_cannot_edit(self):
        from django.contrib.auth.models import Permission
        obj=PropertyAsset.objects.create(property=self.unit.property,title='Readable asset',status='in_service',notes='Warranty details',created_by=self.admin)
        self.actor.user_permissions.add(Permission.objects.get(codename='view_propertyasset'))
        self.client.force_login(self.actor)
        response=self.client.get(self.url('assets',obj.pk))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Warranty details')
        self.assertTrue(response.context['form'].fields['title'].disabled)
        self.assertEqual(self.client.post(self.url('assets',obj.pk),{}).status_code,403)

    def test_blank_quantity_reports_validation_error(self):
        form=AssetForm(self.data('assets',quantity=''))
        self.assertFalse(form.is_valid());self.assertIn('quantity',form.errors)
