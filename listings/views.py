import re
from decimal import Decimal, InvalidOperation
from django.db.models import Q
from django.views.generic import ListView, DetailView

from .models import Listing


class ListingListView(ListView):
    model = Listing
    template_name = "listings/list.html"
    context_object_name = "listings"
    paginate_by = 21

    def get_queryset(self):
        qs = Listing.objects.all()

        # Base filters: Active + Residential (adjust if your MLS uses different wording)
        qs = qs.filter(status="active").filter(
            property_type__iexact="Residential")

        # Single search field (q) across city / zip / street / title / description
        q = (self.request.GET.get("q") or "").strip()

        # Price filters (match your template field names)
        price_min = (self.request.GET.get("price_min") or "").strip()
        price_max = (self.request.GET.get("price_max") or "").strip()

        if q:
            q_zip = re.sub(r"\D", "", q)  # digits only
            qs = qs.filter(
                Q(city__icontains=q)
                | Q(zip_code__icontains=q_zip if q_zip else q)
                | Q(street_address__icontains=q)
                | Q(title__icontains=q)
                | Q(description__icontains=q)
            )

        def to_decimal(val: str):
            try:
                cleaned = val.replace(",", "").replace("$", "").strip()
                return Decimal(cleaned) if cleaned else None
            except (InvalidOperation, AttributeError):
                return None

        min_v = to_decimal(price_min)
        max_v = to_decimal(price_max)

        if min_v is not None:
            qs = qs.filter(price__gte=min_v)
        if max_v is not None:
            qs = qs.filter(price__lte=max_v)

        return qs.order_by("-created_at")


class ListingDetailView(DetailView):
    model = Listing
    template_name = "listings/detail.html"
    context_object_name = "listing"
