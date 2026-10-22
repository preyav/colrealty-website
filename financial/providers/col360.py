from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from maintenance.models import VendorInvoice, VendorPayment
from portal.forms import VendorInvoiceForm, VendorPaymentForm

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
            VendorInvoice.objects.filter(work_order=work_order).exclude(status="void")
            .select_related("vendor", "approved_by")
            .prefetch_related("payments__recorded_by", "payments__voided_by")
            .order_by("-created_at")
        )
        invoice_totals = VendorInvoice.objects.filter(work_order=work_order).exclude(
            status="void"
        ).aggregate(total_invoiced=Sum("amount"))
        payment_totals = VendorPayment.objects.filter(
            invoice__work_order=work_order,
            invoice__status__in=["approved", "partially_paid", "paid"],
            status="recorded",
        ).aggregate(total_paid=Sum("amount"))
        total_invoiced = invoice_totals["total_invoiced"] or Decimal("0.00")
        total_paid = payment_totals["total_paid"] or Decimal("0.00")
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

    def get_invoice_form(
        self,
        data=None,
        *,
        vendor_queryset=None,
        initial=None,
        instance=None,
    ):
        form = VendorInvoiceForm(data, initial=initial, instance=instance)
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

    def update_invoice(self, form, *, invoice):
        if invoice.status != "submitted":
            raise FinancialProviderError("Only a submitted invoice can be edited.")
        if not form.is_valid():
            raise FinancialProviderError("Invoice form is not valid.")
        updated_invoice = form.save(commit=False)
        updated_invoice.work_order = invoice.work_order
        updated_invoice.status = "submitted"
        updated_invoice.save()
        return updated_invoice

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

    def get_payment_form(self, data=None, *, invoice, initial=None):
        return VendorPaymentForm(data, invoice=invoice, initial=initial)

    def record_payment(self, form, *, invoice, actor):
        if not form.is_valid():
            raise FinancialProviderError("Payment form is not valid.")
        with transaction.atomic():
            locked_invoice = VendorInvoice.objects.select_for_update().get(pk=invoice.pk)
            if locked_invoice.status not in {"approved", "partially_paid"}:
                raise FinancialProviderError(
                    "Payments can only be recorded against an approved invoice with a balance due."
                )
            paid = locked_invoice.payments.filter(status="recorded").aggregate(
                total=Sum("amount")
            )["total"] or Decimal("0.00")
            amount = form.cleaned_data["amount"]
            outstanding = locked_invoice.amount - paid
            if amount > outstanding:
                raise FinancialProviderError(
                    f"Payment cannot exceed the outstanding balance of ${outstanding:.2f}."
                )
            payment = form.save(commit=False)
            payment.invoice = locked_invoice
            payment.recorded_by = actor
            payment.status = "recorded"
            payment.save()
            new_paid = paid + amount
            if new_paid == locked_invoice.amount:
                locked_invoice.status = "paid"
                locked_invoice.paid_at = timezone.now()
            else:
                locked_invoice.status = "partially_paid"
                locked_invoice.paid_at = None
            locked_invoice.save(update_fields=["status", "paid_at", "updated_at"])
        return payment, locked_invoice

    def void_payment(self, payment, *, actor, reason):
        reason = (reason or "").strip()
        if not reason:
            raise FinancialProviderError("A reason is required to void a payment.")
        from accounting.reimbursement_models import OnBehalfSettlement
        from accounting.book_models import BookPosting
        if OnBehalfSettlement.objects.filter(payment=payment).exists() or BookPosting.objects.filter(source_key='bill-payment:'+str(payment.pk)).exists():
            from accounting.book_services import void_bill_payment
            from django.core.exceptions import ValidationError
            try:
                result = void_bill_payment(payment, reason, actor)
            except ValidationError as exc:
                raise FinancialProviderError('; '.join(exc.messages)) from exc
            return result, result.invoice
        with transaction.atomic():
            payment = VendorPayment.objects.select_for_update().select_related(
                "invoice"
            ).get(pk=payment.pk)
            if payment.status == "void":
                raise FinancialProviderError("This payment is already void.")
            invoice = VendorInvoice.objects.select_for_update().get(pk=payment.invoice_id)
            payment.status = "void"
            payment.voided_by = actor
            payment.voided_at = timezone.now()
            payment.void_reason = reason
            payment.save(
                update_fields=["status", "voided_by", "voided_at", "void_reason"]
            )
            paid = invoice.payments.filter(status="recorded").aggregate(
                total=Sum("amount")
            )["total"] or Decimal("0.00")
            invoice.status = "partially_paid" if paid > 0 else "approved"
            invoice.paid_at = None
            invoice.save(update_fields=["status", "paid_at", "updated_at"])
        return payment, invoice

    def get_payment(self, payment_id):
        try:
            return VendorPayment.objects.select_related(
                "invoice__work_order", "invoice__vendor"
            ).get(pk=payment_id)
        except VendorPayment.DoesNotExist as exc:
            raise FinancialProviderError("Payment not found.") from exc
