"""Property profile regressions, including existing unit/lease preservation."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from common.audit.models import AuditEvent
from leasing.models import Lease
from .models import (
    Property,
    PropertyUnit,
    PropertyProfile,
    PropertyMarketingDefaults,
    PropertyDocumentLink,
    PropertyEnergyCertification,
)
from .editor_forms import PropertyRecordForm, PropertyProfileForm, PropertyMarketingForm


class PropertyEditorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            username="property-reviewer", password="test-only", is_staff=True
        )

    def setUp(self):
        self.client.force_login(self.staff)

    def values(self, **changes):
        data = {
            "street_address": "100 Test Property Ln",
            "city": "Austin",
            "state": "TX",
            "zip_code": "78701",
            "county": "Travis",
            "subdivision": "",
            "property_type": "single_family_residential",
            "management_status": "active",
            "year_built": "2004",
            "bedrooms": "3",
            "bathrooms_full": "2",
            "bathrooms_half": "1",
            "sqft": "1800",
            "documents-TOTAL_FORMS": "1",
            "documents-INITIAL_FORMS": "0",
            "documents-MIN_NUM_FORMS": "0",
            "documents-MAX_NUM_FORMS": "100",
            "documents-0-category": "other",
            "certifications-TOTAL_FORMS": "1",
            "certifications-INITIAL_FORMS": "0",
            "certifications-MIN_NUM_FORMS": "0",
            "certifications-MAX_NUM_FORMS": "30",
            "certifications-0-status": "",
        }
        data.update(changes)
        return data

    def create(self, **changes):
        response = self.client.post(
            reverse("portal:create_property"), self.values(**changes)
        )
        self.assertEqual(
            response.status_code,
            302,
            response.context
            and [
                (name, response.context[name].errors)
                for name in (
                    "form",
                    "profile_form",
                    "marketing_form",
                    "document_formset",
                    "certification_formset",
                )
            ],
        )
        return Property.objects.latest("pk")

    def test_get_has_eight_sections_and_two_column_layout(self):
        response = self.client.get(reverse("portal:create_property"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["property_sections"]), 8)
        self.assertContains(response, "grid-template-columns:repeat(2,minmax(0,1fr))")
        self.assertContains(response, "id_profile-has_hoa")
        self.assertContains(response, "documents-empty")

    def test_optional_sections_can_be_empty_and_primary_unit_is_synced(self):
        obj = self.create()
        self.assertEqual(obj.profile.association_name, "")
        self.assertEqual(obj.document_links.count(), 0)
        self.assertEqual(obj.energy_certifications.count(), 0)
        unit = obj.units.get()
        self.assertEqual(
            (unit.bathrooms_full, unit.bathrooms_half, unit.baths),
            (2, 1, Decimal("2.5")),
        )

    def test_sections_document_certification_and_marketing_defaults_roundtrip(self):
        obj = self.create(
            **{
                "profile-ownership_type": "freehold",
                "profile-roof": "Metal",
                "profile-water_source": "Municipal",
                "profile-solar": "true",
                "profile-solar_ownership": "owned",
                "profile-has_hoa": "true",
                "profile-association_name": "Test Association",
                "profile-association_fee": "125",
                "profile-association_fee_frequency": "monthly",
                "marketing-showing_contact_email": "test@example.com",
                "marketing-assigned_manager_name": self.staff.get_username(),
                "marketing-public_remarks": "A spacious home.",
                "documents-0-title": "Inspection",
                "documents-0-url": "https://drive.google.com/file/d/test/view",
                "certifications-0-verification_type": "Energy Star",
                "certifications-0-status": "verified",
                "certifications-0-year": str(timezone.localdate().year),
            }
        )
        self.assertEqual(obj.profile.association_fee, Decimal("125"))
        self.assertEqual(obj.marketing_defaults.assigned_manager_name, self.staff.get_username())
        self.assertEqual(obj.document_links.get().title, "Inspection")
        self.assertEqual(
            obj.energy_certifications.get().verification_type, "Energy Star"
        )
        detail = self.client.get(reverse("portal:property_detail", args=[obj.pk]))
        self.assertContains(detail, "Freehold")
        self.assertContains(detail, "$125.00")
        self.assertContains(detail, "Inspection")
        self.assertContains(detail, "test@example.com")
        self.assertEqual(obj.units.count(), 1)

    def test_invalid_document_saves_nothing(self):
        response = self.client.post(
            reverse("portal:create_property"),
            self.values(
                **{
                    "documents-0-title": "Bad Link",
                    "documents-0-url": "javascript:alert(1)",
                }
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Property.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_mult_unit_create_does_not_invent_a_primary_unit(self):
        obj = self.create(
            property_type="other",
            property_type_other="Duplex",
            is_multi_unit="on",
            bedrooms="",
            bathrooms_full="",
            bathrooms_half="",
            sqft="",
        )
        self.assertTrue(obj.is_multi_unit)
        self.assertEqual(obj.units.count(), 0)

    def test_mult_unit_edit_preserves_individual_units_and_leases(self):
        obj = self.create(
            property_type="other",
            property_type_other="Duplex",
            is_multi_unit="on",
            bedrooms="",
            bathrooms_full="",
            bathrooms_half="",
            sqft="",
        )
        first = PropertyUnit.objects.create(
            property=obj,
            unit_number="A",
            beds=2,
            baths=1,
            bathrooms_full=1,
            bathrooms_half=0,
            sqft=900,
        )
        second = PropertyUnit.objects.create(
            property=obj,
            unit_number="B",
            beds=3,
            baths=2,
            bathrooms_full=2,
            bathrooms_half=0,
            sqft=1200,
        )
        lease = Lease.objects.create(
            unit=first,
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            monthly_rent=1500,
            status="active",
        )
        code = obj.property_code
        response = self.client.post(
            reverse("portal:edit_property", args=[obj.pk]),
            self.values(
                property_type="other",
                property_type_other="Duplex",
                is_multi_unit="on",
                bedrooms="9",
                bathrooms_full="8",
                bathrooms_half="7",
                sqft="9999",
                street_address="Updated Test Address",
            ),
        )
        self.assertEqual(response.status_code, 302)
        first.refresh_from_db()
        second.refresh_from_db()
        obj.refresh_from_db()
        lease.refresh_from_db()
        self.assertEqual(
            (first.beds, first.sqft, second.beds, second.sqft), (2, 900, 3, 1200)
        )
        self.assertEqual(lease.unit_id, first.pk)
        self.assertEqual(obj.property_code, code)
        self.assertEqual(obj.units.count(), 2)

    def test_cannot_disable_multi_unit_with_multiple_units(self):
        obj = self.create(
            property_type="other",
            property_type_other="Duplex",
            is_multi_unit="on",
            bedrooms="",
            bathrooms_full="",
            bathrooms_half="",
            sqft="",
        )
        PropertyUnit.objects.create(property=obj, unit_number="A")
        PropertyUnit.objects.create(property=obj, unit_number="B")
        response = self.client.post(
            reverse("portal:edit_property", args=[obj.pk]), self.values()
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("is_multi_unit", response.context["form"].errors)
        obj.refresh_from_db()
        self.assertTrue(obj.is_multi_unit)

    def test_single_unit_edit_preserves_unit_and_lease_identity(self):
        obj = self.create()
        unit = obj.units.get()
        lease = Lease.objects.create(
            unit=unit,
            start_date=date(2026, 1, 1),
            end_date=date(2027, 1, 1),
            monthly_rent=1500,
        )
        response = self.client.post(
            reverse("portal:edit_property", args=[obj.pk]),
            self.values(bedrooms="4", sqft="2100", bathrooms_half="0"),
        )
        self.assertEqual(response.status_code, 302)
        unit.refresh_from_db()
        lease.refresh_from_db()
        self.assertEqual(unit.sqft, 2100)
        self.assertEqual(lease.unit_id, unit.pk)
        self.assertEqual(obj.units.count(), 1)

    def test_tampered_document_id_cannot_reparent_another_property(self):
        first = self.create()
        second = self.create(street_address="200 Test Property Ln")
        doc = PropertyDocumentLink.objects.create(
            property=first, title="Private agreement", url="https://example.com/doc"
        )
        data = self.values(
            **{
                "documents-INITIAL_FORMS": "1",
                "documents-0-id": str(doc.pk),
                "documents-0-title": "Move it",
                "documents-0-url": doc.url,
            }
        )
        response = self.client.post(
            reverse("portal:edit_property", args=[second.pk]), data
        )
        self.assertEqual(response.status_code, 200)
        doc.refresh_from_db()
        self.assertEqual((doc.property_id, doc.title), (first.pk, "Private agreement"))

    def test_reference_entries_can_be_edited_and_removed(self):
        obj = self.create(
            **{
                "documents-0-title": "Old inspection",
                "documents-0-url": "https://example.com/inspection",
            }
        )
        doc = obj.document_links.get()
        data = self.values(
            **{
                "documents-INITIAL_FORMS": "1",
                "documents-0-id": str(doc.pk),
                "documents-0-title": "New inspection",
                "documents-0-url": doc.url,
            }
        )
        self.assertEqual(
            self.client.post(
                reverse("portal:edit_property", args=[obj.pk]), data
            ).status_code,
            302,
        )
        doc.refresh_from_db()
        self.assertEqual(doc.title, "New inspection")
        data["documents-0-DELETE"] = "on"
        self.assertEqual(
            self.client.post(
                reverse("portal:edit_property", args=[obj.pk]), data
            ).status_code,
            302,
        )
        self.assertEqual(obj.document_links.count(), 0)

    def test_access_code_is_not_in_audit_or_detail_page(self):
        obj = self.create(**{"marketing-access_code": "secret-test-code"})
        self.assertEqual(obj.marketing_defaults.access_code, "secret-test-code")
        self.assertNotIn(
            "secret-test-code",
            str(
                list(AuditEvent.objects.values("old_values", "new_values", "metadata"))
            ),
        )
        self.assertNotContains(
            self.client.get(reverse("portal:property_detail", args=[obj.pk])),
            "secret-test-code",
        )

    def test_atomic_failure_rolls_back_every_saved_record(self):
        with patch(
            "properties.editor.save_children", side_effect=RuntimeError("test rollback")
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse("portal:create_property"), self.values())
        self.assertEqual(Property.objects.count(), 0)
        self.assertEqual(PropertyProfile.objects.count(), 0)
        self.assertEqual(PropertyUnit.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_core_validation_rejects_bad_zip_coordinates_year_area_and_negative_rooms(
        self,
    ):
        for field, value in [
            ("zip_code", "ABC"),
            ("latitude", "91"),
            ("year_built", "9999"),
            ("sqft", "0"),
            ("bedrooms", "-1"),
            ("state", "ZZ"),
        ]:
            with self.subTest(field=field):
                form = PropertyRecordForm(self.values(**{field: value}))
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
        self.assertFalse(PropertyRecordForm(self.values(latitude="30.2")).is_valid())

    def test_profile_business_rules(self):
        examples = [
            ("association_name", {"has_hoa": "true"}),
            (
                "association_fee_frequency",
                {
                    "has_hoa": "true",
                    "association_name": "HOA",
                    "association_fee": "100",
                },
            ),
            ("association_fee", {"association_fee": "-1"}),
            ("tax_year", {"annual_tax_amount": "1200"}),
            ("tax_rate", {"tax_rate": "101"}),
            ("waterfront", {"waterfront": "false", "water_body_name": "Lake"}),
            ("pool_features", {"has_pool": "false", "pool_features": "Private pool"}),
            ("solar_ownership", {"solar": "false", "solar_ownership": "leased"}),
        ]
        for field, values in examples:
            with self.subTest(field=field):
                form = PropertyProfileForm(values)
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_marketing_validation_and_name_length(self):
        user = get_user_model().objects.create_user(username="ordinary-user")
        form = PropertyMarketingForm(
            {
                "assigned_manager_name": "x" * 256,
                "showing_contact_email": "bad-email",
                "showing_contact_phone": "abc",
                "allow_address_display": "on",
                "branded_tour_url": "ftp://example.com",
            }
        )
        self.assertFalse(form.is_valid())
        for name in (
            "assigned_manager_name",
            "showing_contact_email",
            "showing_contact_phone",
            "allow_address_display",
            "branded_tour_url",
        ):
            self.assertIn(name, form.errors)

    def test_staff_permissions_are_required(self):
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("portal:create_property")).status_code, 302
        )
        self.assertEqual(
            self.client.post(
                reverse("portal:create_property"), self.values()
            ).status_code,
            302,
        )
        self.assertEqual(Property.objects.count(), 0)

    def test_existing_property_without_profile_can_be_viewed_and_enriched(self):
        obj = Property.objects.create(
            street_address="Existing Home",
            city="Austin",
            state="TX",
            zip_code="78701",
            county="Travis",
            subdivision="",
            property_type="single_family_residential",
            bedrooms=3,
            bathrooms_full=2,
            bathrooms_half=0,
            sqft=1500,
        )
        unit = PropertyUnit.objects.create(property=obj, sqft=1500)
        self.assertEqual(
            self.client.get(
                reverse("portal:property_detail", args=[obj.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("portal:edit_property", args=[obj.pk])).status_code,
            200,
        )
        response = self.client.post(
            reverse("portal:edit_property", args=[obj.pk]),
            self.values(**{"profile-roof": "Shingle"}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(obj.profile.roof, "Shingle")
        self.assertEqual(obj.units.get().pk, unit.pk)

    def test_existing_inactive_manager_link_is_preserved_when_name_changes(self):
        manager = get_user_model().objects.create_user(
            username="former-manager", is_staff=True, is_active=False
        )
        obj = self.create()
        PropertyMarketingDefaults.objects.filter(property=obj).update(assigned_manager=manager)
        form = PropertyMarketingForm(
            {"assigned_manager_name": "Replacement Display Name"},
            instance=PropertyMarketingDefaults.objects.get(property=obj),
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.assigned_manager_id, manager.pk)
        self.assertEqual(saved.assigned_manager_name, "Replacement Display Name")

    def test_public_defaults_do_not_publish_or_create_marketing_records(self):
        from listings.models import Listing
        from rentals.models import Rental

        before = (Listing.objects.count(), Rental.objects.count())
        self.create(
            **{
                "marketing-allow_public_display": "on",
                "marketing-allow_address_display": "on",
                "marketing-public_remarks": "Marketing draft only.",
            }
        )
        self.assertEqual((Listing.objects.count(), Rental.objects.count()), before)

    def test_tampered_delete_cannot_remove_another_property_document(self):
        first = self.create()
        second = self.create(street_address="Second home")
        doc = PropertyDocumentLink.objects.create(
            property=first, title="Agreement", url="https://example.com/doc"
        )
        response = self.client.post(
            reverse("portal:edit_property", args=[second.pk]),
            self.values(
                **{
                    "documents-INITIAL_FORMS": "1",
                    "documents-0-id": str(doc.pk),
                    "documents-0-DELETE": "on",
                }
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            PropertyDocumentLink.objects.filter(pk=doc.pk, property=first).exists()
        )
