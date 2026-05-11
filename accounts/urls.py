from django.urls import path
from . import views

app_name = "accounts"
urlpatterns = [
    path("overview/", views.overview, name="overview"),
    path("favorites/", views.favorites, name="favorites"),
    path("save-search/", views.save_search, name="save_search"),
    path("saved-searches/", views.saved_searches, name="saved_searches"),
    path("saved-searches/<int:pk>/", views.saved_search_detail, name="saved_search_detail"),
    path("saved-searches/<int:pk>/delete/", views.delete_saved_search, name="delete_saved_search"),
    path("saved-searches/listing-preview/<int:pk>/", views.saved_search_listing_preview, name="saved_search_listing_preview"),
    path("settings/", views.account_settings, name="settings"),
    path("select-type/", views.select_user_type, name="select_type"),
    path("sign-out/", views.sign_out, name="sign_out"),
    path("favorite/<int:listing_id>/", views.toggle_favorite, name="toggle_favorite"),
]