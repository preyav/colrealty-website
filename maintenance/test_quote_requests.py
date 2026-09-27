from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from maintenance.models import VendorAward, VendorAssignment, VendorEstimate, VendorQuoteRequest, WorkOrder
from portal.forms import VendorAssignmentForm, VendorEstimateForm
from properties.models import Property, PropertyUnit
from vendors.models import Vendor


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class VendorQuoteWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="quote_manager",
            password="test-password",
            is_staff=True,
        )
        self.property = Property.objects.create(
            street_address="500 Quote Lane",
            city="Austin",
            state="TX",
            zip_code="78705",
            county="Travis",
            subdivision="Test",
            property_type="single_family_residential",
            management_status="active",
            is_multi_unit=False,
        )
        self.unit = PropertyUnit.objects.create(property=self.property, unit_number="")
        self.work_order = WorkOrder.objects.create(
            unit=self.unit,
            title="Request plumbing quotes",
            description="Replace the leaking kitchen faucet.",
        )
        self.vendor = Vendor.objects.create(
            name="Taylor Plumber",
            company_name="Taylor Plumbing",
            email="quotes@example.com",
            status="active",
        )
        self.client.force_login(self.user)

    def base_quote_data(self, **overrides):
        data = {
            "vendor": self.vendor.pk,
            "entry_method": "total",
            "source": "phone",
            "amount": "425.00",
            "labor_amount": "",
            "materials_amount": "",
            "tax_amount": "",
            "other_fees": "",
            "discount_amount": "",
            "received_date": date(2026, 9, 24).isoformat(),
            "valid_through": "",
            "description": "Replace faucet and test for leaks.",
            "notes": "",
        }
        data.update(overrides)
        return data

    def test_total_only_quote_is_allowed(self):
        form = VendorEstimateForm(data=self.base_quote_data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["amount"], Decimal("425.00"))

    def test_itemized_quote_calculates_total_less_discount(self):
        form = VendorEstimateForm(data=self.base_quote_data(
            entry_method="itemized",
            amount="",
            labor_amount="250.00",
            materials_amount="100.00",
            tax_amount="20.00",
            other_fees="15.00",
            discount_amount="10.00",
        ))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["amount"], Decimal("375.00"))

    def test_quote_request_is_sent_and_tracked(self):
        response = self.client.post(
            reverse("portal:request_vendor_quotes", args=[self.work_order.pk]),
            {
                "vendors": [self.vendor.pk],
                "response_due": date(2026, 9, 27).isoformat(),
                "scope": self.work_order.description,
                "instructions": "Please separate labor and materials.",
            },
        )
        self.assertRedirects(
            response,
            reverse("portal:work_order_detail", args=[self.work_order.pk]),
        )
        quote_request = VendorQuoteRequest.objects.get()
        self.assertEqual(quote_request.status, "sent")
        self.assertEqual(quote_request.vendor, self.vendor)

    def test_recorded_quote_has_assignment_action_before_quote_request_action(self):
        quote_request = VendorQuoteRequest.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            status="sent",
            scope=self.work_order.description,
            requested_by=self.user,
        )
        estimate = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            quote_request=quote_request,
            amount=Decimal("425.00"),
            status="approved",
            source="email",
        )

        response = self.client.get(
            reverse("portal:work_order_detail", args=[self.work_order.pk])
        )

        self.assertContains(
            response,
            f"{reverse('portal:assign_vendor', args=[self.work_order.pk])}?estimate_id={estimate.pk}",
        )
        self.assertContains(response, "Select Quote")
        self.assertNotContains(response, "Record Received Quote")

    def test_select_quote_preserves_quotes_and_leaves_work_unassigned(self):
        other_vendor = Vendor.objects.create(
            name="Morgan HVAC",
            company_name="Morgan HVAC",
            email="morgan@example.com",
            status="active",
        )
        old_estimate = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            status="approved",
            source="phone",
        )
        new_estimate = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=other_vendor,
            amount=Decimal("390.00"),
            status="pending",
            source="email",
        )

        response = self.client.post(
            f"{reverse('portal:assign_vendor', args=[self.work_order.pk])}?estimate_id={new_estimate.pk}",
            {
                "vendor": other_vendor.pk,
                "scheduled_for": "",
                "vendor_notes": "Preferred quoted vendor.",
            },
        )

        self.assertRedirects(
            response,
            reverse("portal:work_order_detail", args=[self.work_order.pk]),
        )
        self.assertFalse(
            VendorAssignment.objects.filter(
                work_order=self.work_order,
                vendor=other_vendor,
            ).exists()
        )
        old_estimate.refresh_from_db()
        new_estimate.refresh_from_db()
        self.work_order.refresh_from_db()
        self.assertEqual(old_estimate.status, "approved")
        self.assertEqual(new_estimate.status, "pending")
        award = VendorAward.objects.get(
            work_order=self.work_order, status="pending_confirmation"
        )
        self.assertEqual(award.estimate, new_estimate)
        self.assertEqual(award.vendor, other_vendor)
        self.assertEqual(self.work_order.estimated_cost, Decimal("390.00"))
        self.assertEqual(self.work_order.status, "new")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("pending confirmation", mail.outbox[0].body)

    def test_received_quote_can_be_recorded_after_another_quote_is_selected(self):
        VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            status="approved",
            source="phone",
        )
        responding_vendor = Vendor.objects.create(
            name="Austin Pro Plumbing",
            company_name="Austin Pro Plumbing",
            email="austin-pro@example.com",
            status="active",
        )
        quote_request = VendorQuoteRequest.objects.create(
            work_order=self.work_order,
            vendor=responding_vendor,
            status="sent",
            scope=self.work_order.description,
            requested_by=self.user,
        )
        url = (
            f"{reverse('portal:add_vendor_estimate', args=[self.work_order.pk])}"
            f"?request_id={quote_request.pk}"
        )

        get_response = self.client.get(url)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(
            get_response.context["form"].fields["vendor"].initial,
            responding_vendor.pk,
        )

        post_response = self.client.post(
            url,
            self.base_quote_data(
                vendor=responding_vendor.pk,
                source="col360",
                amount="390.00",
            ),
        )

        self.assertRedirects(
            post_response,
            reverse("portal:work_order_detail", args=[self.work_order.pk]),
        )
        recorded_quote = VendorEstimate.objects.get(vendor=responding_vendor)
        quote_request.refresh_from_db()
        self.assertEqual(recorded_quote.quote_request, quote_request)
        self.assertEqual(recorded_quote.status, "pending")
        self.assertEqual(quote_request.status, "quote_received")

    def test_vendor_confirmation_awards_quote_without_assigning_work(self):
        estimate = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            source="email",
        )
        award = VendorAward.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            estimate=estimate,
            method="quote",
            status="pending_confirmation",
            awarded_by=self.user,
        )

        response = self.client.post(
            reverse("portal:confirm_vendor", args=[self.work_order.pk, award.pk])
        )

        self.assertRedirects(
            response, reverse("portal:work_order_detail", args=[self.work_order.pk])
        )
        award.refresh_from_db()
        self.work_order.refresh_from_db()
        self.assertEqual(award.status, "active")
        self.assertEqual(award.confirmed_by, self.user)
        self.assertIsNotNone(award.confirmed_at)
        self.assertEqual(self.work_order.status, "new")
        self.assertFalse(
            VendorAssignment.objects.filter(work_order=self.work_order).exists()
        )

    def test_confirmed_vendor_must_be_explicitly_assigned(self):
        estimate = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            source="email",
        )
        award = VendorAward.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            estimate=estimate,
            method="quote",
            status="active",
            awarded_by=self.user,
            confirmed_by=self.user,
            confirmed_at=timezone.now(),
        )

        response = self.client.post(
            reverse(
                "portal:assign_awarded_vendor",
                args=[self.work_order.pk, award.pk],
            )
        )

        self.assertRedirects(
            response, reverse("portal:work_order_detail", args=[self.work_order.pk])
        )
        assignment = VendorAssignment.objects.get(work_order=self.work_order)
        self.work_order.refresh_from_db()
        self.assertEqual(assignment.vendor, self.vendor)
        self.assertEqual(assignment.status, "assigned")
        self.assertEqual(self.work_order.status, "assigned")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("has been assigned to you", mail.outbox[0].body)

    def test_assigned_vendor_cannot_be_changed_until_assignment_is_cancelled(self):
        estimate = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            source="email",
        )
        VendorAward.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            estimate=estimate,
            method="quote",
            status="active",
        )
        VendorAssignment.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            status="assigned",
        )

        response = self.client.get(
            reverse("portal:change_vendor", args=[self.work_order.pk])
        )

        self.assertRedirects(
            response, reverse("portal:work_order_detail", args=[self.work_order.pk])
        )
        self.assertTrue(
            VendorAward.objects.filter(
                work_order=self.work_order, status="active"
            ).exists()
        )

    def test_cancelling_assignment_keeps_confirmed_award(self):
        estimate = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            source="email",
        )
        award = VendorAward.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            estimate=estimate,
            method="quote",
            status="active",
        )
        assignment = VendorAssignment.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            status="assigned",
        )
        self.work_order.status = "assigned"
        self.work_order.save(update_fields=["status"])

        response = self.client.post(
            reverse(
                "portal:cancel_vendor_assignment",
                args=[self.work_order.pk, assignment.pk],
            ),
            {
                "reason": "vendor_unavailable",
                "notes": "Vendor cannot meet the required start date.",
            },
        )

        self.assertRedirects(
            response, reverse("portal:work_order_detail", args=[self.work_order.pk])
        )
        assignment.refresh_from_db()
        award.refresh_from_db()
        self.work_order.refresh_from_db()
        self.assertEqual(assignment.status, "cancelled")
        self.assertEqual(award.status, "active")
        self.assertEqual(self.work_order.status, "new")

    def test_change_vendor_revokes_award_and_selects_alternative(self):
        current_estimate = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            status="approved",
            source="phone",
        )
        current_award = VendorAward.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            estimate=current_estimate,
            method="quote",
            awarded_by=self.user,
        )
        replacement_vendor = Vendor.objects.create(
            name="Backup Vendor",
            company_name="Backup Vendor",
            email="backup@example.com",
            status="active",
        )
        replacement_estimate = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=replacement_vendor,
            amount=Decimal("390.00"),
            status="pending",
            source="email",
        )

        response = self.client.post(
            reverse("portal:change_vendor", args=[self.work_order.pk]),
            {
                "reason": "vendor_unavailable",
                "notes": "Current vendor cannot comply.",
                "replacement_estimate": replacement_estimate.pk,
            },
        )

        self.assertRedirects(
            response,
            reverse("portal:work_order_detail", args=[self.work_order.pk]),
        )
        current_award.refresh_from_db()
        replacement_estimate.refresh_from_db()
        self.work_order.refresh_from_db()
        self.assertEqual(current_award.status, "revoked")
        self.assertEqual(replacement_estimate.status, "pending")
        self.assertEqual(
            VendorAward.objects.get(
                work_order=self.work_order, status="pending_confirmation"
            ).estimate,
            replacement_estimate,
        )
        self.assertEqual(self.work_order.status, "new")
        self.assertIsNone(self.work_order.scheduled_for)
        self.assertFalse(
            VendorAssignment.objects.filter(
                work_order=self.work_order, vendor=replacement_vendor
            ).exists()
        )

    def test_existing_award_returns_staff_to_work_order(self):
        estimate = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            source="phone",
        )
        VendorAward.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            estimate=estimate,
            method="quote",
        )
        response = self.client.get(
            reverse("portal:assign_vendor", args=[self.work_order.pk])
        )
        self.assertRedirects(
            response, reverse("portal:work_order_detail", args=[self.work_order.pk])
        )

    def test_change_vendor_requires_reason(self):
        estimate = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            source="phone",
        )
        VendorAward.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            estimate=estimate,
            method="quote",
        )
        response = self.client.post(
            reverse("portal:change_vendor", args=[self.work_order.pk]),
            {"reason": "", "notes": "", "replacement_estimate": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "reason", "This field is required.")
        self.assertTrue(
            VendorAward.objects.filter(work_order=self.work_order, status="active").exists()
        )

    def test_direct_assignment_requires_quote_waiver_reason(self):
        response = self.client.post(
            reverse("portal:assign_vendor", args=[self.work_order.pk]),
            {
                "vendor": self.vendor.pk,
                "scheduled_for": "",
                "vendor_notes": "Known warranty provider.",
                "direct_assignment_reason": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "direct_assignment_reason",
            "This field is required.",
        )

    def test_database_allows_only_one_current_award(self):
        estimate = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            source="phone",
        )
        VendorAward.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            estimate=estimate,
            method="quote",
        )
        other_vendor = Vendor.objects.create(
            name="Second Vendor",
            company_name="Second Vendor",
            email="second@example.com",
            status="active",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            VendorAward.objects.create(
                work_order=self.work_order,
                vendor=other_vendor,
                method="direct",
                status="pending_confirmation",
                decision_reason="urgent",
            )

    def test_higher_quote_requires_award_rationale(self):
        lower_vendor = Vendor.objects.create(
            name="Lower Vendor",
            company_name="Lower Vendor",
            email="lower@example.com",
            status="active",
        )
        VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=lower_vendor,
            amount=Decimal("300.00"),
            source="email",
        )
        higher_quote = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            source="email",
        )
        form = VendorAssignmentForm(
            data={
                "vendor": self.vendor.pk,
                "scheduled_for": "",
                "vendor_notes": "",
                "award_rationale": "",
                "award_rationale_notes": "",
            },
            work_order=self.work_order,
            quote_selected=True,
            selected_estimate=higher_quote,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("award_rationale", form.errors)

    def test_award_rationale_controls_are_inside_assignment_form(self):
        lower_vendor = Vendor.objects.create(
            name="Lower Vendor",
            company_name="Lower Vendor",
            email="lower@example.com",
            status="active",
        )
        VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=lower_vendor,
            amount=Decimal("300.00"),
            source="email",
        )
        higher_quote = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            source="email",
        )
        response = self.client.get(
            f"{reverse('portal:assign_vendor', args=[self.work_order.pk])}?estimate_id={higher_quote.pk}"
        )
        content = response.content.decode()
        form_start = content.index('<form method="post">')
        rationale = content.index('id="id_award_rationale"')
        form_end = content.index("</form>", form_start)
        self.assertLess(form_start, rationale)
        self.assertLess(rationale, form_end)

    def test_higher_quote_rationale_is_saved_on_award(self):
        lower_vendor = Vendor.objects.create(
            name="Lower Vendor",
            company_name="Lower Vendor",
            email="lower@example.com",
            status="active",
        )
        VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=lower_vendor,
            amount=Decimal("300.00"),
            source="email",
        )
        higher_quote = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            source="email",
        )
        response = self.client.post(
            f"{reverse('portal:assign_vendor', args=[self.work_order.pk])}?estimate_id={higher_quote.pk}",
            {
                "vendor": self.vendor.pk,
                "scheduled_for": "",
                "vendor_notes": "",
                "award_rationale": "faster_availability",
                "award_rationale_notes": "Can begin tomorrow.",
            },
        )
        self.assertRedirects(
            response,
            reverse("portal:work_order_detail", args=[self.work_order.pk]),
        )
        award = VendorAward.objects.get(
            work_order=self.work_order, status="pending_confirmation"
        )
        self.assertEqual(award.decision_reason, "faster_availability")
        self.assertEqual(award.decision_notes, "Can begin tomorrow.")

    def test_awarded_work_order_uses_one_vendor_section_without_disabled_financials(self):
        estimate = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            source="phone",
        )
        VendorAward.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            estimate=estimate,
            method="quote",
            decision_reason="lowest_qualified_quote",
        )
        VendorAssignment.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            status="assigned",
        )
        response = self.client.get(
            reverse("portal:work_order_detail", args=[self.work_order.pk])
        )
        self.assertContains(response, "Vendor Award &amp; Quotes")
        self.assertNotContains(response, ">Active Vendor</h2>", html=False)
        self.assertNotContains(response, "Accounting is disabled")

    def test_awarded_work_order_displays_active_and_alternative_vendors_together(self):
        active_quote = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            source="phone",
        )
        alternative_vendor = Vendor.objects.create(
            name="Alternative Vendor",
            company_name="Alternative Vendor",
            email="alternative@example.com",
            status="active",
        )
        VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=alternative_vendor,
            amount=Decimal("400.00"),
            source="email",
        )
        VendorAward.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            estimate=active_quote,
            method="quote",
            decision_reason="better_scope",
        )
        VendorAssignment.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            status="assigned",
        )

        response = self.client.get(
            reverse("portal:work_order_detail", args=[self.work_order.pk])
        )

        self.assertContains(response, str(self.vendor), count=1)
        self.assertContains(response, "Alternative Vendor")
        self.assertContains(response, "Awarded Vendor")
        self.assertContains(response, "Alternative")
        self.assertContains(response, "Available through Change Vendor")
        self.assertContains(response, "Work Status")
        self.assertContains(response, "More Details")
        self.assertContains(response, "Change Vendor")
        self.assertNotContains(response, "alternative-quotes-toggle")

    def test_active_vendor_award_information_is_kept_in_expandable_details(self):
        active_quote = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            source="phone",
        )
        VendorAward.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            estimate=active_quote,
            method="quote",
            decision_reason="better_scope",
            decision_notes="Includes a longer workmanship warranty.",
            awarded_by=self.user,
        )
        VendorAssignment.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            status="assigned",
        )

        response = self.client.get(
            reverse("portal:work_order_detail", args=[self.work_order.pk])
        )

        self.assertContains(response, "Selection Method")
        self.assertContains(response, "Award Rationale")
        self.assertContains(response, "Better scope of work")
        self.assertContains(response, "Includes a longer workmanship warranty.")
        self.assertContains(response, "Awarded By")

    def test_vendor_awaiting_quote_can_still_be_recorded_after_an_award(self):
        active_quote = VendorEstimate.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            amount=Decimal("425.00"),
            source="phone",
        )
        VendorAward.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            estimate=active_quote,
            method="quote",
            decision_reason="lowest_qualified_quote",
        )
        VendorAssignment.objects.create(
            work_order=self.work_order,
            vendor=self.vendor,
            status="assigned",
        )
        pending_vendor = Vendor.objects.create(
            name="Pending Vendor",
            company_name="Pending Vendor",
            email="pending@example.com",
            status="active",
        )
        VendorQuoteRequest.objects.create(
            work_order=self.work_order,
            vendor=pending_vendor,
            status="sent",
        )

        response = self.client.get(
            reverse("portal:work_order_detail", args=[self.work_order.pk])
        )

        self.assertContains(response, "Pending Vendor")
        self.assertContains(response, "Record Received Quote")
