from .base import BaseFinancialProvider


class DisabledFinancialProvider(BaseFinancialProvider):
    key = "disabled"
    label = "Financials Disabled"
    enabled = False
