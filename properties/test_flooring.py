from django.template.loader import render_to_string
from django.test import TestCase
from .editor_forms import PropertyProfileForm
from .editor_display import profile_sections
from .models import FlooringOption, Property, PropertyProfile


class FlooringTests(TestCase):
    def setUp(self):
        self.property = Property.objects.create(street_address="100 Test Ln", city="Austin", state="TX", zip_code="78701")
        self.profile = PropertyProfile.objects.create(property=self.property, flooring="Original room-by-room notes")

    def form(self, codes, **changes):
        data = {"profile-flooring_types": codes, "profile-flooring": self.profile.flooring}
        data.update(changes)
        return PropertyProfileForm(data, instance=self.profile, prefix="profile")

    def test_multiple_types_save_reopen_and_preserve_legacy(self):
        form = self.form(["carpet", "wood"])
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.flooring_types, ["carpet", "wood"])
        self.assertEqual(self.profile.flooring, "Original room-by-room notes")
        reopened = PropertyProfileForm(instance=self.profile, prefix="profile")
        self.assertEqual(reopened["flooring_types"].value(), ["carpet", "wood"])
        fields = [f for s in profile_sections(self.property) for f in s["fields"] if f["label"] == "Flooring"]
        self.assertEqual(fields[0]["value"], "Carpet, Wood; Original room-by-room notes")

    def test_admin_added_label_is_rendered_and_can_be_saved(self):
        FlooringOption.objects.create(code="engineered-wood", label="Engineered Wood")
        form = self.form(["engineered-wood"])
        self.assertTrue(form.is_valid(), form.errors)
        html = render_to_string("portal/property_flooring.html", {"profile_form": form, "field": form["flooring"]})
        self.assertIn("Engineered Wood", html)
        self.assertIn('type="checkbox"', html)
        self.assertRegex(html, r'value="engineered-wood"[^>]* checked')

    def test_retired_choices_preserved_only_for_existing_property(self):
        FlooringOption.objects.filter(code="wood").update(is_active=False)
        self.profile.flooring_types = ["wood"]
        self.profile.save()
        form = self.form(["wood"])
        self.assertTrue(form.is_valid(), form.errors)
        new = PropertyProfileForm({"flooring_types": ["wood"]})
        self.assertFalse(new.is_valid())
        self.assertIn("flooring_types", new.errors)

    def test_deleted_vocabulary_keeps_saved_selection(self):
        self.profile.flooring_types = ["historic-type"]
        self.profile.save()
        form = self.form(["historic-type"])
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_post_is_rejected_and_other_details_survive(self):
        invalid = self.form(["made-up-code"])
        self.assertFalse(invalid.is_valid())
        self.assertIn("flooring_types", invalid.errors)
        form = self.form(["other"], **{"profile-flooring": "Reclaimed timber in study"})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.flooring, "Reclaimed timber in study")

    def test_clearing_selections_does_not_remove_notes(self):
        self.profile.flooring_types = ["tile"]
        self.profile.save()
        form = self.form([])
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.flooring_types, [])
        self.assertEqual(self.profile.flooring, "Original room-by-room notes")
