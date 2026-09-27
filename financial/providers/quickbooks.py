from .base import BaseFinancialProvider, FinancialProviderError


class QuickBooksFinancialProvider(BaseFinancialProvider):
    """Safe placeholder for a future authenticated QuickBooks connector."""

    key = "quickbooks"
    label = "QuickBooks"
    enabled = False

    def _disabled(self):
        raise FinancialProviderError(
            "QuickBooks is selected but the connector has not been configured yet."
        )
