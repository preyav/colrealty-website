# pages/urls.py
from django.urls import path
from . import views
from .views import health

urlpatterns = [
    path("", views.home, name="home"),
    path("contact/", views.contact, name="contact"),
    path("health/", health, name="health"),
]
