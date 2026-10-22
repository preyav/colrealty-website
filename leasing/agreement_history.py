"""Read model for the original agreement and subsequent explicit changes."""
from django.utils import timezone

def agreement_history(lease, as_of=None):
    as_of=as_of or timezone.localdate()
    agreements=list(lease.agreements.all())
    current={'expiration_date':lease.end_date,'monthly_rent':lease.monthly_rent,
             'rent_source':'Original lease','expiration_source':'Original lease'}
    items=[]
    for agreement in agreements:
        applicable=agreement.status=='executed' and agreement.effective_date<=as_of and (not agreement.signed_date or agreement.signed_date<=as_of)
        if applicable:
            if agreement.expiration_date:
                current.update(expiration_date=agreement.expiration_date,expiration_source=agreement.title)
            if agreement.rent_action=='changed':
                current.update(monthly_rent=agreement.monthly_rent,rent_source=agreement.title)
        # Record the accumulated terms at this point without applying unsigned fallback notices.
        items.append({'agreement':agreement,'applicable':applicable})
    reviews=any(a.review_notes or (a.signed_date and a.return_deadline and a.signed_date>a.return_deadline) for a in agreements if a.status=='executed')
    return {'lease':lease,'history_items':items,'recorded_terms':current,'history_review':reviews}
