from dataclasses import dataclass
from datetime import timedelta
from django.db.models import Avg, Count
from django.utils import timezone
from django.core.cache import cache

# Update import path to your actual Listing model:
from listings.models import Listing

@dataclass
class MarketStats:
    median_price: float | None
    avg_dom: float | None
    active_count: int
    sold_30d_count: int

def _median(values):
    vals = sorted([v for v in values if v is not None])
    if not vals:
        return None
    n = len(vals)
    mid = n // 2
    return float(vals[mid]) if n % 2 else float((vals[mid - 1] + vals[mid]) / 2)

def get_market_stats(city: str | None = None) -> MarketStats:
    """
    Pulls stats for ACTIVE and SOLD in last 30 days. Cached 6 hours.
    """
    cache_key = f"mls_stats:{city or 'all'}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    qs = Listing.objects.all()

    if city:
        qs = qs.filter(city__iexact=city)

    active_qs = qs.filter(status__iexact="active")
    sold_since = timezone.now().date() - timedelta(days=30)
    sold_qs = qs.filter(status__iexact="sold", sold_date__gte=sold_since)

    # Median price for active listings (often what buyers care about)
    prices = list(active_qs.values_list("price", flat=True)[:5000])
    median_price = _median(prices)

    # Average DOM (use stored field if you have it)
    avg_dom = active_qs.aggregate(v=Avg("days_on_market"))["v"]

    active_count = active_qs.aggregate(c=Count("id"))["c"]
    sold_30d_count = sold_qs.aggregate(c=Count("id"))["c"]

    stats = MarketStats(
        median_price=median_price,
        avg_dom=float(avg_dom) if avg_dom is not None else None,
        active_count=active_count or 0,
        sold_30d_count=sold_30d_count or 0,
    )

    cache.set(cache_key, stats, 60 * 60 * 6)  # 6 hours
    return stats