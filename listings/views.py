from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import Listing

class ListingListView(ListView):
    model = Listing
    template_name = "listings/list.html"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()

        # 1) Base filter: Active + Residential
        qs = qs.filter(
            status__iexact="active",
            property_type__iexact="Residential",
        )

        # 2) Text filters
        city = (self.request.GET.get("city") or "").strip()
        zip_code = (self.request.GET.get("zip") or "").strip()
        neighborhood = (self.request.GET.get("neighborhood") or "").strip()

        if city:
            qs = qs.filter(city__iexact=city)

        if zip_code:
            qs = qs.filter(zip_code__iexact=zip_code)

        if neighborhood:
            # If you have a neighborhood field, use it; otherwise fallback to text search
            if any(f.name == "neighborhood" for f in Listing._meta.fields):
                qs = qs.filter(neighborhood__icontains=neighborhood)
            else:
                qs = qs.filter(
                    Q(street_address__icontains=neighborhood) |
                    Q(description__icontains=neighborhood) |
                    Q(city__icontains=neighborhood)
                )

        # 3) Price range filters (min/max optional)
        min_price_raw = (self.request.GET.get("min_price") or "").strip()
        max_price_raw = (self.request.GET.get("max_price") or "").strip()

        try:
            if min_price_raw:
                qs = qs.filter(price__gte=min_price_raw)
        except (ValueError, TypeError):
            pass

        try:
            if max_price_raw:
                qs = qs.filter(price__lte=max_price_raw)
        except (ValueError, TypeError):
            pass

        # 4) Sort newest first (or change to price, etc.)
        return qs.order_by("-created_at")

class ListingDetailView(DetailView):
    model = Listing
    template_name = "listings/detail.html"
    context_object_name = "listing"

