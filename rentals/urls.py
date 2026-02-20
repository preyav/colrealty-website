from django.urls import path
from . import views

app_name = "rentals"

urlpatterns = [
    path("markers/", views.rental_markers, name="markers"),
    path("", views.rental_list, name="list"),
    path("<int:pk>/", views.rental_detail, name="detail"),
]
