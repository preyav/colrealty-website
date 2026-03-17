from django.urls import path
from . import views

app_name = "ai_concierge"

urlpatterns = [
    path("demo/", views.concierge_widget_page, name="demo"),
    path("chat/", views.ai_chat, name="chat"),
    path("profile/", views.get_profile, name="profile"),
]
