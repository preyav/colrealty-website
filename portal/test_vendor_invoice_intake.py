from unittest.mock import patch
from django.test import TestCase, RequestFactory
from accounting import test_general_ledger as fixtures
from maintenance.models import WorkOrder, VendorInvoice
from owners.models import OwnerProfile
from tenants.models import TenantProfile
from vendors.models import Vendor
from portal.views import finance_vendor_invoices


class VendorInvoiceIntakeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        fixtures.GeneralLedgerTests.setUpTestData.__func__(cls)
        cls.tenant = TenantProfile.objects.create(first_name='Intake', last_name='Tenant')
        cls.owner = OwnerProfile.objects.create(first_name='Intake', last_name='Owner')
        cls.vendor = Vendor.objects.create(name='Intake vendor')

    def work(self, **changes):
        return WorkOrder.objects.create(unit=self.unit, title='Intake test', description='Test work', status=changes.pop('status', 'completed'), **changes)

    def intake_ids(self):
        request = RequestFactory().get('/portal/finance/vendor-bills/')
        request.user = self.staff
        with patch('portal.views.render') as render:
            finance_vendor_invoices(request)
        return set(render.call_args.args[2]['ready_to_bill'].values_list('pk', flat=True))

    def test_completed_vendor_work_is_available(self):
        work = self.work()
        self.assertIn(work.pk, self.intake_ids())

    def test_tenant_work_is_excluded(self):
        work = self.work(performer_tenant=self.tenant)
        self.assertNotIn(work.pk, self.intake_ids())
        work.refresh_from_db()
        self.assertEqual(work.performer_tenant_id, self.tenant.pk)

    def test_owner_work_is_excluded(self):
        work = self.work(performer_owner=self.owner)
        self.assertNotIn(work.pk, self.intake_ids())

    def test_unfinished_vendor_work_is_excluded(self):
        for status in ['new', 'assigned', 'scheduled', 'in_progress', 'cancelled']:
            with self.subTest(status=status):
                self.assertNotIn(self.work(status=status).pk, self.intake_ids())

    def test_current_invoice_excludes_work_and_void_allows_intake(self):
        for status in ['submitted', 'approved', 'partially_paid', 'paid', 'disputed', 'void']:
            with self.subTest(status=status):
                work = self.work()
                VendorInvoice.objects.create(work_order=work, vendor=self.vendor, amount='10', status=status)
                self.assertEqual(work.pk in self.intake_ids(), status == 'void')
