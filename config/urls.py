# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/",    admin.site.urls),
    path("portal/",   include(("portal.urls", "portal"), namespace="portal")),
    path("",          include("pages.urls")),
    path("listings/", include(("listings.urls", "listings"), namespace="listings")),
    path("rentals/",  include("rentals.urls")),
    path("leads/",    include("leads.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
