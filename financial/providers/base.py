from abc import ABC, abstractmethod
from decimal import Decimal


class FinancialProviderError(Exception):
    """Base exception for financial provider operations."""


class FinancialProviderDisabled(FinancialProviderError):
    """Raised when an accounting action is requested while financials are disabled."""


class BaseFinancialProvider(ABC):
    key = "base"
    label = "Financial Provider"
    enabled = False

    def capabilities(self):
        return {
            "enabled": self.enabled,
            "can_view_invoices": False,
            "can_add_invoice": False,
            "can_approve_invoice": False,
            "can_record_payment": False,
        }

    def work_order_summary(self, work_order):
        return {
            "provider": self.key,
            "provider_label": self.label,
            "enabled": self.enabled,
            "capabilities": self.capabilities(),
            "invoices": [],
            "total_invoiced": Decimal("0.00"),
            "total_paid": Decimal("0.00"),
            "outstanding": Decimal("0.00"),
        }

    def _disabled(self):
        raise FinancialProviderDisabled(
            f"{self.label} does not provide native invoice/payment actions."
        )

    def get_invoice_form(self, *args, **kwargs):
        self._disabled()

    def create_invoice(self, *args, **kwargs):
        self._disabled()

    def get_invoice(self, *args, **kwargs):
        self._disabled()

    def approve_invoice(self, *args, **kwargs):
        self._disabled()

    def mark_invoice_paid(self, *args, **kwargs):
        self._disabled()
