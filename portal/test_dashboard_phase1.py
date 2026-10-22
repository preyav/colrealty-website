from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, RequestFactory
from django.utils import timezone
from common.models import FormFieldSetting
from leasing.models import Lease, LeaseAgreement
from maintenance.models import WorkOrder, VendorInvoice, VendorPayment
from properties.models import Property, PropertyUnit
from vendors.models import Vendor
from portal.dashboard_data import build_dashboard, current_terms


class DashboardPhase1Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_pm_dashboard', verbosity=0)
        call_command('seed_rent_ledger', verbosity=0)
        cls.user = get_user_model().objects.create(username='dashboard_test', is_staff=True)

    def setUp(self):
        self.today = timezone.localdate()
        self.request = RequestFactory().get('/portal/')
        self.request.user = self.user

    def portfolio(self):
        prop = Property.objects.create(street_address='Dashboard test property', management_status='active')
        unit = PropertyUnit.objects.create(property=prop, unit_number='1', status='occupied')
        return prop, unit

    def test_empty_dashboard_does_not_invent_occupancy_or_rent_balance(self):
        data = build_dashboard(self.request)
        self.assertEqual(len(data['cards']), 6)
        self.assertIsNone(data['occupancy_rate'])
        self.assertIn('rent_unavailable', data['ui'])

    def test_executed_extension_and_unchanged_rent_carry_forward(self):
        _, unit = self.portfolio()
        lease = Lease.objects.create(unit=unit, start_date=self.today-timedelta(days=400), end_date=self.today-timedelta(days=30), monthly_rent='2395', status='active')
        LeaseAgreement.objects.create(lease=lease, kind='extension', status='executed', title='Executed extension', effective_date=self.today-timedelta(days=60), signed_date=self.today-timedelta(days=60), expiration_date=self.today+timedelta(days=365), rent_action='changed', monthly_rent='2400', recorded_by=self.user)
        LeaseAgreement.objects.create(lease=lease, kind='extension', status='executed', title='Continuation', effective_date=self.today-timedelta(days=20), signed_date=self.today-timedelta(days=20), expiration_date=self.today+timedelta(days=730), rent_action='unchanged', recorded_by=self.user)
        LeaseAgreement.objects.create(lease=lease, kind='extension', status='draft', title='Draft', effective_date=self.today, expiration_date=self.today+timedelta(days=1095), rent_action='changed', monthly_rent='9999', recorded_by=self.user)
        terms = current_terms(lease, self.today)
        self.assertEqual(terms['monthly_rent'], Decimal('2400'))
        self.assertEqual(terms['expiration_date'], self.today+timedelta(days=730))
        data = build_dashboard(self.request)
        self.assertEqual(data['summary'][1]['value'], 1)
        self.assertEqual(data['cards'][2]['metrics'][0]['value'], 0)
        lease.refresh_from_db()
        self.assertEqual(lease.monthly_rent, Decimal('2395'))

    def test_expiration_window_boundary_is_inclusive(self):
        _, unit = self.portfolio()
        Lease.objects.create(unit=unit,start_date=self.today-timedelta(days=1),end_date=self.today+timedelta(days=30),monthly_rent='1000',status='active')
        self.assertEqual(build_dashboard(self.request)['cards'][2]['metrics'][0]['value'], 1)

    def test_vendor_balance_ignores_void_payments_and_invoices(self):
        _, unit = self.portfolio()
        order = WorkOrder.objects.create(unit=unit,title='Test repair',description='Scope')
        vendor = Vendor.objects.create(name='Test vendor')
        invoice = VendorInvoice.objects.create(work_order=order,vendor=vendor,amount='100',status='partially_paid')
        VendorPayment.objects.create(invoice=invoice,amount='30',payment_date=self.today,payment_method='check',status='recorded')
        VendorPayment.objects.create(invoice=invoice,amount='20',payment_date=self.today,payment_method='check',status='void')
        self.assertEqual(build_dashboard(self.request)['cards'][3]['metrics'][3]['value'], '$70.00')
        invoice.status='void';invoice.save(update_fields=['status'])
        self.assertEqual(build_dashboard(self.request)['cards'][3]['metrics'][3]['value'], '$0.00')

    def test_inactive_properties_are_outside_dashboard_portfolio(self):
        prop, _ = self.portfolio()
        prop.management_status='inactive';prop.save(update_fields=['management_status'])
        self.assertEqual(build_dashboard(self.request)['summary'][0]['value'], 0)

    def test_seed_preserves_custom_dashboard_wording(self):
        FormFieldSetting.objects.filter(form_key='pm_dashboard',field_key='attention').update(label='My priorities')
        call_command('seed_pm_dashboard', verbosity=0)
        call_command('seed_rent_ledger', verbosity=0)
        self.assertEqual(build_dashboard(self.request)['cards'][0]['title'], 'My priorities')
