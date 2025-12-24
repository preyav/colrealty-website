# pages/views.py
from django.shortcuts import render


def home(request):
    # Adjust template path if yours is different
    return render(request, "pages/home.html")


def contact(request):
    # Adjust template path if yours is different
    return render(request, "pages/contact.html")
