from django.urls import path
from .views import create_lead

app_name = "leads"

urlpatterns = [
    path("create/", create_lead, name="create"),
]
