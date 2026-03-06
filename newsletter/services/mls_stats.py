from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from django.db.models import Avg, Count, F
from django.utils import timezone
from django.core.cache import cache

from listings.models import Listing


@dataclass
class MarketStats:
    median_price_active: float | None
    avg_dom_active: float | None
    active_count: int
    new_30d_count: int
    sold_30d_count: int
    median_ppsf_active: float | None


def _median_decimal(values):
    vals = sorted([v for v in values if v is not None])
    if not vals:
        return None
    n = len(vals)
    mid = n // 2
    if n % 2 == 1:
        return float(vals[mid])
    return float((vals[mid - 1] + vals[mid]) / 2)


def get_market_stats(city=None):
    cache_key = f"mls_stats:v3:{(city or 'all').lower()}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    qs = Listing.objects.all()
    if city:
        qs = qs.filter(city__iexact=city)

    active_qs = qs.filter(status__iexact="active")
    since_30 = timezone.now() - timedelta(days=30)

    new_30d_qs = qs.filter(created_at__gte=since_30)

    # Your model does NOT have sold_date, so use updated_at as fallback
    sold_qs = qs.filter(status__iexact="sold", updated_at__gte=since_30)

    active_prices = list(active_qs.values_list("price", flat=True)[:10000])
    median_price_active = _median_decimal(active_prices)

    avg_dom_active = active_qs.aggregate(v=Avg("days_on_market"))["v"]
    avg_dom_active = float(avg_dom_active) if avg_dom_active is not None else None

    active_count = active_qs.aggregate(c=Count("id"))["c"] or 0
    new_30d_count = new_30d_qs.aggregate(c=Count("id"))["c"] or 0
    sold_30d_count = sold_qs.aggregate(c=Count("id"))["c"] or 0

    ppsf_qs = active_qs.filter(sqft__gt=0).annotate(ppsf=F("price") / F("sqft"))
    ppsf_vals = list(ppsf_qs.values_list("ppsf", flat=True)[:10000])
    median_ppsf_active = _median_decimal(ppsf_vals)

    stats = MarketStats(
        median_price_active=median_price_active,
        avg_dom_active=avg_dom_active,
        active_count=active_count,
        new_30d_count=new_30d_count,
        sold_30d_count=sold_30d_count,
        median_ppsf_active=median_ppsf_active,
    )

    cache.set(cache_key, stats, 60 * 60 * 6)
    return stats