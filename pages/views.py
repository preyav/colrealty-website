# pages/views.py
from django.shortcuts import render
from django.http import JsonResponse


def home(request):
    # Adjust template path if yours is different
    return render(request, "pages/home.html")


def contact(request):
    # Adjust template path if yours is different
    return render(request, "pages/contact.html")

def health(request):
    return JsonResponse({"status": "ok"})