from django.urls import path
from . import views

app_name = "portal"

urlpatterns = [
    path("",                                    views.dashboard,           name="dashboard"),
    path("leads/",                              views.leads_list,          name="leads"),
    path("leads/retry-all/",                    views.leads_retry_all,     name="leads_retry_all"),
    path("leads/<int:lead_id>/retry/",          views.lead_retry_hubspot,  name="lead_retry"),
    path("listings/",                           views.listings_list,       name="listings"),
    path("listings/<int:listing_id>/featured/", views.toggle_featured,     name="toggle_featured"),
    path("rentals/",                            views.rentals_list,        name="rentals"),
]
