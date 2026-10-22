"""Bill payees are independent of work-order contractor assignments."""
from django.db.models import Q
from vendors.models import Vendor


def invoice_payees(current_vendor_id=None):
    criteria=Q(status='active')
    if current_vendor_id is not None:
        criteria |= Q(pk=current_vendor_id)
    return Vendor.objects.filter(criteria).order_by('company_name','name','pk')
