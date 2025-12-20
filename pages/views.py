from django.views.generic import TemplateView
from listings.models import Listing

class HomePageView(TemplateView):
    template_name = "pages/home.html"

class BuyPageView(TemplateView):
    template_name = "pages/buy.html"

class ContactPageView(TemplateView):
    template_name = "pages/contact.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["featured_listings"] = Listing.objects.filter(
            is_featured=True, status="active"
        )[:6]
        return context
