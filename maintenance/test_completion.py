from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from portal.forms import WorkOrderCompleteForm


class WorkOrderCompletionValidationTests(SimpleTestCase):
    def setUp(self):
        self.started_at = timezone.now() - timedelta(hours=1)

    def form_data(self, **overrides):
        data = {
            "actual_cost": "325.00",
            "completed_at": "",
            "completion_notes": "Replaced the failed component and tested it.",
        }
        data.update(overrides)
        return data

    def test_completion_notes_are_required(self):
        form = WorkOrderCompleteForm(
            data=self.form_data(completion_notes=""),
            started_at=self.started_at,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("completion_notes", form.errors)

    def test_completion_time_cannot_be_in_the_future(self):
        future = timezone.localtime() + timedelta(hours=1)
        form = WorkOrderCompleteForm(
            data=self.form_data(completed_at=future.strftime("%Y-%m-%dT%H:%M")),
            started_at=self.started_at,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("completed_at", form.errors)

    def test_completion_time_cannot_precede_start(self):
        before_start = timezone.localtime(self.started_at) - timedelta(minutes=1)
        form = WorkOrderCompleteForm(
            data=self.form_data(
                completed_at=before_start.strftime("%Y-%m-%dT%H:%M")
            ),
            started_at=self.started_at,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("completed_at", form.errors)

    def test_blank_completion_time_uses_view_default(self):
        form = WorkOrderCompleteForm(
            data=self.form_data(),
            started_at=self.started_at,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["completed_at"])
