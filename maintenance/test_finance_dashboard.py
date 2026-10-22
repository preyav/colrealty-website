from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from maintenance.models import (
    VendorAssignment,
    VendorInvoice,
    VendorPayment,
    WorkOrder,
)
from properties.models import Property, PropertyUnit
from vendors.models import Vendor


class FinanceDashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="finance_dashboard_manager",
            password="test-password",
            is_staff=True,
        )
        property_record = Property.objects.create(
            street_address="100 Finance Test Drive",
            city="Austin",
            state="TX",
            zip_code="78701",
            county="Travis",
            subdivision="Test",
            property_type="single_family_residential",
            management_status="active",
            is_multi_unit=False,
        )
        self.unit = PropertyUnit.objects.create(
            property=property_record,
            unit_number="",
        )
        self.vendor = Vendor.objects.create(
            name="Finance Vendor",
            company_name="Finance Vendor LLC",
            email="finance-vendor@example.com",
            status="active",
        )
        self.client.force_login(self.user)

    def create_work_order(self, **overrides):
        values = {
            "unit": self.unit,
            "title": "Repair plumbing",
            "description": "Repair the leak.",
            "status": "completed",
            "completed_at": timezone.now() - timedelta(days=3),
            "actual_cost": Decimal("250.00"),
        }
        values.update(overrides)
        return WorkOrder.objects.create(**values)

    def create_invoice(self, **overrides):
        work_order = overrides.pop("work_order", self.create_work_order())
        values = {
            "work_order": work_order,
            "vendor": self.vendor,
            "invoice_number": f"INV-{work_order.pk}",
            "amount": Decimal("250.00"),
            "status": "approved",
            "invoice_date": timezone.localdate(),
            "due_date": timezone.localdate() + timedelta(days=30),
        }
        values.update(overrides)
        return VendorInvoice.objects.create(**values)

    def test_dashboard_prioritizes_action_queues_and_recent_activity(self):
        ready_work_order = self.create_work_order(title="Awaiting vendor invoice")
        VendorAssignment.objects.create(
            work_order=ready_work_order,
            vendor=self.vendor,
            status="completed",
            completed_at=ready_work_order.completed_at,
        )
        submitted = self.create_invoice(status="submitted")
        overdue = self.create_invoice(
            status="partially_paid",
            amount=Decimal("300.00"),
            invoice_date=timezone.localdate() - timedelta(days=30),
            due_date=timezone.localdate() - timedelta(days=1),
        )
        VendorPayment.objects.create(
            invoice=overdue,
            amount=Decimal("100.00"),
            payment_date=timezone.localdate(),
            payment_method="ach",
            recorded_by=self.user,
        )

        response = self.client.get(reverse("portal:finance_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Completed Work Awaiting Invoice")
        self.assertContains(response, "Awaiting vendor invoice")
        self.assertContains(response, "Finance Vendor LLC")
        self.assertContains(response, "Bills Requiring Attention")
        self.assertContains(response, submitted.invoice_number)
        self.assertContains(response, "Overdue")
        self.assertContains(response, "Recent Bill Activity")
        self.assertEqual(response.context["attention_count"], 2)
        self.assertEqual(response.context["overdue_total"], Decimal("200.00"))

    def test_period_filter_is_validated_and_applied(self):
        current = self.create_invoice(amount=Decimal("100.00"))
        older = self.create_invoice(amount=Decimal("900.00"))
        older.invoice_date = timezone.localdate() - timedelta(days=400)
        older.save(update_fields=["invoice_date"])

        response = self.client.get(
            reverse("portal:finance_dashboard"),
            {"period": "year"},
        )
        self.assertEqual(response.context["billed_total"], current.amount)
        self.assertEqual(response.context["selected_period"], "year")

        response = self.client.get(
            reverse("portal:finance_dashboard"),
            {"period": "unsupported"},
        )
        self.assertEqual(response.context["selected_period"], "all")
        self.assertEqual(response.context["billed_total"], Decimal("1000.00"))

    def test_dashboard_requires_staff_access(self):
        self.user.is_staff = False
        self.user.save(update_fields=["is_staff"])

        response = self.client.get(reverse("portal:finance_dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_overdue_queue_is_visible_and_hides_invoice_intake(self):
        ready_work_order = self.create_work_order(title="Unrelated invoice intake")
        VendorAssignment.objects.create(
            work_order=ready_work_order,
            vendor=self.vendor,
            status="completed",
            completed_at=ready_work_order.completed_at,
        )
        overdue = self.create_invoice(
            status="partially_paid",
            invoice_date=timezone.localdate() - timedelta(days=30),
            due_date=timezone.localdate() - timedelta(days=1),
        )

        response = self.client.get(
            reverse("portal:finance_vendor_invoices"),
            {"queue": "overdue"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_queue"], "overdue")
        self.assertContains(response, "Overdue bills")
        self.assertContains(response, overdue.invoice_number)
        self.assertNotContains(response, "Ready for Invoice Intake")
        self.assertNotContains(response, "Unrelated invoice intake")
