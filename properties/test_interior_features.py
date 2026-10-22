from django.template.loader import render_to_string
from django.test import TestCase
from .editor_forms import PropertyProfileForm
from .editor_display import profile_sections
from .models import InteriorFeatureOption, Property, PropertyProfile


class InteriorFeatureTests(TestCase):
    def setUp(self):
        self.property = Property.objects.create(street_address="100 Test Ln", city="Austin", state="TX", zip_code="78701")
        self.profile = PropertyProfile.objects.create(property=self.property, interior_features="Original room-by-room notes")

    def form(self, codes, **changes):
        data = {"profile-interior_feature_types": codes, "profile-interior_features": self.profile.interior_features}
        data.update(changes)
        return PropertyProfileForm(data, instance=self.profile, prefix="profile")

    def test_multiple_types_save_reopen_and_preserve_legacy(self):
        form = self.form(["pantry", "kitchen-island"])
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.interior_feature_types, ["pantry", "kitchen-island"])
        self.assertEqual(self.profile.interior_features, "Original room-by-room notes")
        reopened = PropertyProfileForm(instance=self.profile, prefix="profile")
        self.assertEqual(reopened["interior_feature_types"].value(), ["pantry", "kitchen-island"])
        fields = [f for s in profile_sections(self.property) for f in s["fields"] if f["label"] == "Interior Features"]
        self.assertEqual(fields[0]["value"], "Pantry, Kitchen Island; Original room-by-room notes")

    def test_admin_added_label_is_rendered_and_can_be_saved(self):
        InteriorFeatureOption.objects.create(code="custom-feature", label="Custom Feature")
        form = self.form(["custom-feature"])
        self.assertTrue(form.is_valid(), form.errors)
        html = render_to_string("portal/property_interior_features.html", {"profile_form": form, "field": form["interior_features"]})
        self.assertIn("Custom Feature", html)
        self.assertIn('type="checkbox"', html)
        self.assertRegex(html, r'value="custom-feature"[^>]* checked')

    def test_retired_choices_preserved_only_for_existing_property(self):
        InteriorFeatureOption.objects.filter(code="kitchen-island").update(is_active=False)
        self.profile.interior_feature_types = ["kitchen-island"]
        self.profile.save()
        form = self.form(["kitchen-island"])
        self.assertTrue(form.is_valid(), form.errors)
        new = PropertyProfileForm({"interior_feature_types": ["kitchen-island"]})
        self.assertFalse(new.is_valid())
        self.assertIn("interior_feature_types", new.errors)

    def test_deleted_vocabulary_keeps_saved_selection(self):
        self.profile.interior_feature_types = ["historic-type"]
        self.profile.save()
        form = self.form(["historic-type"])
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_post_is_rejected_and_other_details_survive(self):
        invalid = self.form(["made-up-code"])
        self.assertFalse(invalid.is_valid())
        self.assertIn("interior_feature_types", invalid.errors)
        form = self.form(["other"], **{"profile-interior_features": "Reclaimed timber in study"})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.interior_features, "Reclaimed timber in study")

    def test_clearing_selections_does_not_remove_notes(self):
        self.profile.interior_feature_types = ["smart-home"]
        self.profile.save()
        form = self.form([])
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.interior_feature_types, [])
        self.assertEqual(self.profile.interior_features, "Original room-by-room notes")

    def test_none_and_conflicting_steps_are_rejected(self):
        for codes in (["none", "pantry"], ["interior-steps", "no-interior-steps"]):
            form = self.form(codes)
            self.assertFalse(form.is_valid())
            self.assertIn("interior_feature_types", form.errors)
        self.assertTrue(self.form(["none"]).is_valid())

    def test_flooring_and_interior_selections_saved_together(self):
        form = self.form(["pantry", "smart-home"], **{"profile-flooring_types": ["carpet", "wood"], "profile-flooring": "Wood downstairs"})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.flooring_types, ["carpet", "wood"])
        self.assertEqual(self.profile.interior_feature_types, ["pantry", "smart-home"])
