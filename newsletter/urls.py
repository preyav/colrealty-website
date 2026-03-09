from django.urls import path
from . import views

app_name = "newsletter"

urlpatterns = [
    path("", views.newsletter_archive, name="newsletter_archive"),
    path("issue/<slug:slug>/", views.newsletter_detail, name="newsletter_detail"),
    path("subscribe/", views.subscribe, name="newsletter_subscribe"),
    path("latest/", views.newsletter_latest, name="newsletter_latest"),
]
