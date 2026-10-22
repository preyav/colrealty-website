from django.template.loader import render_to_string
from django.test import TestCase
from .editor_forms import PropertyProfileForm
from .editor_display import profile_sections
from .models import FoundationOption, Property, PropertyProfile


class FoundationTests(TestCase):
    def setUp(self):
        self.property = Property.objects.create(street_address="100 Test Ln", city="Austin", state="TX", zip_code="78701")
        self.profile = PropertyProfile.objects.create(property=self.property, foundation="Original room-by-room notes")

    def form(self, codes, **changes):
        data = {"profile-foundation_types": codes, "profile-foundation": self.profile.foundation}
        data.update(changes)
        return PropertyProfileForm(data, instance=self.profile, prefix="profile")

    def test_multiple_types_save_reopen_and_preserve_legacy(self):
        form = self.form(["slab", "raised"])
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.foundation_types, ["slab", "raised"])
        self.assertEqual(self.profile.foundation, "Original room-by-room notes")
        reopened = PropertyProfileForm(instance=self.profile, prefix="profile")
        self.assertEqual(reopened["foundation_types"].value(), ["slab", "raised"])
        fields = [f for s in profile_sections(self.property) for f in s["fields"] if f["label"] == "Foundation"]
        self.assertEqual(fields[0]["value"], "Slab, Raised; Original room-by-room notes")

    def test_admin_added_label_is_rendered_and_can_be_saved(self):
        FoundationOption.objects.create(code="custom-feature", label="Custom Feature")
        form = self.form(["custom-feature"])
        self.assertTrue(form.is_valid(), form.errors)
        html = render_to_string("portal/property_foundation.html", {"profile_form": form, "field": form["foundation"]})
        self.assertIn("Custom Feature", html)
        self.assertIn('type="checkbox"', html)
        self.assertRegex(html, r'value="custom-feature"[^>]* checked')

    def test_retired_choices_preserved_only_for_existing_property(self):
        FoundationOption.objects.filter(code="raised").update(is_active=False)
        self.profile.foundation_types = ["raised"]
        self.profile.save()
        form = self.form(["raised"])
        self.assertTrue(form.is_valid(), form.errors)
        new = PropertyProfileForm({"foundation_types": ["raised"]})
        self.assertFalse(new.is_valid())
        self.assertIn("foundation_types", new.errors)

    def test_deleted_vocabulary_keeps_saved_selection(self):
        self.profile.foundation_types = ["historic-type"]
        self.profile.save()
        form = self.form(["historic-type"])
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_post_is_rejected_and_other_details_survive(self):
        invalid = self.form(["made-up-code"])
        self.assertFalse(invalid.is_valid())
        self.assertIn("foundation_types", invalid.errors)
        form = self.form(["other"], **{"profile-foundation": "Reclaimed timber in study"})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.foundation, "Reclaimed timber in study")

    def test_clearing_selections_does_not_remove_notes(self):
        self.profile.foundation_types = ["block"]
        self.profile.save()
        form = self.form([])
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.foundation_types, [])
        self.assertEqual(self.profile.foundation, "Original room-by-room notes")

    def test_none_cannot_be_combined_with_material(self):
        form = self.form(["none", "slab"])
        self.assertFalse(form.is_valid())
        self.assertIn("foundation_types", form.errors)
        self.assertTrue(self.form(["none"]).is_valid())

    def test_flooring_and_construction_selections_saved_together(self):
        form = self.form(["slab", "block"], **{"profile-flooring_types": ["carpet", "wood"], "profile-flooring": "Wood downstairs"})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.flooring_types, ["carpet", "wood"])
        self.assertEqual(self.profile.foundation_types, ["slab", "block"])

    def test_configurable_selection_limit(self):
        from django.test import override_settings
        with override_settings(PROPERTY_FOUNDATION_MAX_SELECTIONS=1):
            form = self.form(["slab", "raised"])
            self.assertFalse(form.is_valid())
            self.assertIn("foundation_types", form.errors)
            self.assertTrue(self.form(["slab"]).is_valid())
