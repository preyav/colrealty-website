from django.template.loader import render_to_string
from django.test import TestCase
from .editor_forms import PropertyProfileForm
from .editor_display import profile_sections
from .models import RoofOption, Property, PropertyProfile


class RoofTests(TestCase):
    def setUp(self):
        self.property = Property.objects.create(street_address="100 Test Ln", city="Austin", state="TX", zip_code="78701")
        self.profile = PropertyProfile.objects.create(property=self.property, roof="Original room-by-room notes")

    def form(self, codes, **changes):
        data = {"profile-roof_types": codes, "profile-roof": self.profile.roof}
        data.update(changes)
        return PropertyProfileForm(data, instance=self.profile, prefix="profile")

    def test_multiple_types_save_reopen_and_preserve_legacy(self):
        form = self.form(["metal", "shingle"])
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.roof_types, ["metal", "shingle"])
        self.assertEqual(self.profile.roof, "Original room-by-room notes")
        reopened = PropertyProfileForm(instance=self.profile, prefix="profile")
        self.assertEqual(reopened["roof_types"].value(), ["metal", "shingle"])
        fields = [f for s in profile_sections(self.property) for f in s["fields"] if f["label"] == "Roof"]
        self.assertEqual(fields[0]["value"], "Metal, Shingle; Original room-by-room notes")

    def test_admin_added_label_is_rendered_and_can_be_saved(self):
        RoofOption.objects.create(code="custom-feature", label="Custom Feature")
        form = self.form(["custom-feature"])
        self.assertTrue(form.is_valid(), form.errors)
        html = render_to_string("portal/property_roof.html", {"profile_form": form, "field": form["roof"]})
        self.assertIn("Custom Feature", html)
        self.assertIn('type="checkbox"', html)
        self.assertRegex(html, r'value="custom-feature"[^>]* checked')

    def test_retired_choices_preserved_only_for_existing_property(self):
        RoofOption.objects.filter(code="shingle").update(is_active=False)
        self.profile.roof_types = ["shingle"]
        self.profile.save()
        form = self.form(["shingle"])
        self.assertTrue(form.is_valid(), form.errors)
        new = PropertyProfileForm({"roof_types": ["shingle"]})
        self.assertFalse(new.is_valid())
        self.assertIn("roof_types", new.errors)

    def test_deleted_vocabulary_keeps_saved_selection(self):
        self.profile.roof_types = ["historic-type"]
        self.profile.save()
        form = self.form(["historic-type"])
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_post_is_rejected_and_other_details_survive(self):
        invalid = self.form(["made-up-code"])
        self.assertFalse(invalid.is_valid())
        self.assertIn("roof_types", invalid.errors)
        form = self.form(["other"], **{"profile-roof": "Reclaimed timber in study"})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.roof, "Reclaimed timber in study")

    def test_clearing_selections_does_not_remove_notes(self):
        self.profile.roof_types = ["tile"]
        self.profile.save()
        form = self.form([])
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.roof_types, [])
        self.assertEqual(self.profile.roof, "Original room-by-room notes")

    def test_none_cannot_be_combined_with_material(self):
        form = self.form(["none", "metal"])
        self.assertFalse(form.is_valid())
        self.assertIn("roof_types", form.errors)
        self.assertTrue(self.form(["none"]).is_valid())

    def test_flooring_and_construction_selections_saved_together(self):
        form = self.form(["metal", "tile"], **{"profile-flooring_types": ["carpet", "wood"], "profile-flooring": "Wood downstairs"})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.flooring_types, ["carpet", "wood"])
        self.assertEqual(self.profile.roof_types, ["metal", "tile"])

    def test_configurable_selection_limit(self):
        from django.test import override_settings
        with override_settings(PROPERTY_ROOF_MAX_SELECTIONS=1):
            form = self.form(["metal", "shingle"])
            self.assertFalse(form.is_valid())
            self.assertIn("roof_types", form.errors)
            self.assertTrue(self.form(["metal"]).is_valid())

    def test_default_maximum_ten(self):
        codes = list(RoofOption.objects.exclude(code="none").values_list("code", flat=True))[:11]
        form = self.form(codes)
        self.assertFalse(form.is_valid())
        self.assertIn("roof_types", form.errors)
        self.assertTrue(self.form(codes[:10]).is_valid())
