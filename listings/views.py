from django.views.generic import ListView, DetailView
from django.db.models import Q
from .models import Listing

class ListingListView(ListView):
    model = Listing
    template_name = "listings/list.html"
    context_object_name = "listings"
    paginate_by = 21

    def get_queryset(self):
        # 1. Start with the base requirement: only active listings
        qs = Listing.objects.filter(status="active")
        
        # 2. Get the property type from the URL (e.g., ?property_type=Residential)
        # We use "Residential" as a default if nothing is provided
        p_type = self.request.GET.get("property_type", "Residential")
        
        # 3. Apply the filter based on the variable
        if p_type:
            qs = qs.filter(property_type=p_type)

<<<<<<< HEAD
        # 1) Base filter: Active + Residential
        qs = qs.filter(
            status__iexact="Active",
        )
=======
        # --- Your existing search logic ---
        q = self.request.GET.get("q")
        min_price = self.request.GET.get("min_price")
        max_price = self.request.GET.get("max_price")
        beds = self.request.GET.get("beds")
>>>>>>> 2c0d81a (Polish UI for listings and detail pages)

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

        return qs

class ListingDetailView(DetailView):
    model = Listing
    template_name = "listings/detail.html"
    context_object_name = "listing"

