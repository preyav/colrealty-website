from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import Listing

class ListingListView(ListView):
    model = Listing
    template_name = "listings/list.html"
    context_object_name = "listings"
    paginate_by = 12

    def get_queryset(self):
        qs = Listing.objects.filter(status="active")
        q = self.request.GET.get("q")
        min_price = self.request.GET.get("min_price")
        max_price = self.request.GET.get("max_price")
        beds = self.request.GET.get("beds")

        if q:
            qs = qs.filter(
                Q(city__icontains=q) |
                Q(zip_code__icontains=q) |
                Q(street_address__icontains=q)
            )
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)
        if beds:
            qs = qs.filter(beds__gte=beds)

        return qs.filter(property_type__iexact="Residential")

class ListingDetailView(DetailView):
    model = Listing
    template_name = "listings/detail.html"
    context_object_name = "listing"

