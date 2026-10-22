from django.template.loader import render_to_string
from django.test import TestCase
from .editor_forms import PropertyProfileForm
from .editor_display import profile_sections
from .models import ConstructionMaterialOption, Property, PropertyProfile


class ConstructionMaterialTests(TestCase):
    def setUp(self):
        self.property = Property.objects.create(street_address="100 Test Ln", city="Austin", state="TX", zip_code="78701")
        self.profile = PropertyProfile.objects.create(property=self.property, construction_materials="Original room-by-room notes")

    def form(self, codes, **changes):
        data = {"profile-construction_material_types": codes, "profile-construction_materials": self.profile.construction_materials}
        data.update(changes)
        return PropertyProfileForm(data, instance=self.profile, prefix="profile")

    def test_multiple_types_save_reopen_and_preserve_legacy(self):
        form = self.form(["brick", "stone"])
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.construction_material_types, ["brick", "stone"])
        self.assertEqual(self.profile.construction_materials, "Original room-by-room notes")
        reopened = PropertyProfileForm(instance=self.profile, prefix="profile")
        self.assertEqual(reopened["construction_material_types"].value(), ["brick", "stone"])
        fields = [f for s in profile_sections(self.property) for f in s["fields"] if f["label"] == "Construction Materials"]
        self.assertEqual(fields[0]["value"], "Brick, Stone; Original room-by-room notes")

    def test_admin_added_label_is_rendered_and_can_be_saved(self):
        ConstructionMaterialOption.objects.create(code="custom-feature", label="Custom Feature")
        form = self.form(["custom-feature"])
        self.assertTrue(form.is_valid(), form.errors)
        html = render_to_string("portal/property_construction_materials.html", {"profile_form": form, "field": form["construction_materials"]})
        self.assertIn("Custom Feature", html)
        self.assertIn('type="checkbox"', html)
        self.assertRegex(html, r'value="custom-feature"[^>]* checked')

    def test_retired_choices_preserved_only_for_existing_property(self):
        ConstructionMaterialOption.objects.filter(code="stone").update(is_active=False)
        self.profile.construction_material_types = ["stone"]
        self.profile.save()
        form = self.form(["stone"])
        self.assertTrue(form.is_valid(), form.errors)
        new = PropertyProfileForm({"construction_material_types": ["stone"]})
        self.assertFalse(new.is_valid())
        self.assertIn("construction_material_types", new.errors)

    def test_deleted_vocabulary_keeps_saved_selection(self):
        self.profile.construction_material_types = ["historic-type"]
        self.profile.save()
        form = self.form(["historic-type"])
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_post_is_rejected_and_other_details_survive(self):
        invalid = self.form(["made-up-code"])
        self.assertFalse(invalid.is_valid())
        self.assertIn("construction_material_types", invalid.errors)
        form = self.form(["other"], **{"profile-construction_materials": "Reclaimed timber in study"})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.construction_materials, "Reclaimed timber in study")

    def test_clearing_selections_does_not_remove_notes(self):
        self.profile.construction_material_types = ["frame"]
        self.profile.save()
        form = self.form([])
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.construction_material_types, [])
        self.assertEqual(self.profile.construction_materials, "Original room-by-room notes")

    def test_none_cannot_be_combined_with_material(self):
        form = self.form(["none", "brick"])
        self.assertFalse(form.is_valid())
        self.assertIn("construction_material_types", form.errors)
        self.assertTrue(self.form(["none"]).is_valid())

    def test_flooring_and_construction_selections_saved_together(self):
        form = self.form(["brick", "frame"], **{"profile-flooring_types": ["carpet", "wood"], "profile-flooring": "Wood downstairs"})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.flooring_types, ["carpet", "wood"])
        self.assertEqual(self.profile.construction_material_types, ["brick", "frame"])
