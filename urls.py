from django.urls import path, include

urlpatterns = [
    path("", include("apps.listings.urls", namespace="listings")),
]
