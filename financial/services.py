from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string


PROVIDERS = {
    "disabled": "financial.providers.disabled.DisabledFinancialProvider",
    "col360": "financial.providers.col360.COL360FinancialProvider",
    "quickbooks": "financial.providers.quickbooks.QuickBooksFinancialProvider",
}


@lru_cache(maxsize=1)
def get_financial_provider():
    key = str(getattr(settings, "COL360_FINANCIAL_PROVIDER", "disabled")).strip().lower()
    provider_path = PROVIDERS.get(key)
    if not provider_path:
        valid = ", ".join(sorted(PROVIDERS))
        raise ImproperlyConfigured(
            f"Unknown COL360_FINANCIAL_PROVIDER '{key}'. Valid providers: {valid}."
        )
    return import_string(provider_path)()


def get_work_order_financials(work_order):
    return get_financial_provider().work_order_summary(work_order)
