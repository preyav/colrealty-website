# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("allauth.urls")),
    path("admin/",    admin.site.urls),
    path("portal/",   include(("portal.urls", "portal"), namespace="portal")),
    path("",          include("pages.urls")),
    path("listings/", include(("listings.urls", "listings"), namespace="listings")),
    path("rentals/",  include("rentals.urls")),
    path("leads/",    include("leads.urls")),
    path('newsletter/', include('newsletter.urls', namespace='newsletter')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
