from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from common.audit.models import AuditEvent
from maintenance.models import MaintenanceRequest, WorkOrder
from portal.forms import (
    MaintenanceRequestCreateForm,
    MaintenanceRequestReviewForm,
    WorkOrderCreateForm,
)
from properties.models import Property, PropertyUnit


class MaintenanceRequestCreateFormTests(TestCase):
    def setUp(self):
        self.property = Property.objects.create(
            street_address="100 Test Street",
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
            property=self.property,
            unit_number="",
        )
        self.other_property = Property.objects.create(
            street_address="200 Test Street",
            city="Austin",
            state="TX",
            zip_code="78702",
            county="Travis",
            subdivision="Test",
            property_type="single_family_residential",
            management_status="active",
            is_multi_unit=False,
        )
        self.other_unit = PropertyUnit.objects.create(
            property=self.other_property,
            unit_number="",
        )

    def form_data(self, **overrides):
        data = {
            "property": self.property.pk,
            "unit": self.unit.pk,
            "lease": "",
            "reported_by_tenant": "",
            "title": "Leaking faucet",
            "description": "The kitchen faucet is leaking.",
            "category": "plumbing",
            "priority": "normal",
            "permission_to_enter": "on",
            "availability_date": date(2026, 10, 2).isoformat(),
            "availability_start_time": "10:00",
            "availability_end_time": "11:15",
        }
        data.update(overrides)
        return data

    def test_accepts_structured_availability(self):
        form = MaintenanceRequestCreateForm(data=self.form_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_unit_from_another_property(self):
        form = MaintenanceRequestCreateForm(
            data=self.form_data(unit=self.other_unit.pk)
        )
        self.assertFalse(form.is_valid())
        self.assertIn("unit", form.errors)

    def test_requires_complete_availability_window(self):
        form = MaintenanceRequestCreateForm(
            data=self.form_data(availability_end_time="")
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_end_time_must_follow_start_time(self):
        form = MaintenanceRequestCreateForm(
            data=self.form_data(
                availability_start_time="11:00",
                availability_end_time="10:45",
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("availability_end_time", form.errors)

    def test_time_choices_use_fifteen_minute_intervals(self):
        form = MaintenanceRequestCreateForm()
        values = [
            value
            for value, _label in form.fields[
                "availability_start_time"
            ].widget.choices
            if value
        ]
        self.assertIn("10:00", values)
        self.assertIn("10:15", values)
        self.assertIn("10:30", values)
        self.assertNotIn("10:10", values)

    def test_location_fields_are_ordered_and_use_concise_labels(self):
        self.unit.unit_number = "1602"
        self.unit.save(update_fields=["unit_number"])

        form = MaintenanceRequestCreateForm(
            instance=MaintenanceRequest(unit=self.unit)
        )

        self.assertEqual(
            list(form.fields)[:4],
            ["property", "unit", "lease", "reported_by_tenant"],
        )
        self.assertEqual(form.fields["lease"].label, "Lease Period")
        self.assertEqual(
            form.fields["unit"].label_from_instance(self.unit),
            "Unit 1602",
        )


class MaintenanceRequestReviewWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="maintenance_manager",
            password="test-password",
            is_staff=True,
        )
        self.property = Property.objects.create(
            street_address="300 Review Street",
            city="Austin",
            state="TX",
            zip_code="78703",
            county="Travis",
            subdivision="Test",
            property_type="single_family_residential",
            management_status="active",
            is_multi_unit=False,
        )
        self.unit = PropertyUnit.objects.create(
            property=self.property,
            unit_number="",
        )
        self.maintenance_request = MaintenanceRequest.objects.create(
            unit=self.unit,
            reported_by_user=self.user,
            title="No hot water",
            description="The water heater is not producing hot water.",
            category="plumbing",
            priority="normal",
            status="new",
        )
        self.client.force_login(self.user)

    def approval_data(self, **overrides):
        data = {
            "category": "plumbing",
            "priority": "high",
            "review_notes": "Confirm access with the tenant before arrival.",
        }
        data.update(overrides)
        return data

    def test_review_form_contains_only_review_fields(self):
        form = MaintenanceRequestReviewForm(
            instance=self.maintenance_request,
        )
        self.assertEqual(
            list(form.fields),
            [
                "category",
                "priority",
                "assigned_reviewer",
                "review_due_at",
                "pending_reason",
                "review_notes",
                "decision",
            ],
        )

    def test_follow_up_fields_are_progressively_disclosed(self):
        response = self.client.get(
            reverse(
                "portal:maintenance_detail",
                args=[self.maintenance_request.pk],
            )
        )

        self.assertContains(response, 'id="review-follow-up-fields"')
        self.assertContains(response, 'data-decision="under_review"')
        self.assertContains(response, 'data-decision="pending_information"')
        self.assertContains(response, 'data-decision="declined"')
        self.assertContains(response, "display:none;margin-top:16px")

    def test_new_request_can_be_reviewed_and_approved_directly(self):
        response = self.client.post(
            reverse(
                "portal:approve_maintenance_request",
                args=[self.maintenance_request.pk],
            ),
            self.approval_data(),
        )

        self.assertRedirects(
            response,
            reverse(
                "portal:create_work_order",
                args=[self.maintenance_request.pk],
            ),
        )
        self.maintenance_request.refresh_from_db()
        self.assertEqual(self.maintenance_request.status, "approved")
        self.assertEqual(self.maintenance_request.priority, "high")
        self.assertEqual(
            self.maintenance_request.review_notes,
            "Confirm access with the tenant before arrival.",
        )
        self.assertEqual(self.maintenance_request.reviewed_by, self.user)
        self.assertIsNotNone(self.maintenance_request.reviewed_at)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="MAINTENANCE_REQUEST_APPROVED",
                entity_id=str(self.maintenance_request.pk),
            ).exists()
        )

    def test_legacy_triaged_request_can_use_combined_approval(self):
        self.maintenance_request.status = "triaged"
        self.maintenance_request.save(update_fields=["status"])

        response = self.client.post(
            reverse(
                "portal:approve_maintenance_request",
                args=[self.maintenance_request.pk],
            ),
            self.approval_data(),
        )

        self.assertEqual(response.status_code, 302)
        self.maintenance_request.refresh_from_db()
        self.assertEqual(self.maintenance_request.status, "approved")

    def test_request_can_be_placed_pending_with_owner_and_deadline(self):
        due_at = timezone.now() + timedelta(days=2)
        response = self.client.post(
            reverse(
                "portal:approve_maintenance_request",
                args=[self.maintenance_request.pk],
            ),
            self.approval_data(
                decision="pending_information",
                pending_reason="budget_review",
                assigned_reviewer=self.user.pk,
                review_due_at=due_at.strftime("%Y-%m-%dT%H:%M"),
                review_notes="Confirm the available repair budget with accounting.",
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.maintenance_request.refresh_from_db()
        self.assertEqual(self.maintenance_request.status, "pending_information")
        self.assertEqual(self.maintenance_request.pending_reason, "budget_review")
        self.assertEqual(self.maintenance_request.assigned_reviewer, self.user)
        self.assertIsNotNone(self.maintenance_request.review_due_at)
        self.assertTrue(
            AuditEvent.objects.filter(
                action="MAINTENANCE_REQUEST_PENDING_INFORMATION",
                entity_id=str(self.maintenance_request.pk),
            ).exists()
        )

    def test_pending_decision_requires_explanation_owner_and_deadline(self):
        response = self.client.post(
            reverse(
                "portal:approve_maintenance_request",
                args=[self.maintenance_request.pk],
            ),
            self.approval_data(
                decision="pending_information",
                pending_reason="",
                assigned_reviewer="",
                review_due_at="",
                review_notes="",
            ),
        )

        self.assertEqual(response.status_code, 400)
        self.maintenance_request.refresh_from_db()
        self.assertEqual(self.maintenance_request.status, "new")

    def test_request_can_be_declined_with_reason(self):
        response = self.client.post(
            reverse(
                "portal:approve_maintenance_request",
                args=[self.maintenance_request.pk],
            ),
            self.approval_data(
                decision="declined",
                review_notes="Duplicate of an existing open request.",
            ),
        )

        self.assertEqual(response.status_code, 302)
        self.maintenance_request.refresh_from_db()
        self.assertEqual(self.maintenance_request.status, "declined")
        self.assertEqual(self.maintenance_request.reviewed_by, self.user)
        self.assertIsNotNone(self.maintenance_request.reviewed_at)

    def test_detail_shows_earlier_property_maintenance_history(self):
        previous = MaintenanceRequest.objects.create(
            unit=self.unit,
            reported_by_user=self.user,
            title="Earlier plumbing repair",
            description="Previous issue at the property.",
            category="plumbing",
            status="completed",
        )

        response = self.client.get(
            reverse(
                "portal:maintenance_detail",
                args=[self.maintenance_request.pk],
            )
        )

        self.assertContains(response, "Property &amp; Unit Maintenance History")
        self.assertContains(response, previous.title)


class WorkOrderDirectoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="work_order_manager",
            password="test-password",
            is_staff=True,
        )
        self.property = Property.objects.create(
            street_address="400 Work Order Avenue",
            city="Austin",
            state="TX",
            zip_code="78704",
            county="Travis",
            subdivision="Test",
            property_type="single_family_residential",
            management_status="active",
            is_multi_unit=False,
        )
        self.unit = PropertyUnit.objects.create(
            property=self.property,
            unit_number="",
        )
        self.older = WorkOrder.objects.create(
            unit=self.unit,
            title="Older plumbing repair",
            description="Repair the kitchen faucet.",
            status="completed",
        )
        self.newer = WorkOrder.objects.create(
            unit=self.unit,
            title="New electrical repair",
            description="Repair the living room lights.",
            status="new",
        )
        self.client.force_login(self.user)

    def test_directory_lists_newest_work_order_first(self):
        response = self.client.get(reverse("portal:work_orders"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["work_orders"]),
            [self.newer, self.older],
        )

    def test_directory_filters_by_status(self):
        response = self.client.get(
            reverse("portal:work_orders"),
            {"status": "completed"},
        )

        self.assertEqual(list(response.context["work_orders"]), [self.older])

    def test_unassigned_queue_excludes_closed_work_orders(self):
        response = self.client.get(
            reverse("portal:work_orders"),
            {"queue": "unassigned"},
        )

        self.assertEqual(list(response.context["work_orders"]), [self.newer])


class WorkOrderValidationAndReplacementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="replacement_manager",
            password="test-password",
            is_staff=True,
        )
        self.property = Property.objects.create(
            street_address="500 Replacement Way",
            city="Austin",
            state="TX",
            zip_code="78705",
            county="Travis",
            subdivision="Test",
            property_type="single_family_residential",
            management_status="active",
            is_multi_unit=False,
        )
        self.unit = PropertyUnit.objects.create(
            property=self.property,
            unit_number="",
        )
        self.maintenance_request = MaintenanceRequest.objects.create(
            unit=self.unit,
            reported_by_user=self.user,
            title="Repair leaking sink",
            description="Repair the pipe beneath the sink.",
            category="plumbing",
            priority="normal",
            status="approved",
        )
        self.client.force_login(self.user)

    def work_order_data(self, **overrides):
        data = {
            "title": "Repair leaking sink",
            "description": "Repair the pipe beneath the sink.",
            "scheduled_for": "",
            "estimated_cost": "250.00",
            "notes": "",
        }
        data.update(overrides)
        return data

    def test_create_form_rejects_past_scheduled_datetime(self):
        past = timezone.localtime() - timedelta(days=1)
        form = WorkOrderCreateForm(
            data=self.work_order_data(
                scheduled_for=past.strftime("%Y-%m-%dT%H:%M")
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("scheduled_for", form.errors)

    def test_create_form_sets_browser_minimum_and_fifteen_minute_step(self):
        form = WorkOrderCreateForm()
        attrs = form.fields["scheduled_for"].widget.attrs

        self.assertIn("min", attrs)
        self.assertEqual(attrs["step"], "900")
        self.assertEqual(int(attrs["min"][-2:]) % 15, 0)

    def test_create_form_accepts_future_quarter_hour(self):
        scheduled_for = (timezone.localtime() + timedelta(days=1)).replace(
            minute=0,
            second=0,
            microsecond=0,
        )
        form = WorkOrderCreateForm(
            data=self.work_order_data(
                scheduled_for=scheduled_for.strftime("%Y-%m-%dT%H:%M")
            )
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_create_form_rejects_non_quarter_hour(self):
        scheduled_for = (timezone.localtime() + timedelta(days=1)).replace(
            minute=7,
            second=0,
            microsecond=0,
        )
        form = WorkOrderCreateForm(
            data=self.work_order_data(
                scheduled_for=scheduled_for.strftime("%Y-%m-%dT%H:%M")
            )
        )

        self.assertFalse(form.is_valid())
        self.assertIn("scheduled_for", form.errors)

    def test_cancelled_work_order_can_be_replaced_without_deleting_history(self):
        original = WorkOrder.objects.create(
            maintenance_request=self.maintenance_request,
            unit=self.unit,
            title="Original repair order",
            description="Original work order.",
            status="new",
        )
        self.maintenance_request.status = "converted"
        self.maintenance_request.save(update_fields=["status"])

        cancel_response = self.client.post(
            reverse("portal:cancel_work_order", args=[original.pk]),
            {"cancellation_reason": "Vendor is no longer available."},
        )
        self.assertEqual(cancel_response.status_code, 302)

        original.refresh_from_db()
        self.maintenance_request.refresh_from_db()
        self.assertEqual(original.status, "cancelled")
        self.assertEqual(self.maintenance_request.status, "approved")

        replacement_response = self.client.post(
            reverse(
                "portal:create_work_order",
                args=[self.maintenance_request.pk],
            ),
            self.work_order_data(),
        )
        self.assertEqual(replacement_response.status_code, 302)

        linked_orders = list(
            WorkOrder.objects.filter(
                maintenance_request=self.maintenance_request
            ).order_by("created_at")
        )
        self.assertEqual(len(linked_orders), 2)
        replacement = linked_orders[1]
        self.assertEqual(replacement.supersedes, original)
        self.assertEqual(original.status, "cancelled")
        self.maintenance_request.refresh_from_db()
        self.assertEqual(self.maintenance_request.status, "converted")
