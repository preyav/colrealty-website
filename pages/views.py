# pages/views.py
from datetime import timedelta
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth.views import LoginView
from listings.models import Listing

class ColRealtyLoginView(LoginView):
    template_name = 'pages/login.html'
    # Redirect to homepage or a specific dashboard after login
    next_page = 'index'

def home(request):
    qs = Listing.objects.all().order_by("-id")

    paginator = Paginator(qs, 12)  # 12 listings per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "listings": page_obj,              # important: template loops over listings
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
    }
    return render(request, "pages/home.html", context)

# BUY pages
def contact(request):
    return render(request, "pages/contact.html")


# BUY pages
def buy(request):
    return render(request, "pages/buy.html")  

def buy_map(request):
    return render(request, "pages/buy/map.html")


def buy_neighborhoods(request):
    return render(request, "pages/buy/neighborhoods.html")


def buy_off_market(request):
    return render(request, "pages/buy/off_market.html")


# SELL pages
def sell(request):
    return render(request, "pages/sell.html")  

def sell_valuation(request):
    return render(request, "pages/sell/valuation.html")


def sell_marketing(request):
    return render(request, "pages/sell/marketing.html")


def sell_concierge(request):
    return render(request, "pages/sell/concierge.html")


# RENT
def rent(request):
    return render(request, "pages/rent.html")

def rent_marketing(request):
    return render(request, "pages/rent/marketing.html")

# PROPERTY MANAGEMENT
def propman(request):
    return render(request, "pages/propman.html")

# CONTACT
def contact(request):
    return render(request, "pages/contact.html")


# CUSTOM LOGIN placeholders
def login(request):
    return render(request, "pages/login.html")


def health(request):
    return JsonResponse({"status": "ok"})
