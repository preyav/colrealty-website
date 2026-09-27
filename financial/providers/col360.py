from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from maintenance.models import VendorInvoice
from portal.forms import VendorInvoiceForm

from .base import BaseFinancialProvider, FinancialProviderError


class COL360FinancialProvider(BaseFinancialProvider):
    """Native COL360 accounting provider using the existing VendorInvoice model."""

    key = "col360"
    label = "COL360 Financial"
    enabled = True

    def capabilities(self):
        return {
            "enabled": True,
            "can_view_invoices": True,
            "can_add_invoice": True,
            "can_approve_invoice": True,
            "can_record_payment": True,
        }

    def work_order_summary(self, work_order):
        invoices = list(
            VendorInvoice.objects.filter(work_order=work_order)
            .select_related("vendor", "approved_by")
            .order_by("-created_at")
        )
        totals = VendorInvoice.objects.filter(work_order=work_order).aggregate(
            total_invoiced=Sum("amount"),
            total_paid=Sum("amount", filter=Q(status="paid")),
        )
        total_invoiced = totals["total_invoiced"] or Decimal("0.00")
        total_paid = totals["total_paid"] or Decimal("0.00")
        summary = super().work_order_summary(work_order)
        summary.update({
            "enabled": True,
            "capabilities": self.capabilities(),
            "invoices": invoices,
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "outstanding": total_invoiced - total_paid,
        })
        return summary

    def get_invoice_form(self, data=None, *, vendor_queryset=None):
        form = VendorInvoiceForm(data)
        if vendor_queryset is not None:
            form.fields["vendor"].queryset = vendor_queryset
        return form

    def create_invoice(self, form, *, work_order):
        if not form.is_valid():
            raise FinancialProviderError("Invoice form is not valid.")
        invoice = form.save(commit=False)
        invoice.work_order = work_order
        invoice.status = "submitted"
        invoice.save()
        return invoice

    def get_invoice(self, invoice_id):
        try:
            return VendorInvoice.objects.select_related("work_order", "vendor").get(pk=invoice_id)
        except VendorInvoice.DoesNotExist as exc:
            raise FinancialProviderError("Invoice not found.") from exc

    def approve_invoice(self, invoice, *, actor):
        if invoice.status == "approved":
            return invoice, "already_approved"
        if invoice.status == "paid":
            return invoice, "already_paid"
        if invoice.status in {"void", "disputed"}:
            raise FinancialProviderError("A void or disputed invoice cannot be approved.")
        if invoice.status != "submitted":
            raise FinancialProviderError("Only submitted invoices can be approved.")
        with transaction.atomic():
            invoice.status = "approved"
            invoice.approved_by = actor
            invoice.approved_at = timezone.now()
            invoice.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return invoice, "approved"

    def mark_invoice_paid(self, invoice, *, actor=None):
        if invoice.status == "paid":
            return invoice, "already_paid"
        if invoice.status != "approved":
            raise FinancialProviderError("Only an approved invoice can be marked as paid.")
        with transaction.atomic():
            invoice.status = "paid"
            invoice.paid_at = timezone.now()
            invoice.save(update_fields=["status", "paid_at", "updated_at"])
        return invoice, "paid"
