from django.test import TestCase
from vendors.models import Vendor
from portal.invoice_payees import invoice_payees

class InvoicePayeeTests(TestCase):
    def test_active_payee_does_not_require_contractor_assignment(self):
        contractor=Vendor.objects.create(name='Contractor',status='active')
        payee=Vendor.objects.create(name='Warranty provider',status='active')
        inactive=Vendor.objects.create(name='Inactive',status='inactive')
        self.assertSetEqual(set(invoice_payees(contractor.pk).values_list('pk',flat=True)),{contractor.pk,payee.pk})
        self.assertFalse(invoice_payees().filter(pk=inactive.pk).exists())
    def test_existing_inactive_payee_is_preserved(self):
        current=Vendor.objects.create(name='Existing payee',status='inactive')
        other=Vendor.objects.create(name='Other inactive',status='inactive')
        self.assertTrue(invoice_payees(current.pk).filter(pk=current.pk).exists())
        self.assertFalse(invoice_payees(current.pk).filter(pk=other.pk).exists())
