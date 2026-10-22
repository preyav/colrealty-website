"""Synthetic regression checks for property grouping and ownership editing."""
from importlib import import_module
from django.apps import apps
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from .models import Property, PropertyMarketingDefaults
from .editor_sections import SECTION_ORDER, CORE_FIELDS, PROFILE_SECTIONS, MARKETING_SECTIONS
from .editor_display import profile_sections
from .test_property_overview import PropertyOverviewTests


class OwnershipManagementTests(TestCase):
    setUp = PropertyOverviewTests.setUp
    values = PropertyOverviewTests.values

    def test_all_sections_and_fields_appear_once(self):
        response = self.client.get(reverse('portal:create_property'))
        sections = response.context['property_sections']
        self.assertEqual([s['title'] for s in sections], SECTION_ORDER)
        names = [f.name for s in sections for f in s['fields']]
        # Feature selectors are rendered by their corresponding detail partials.
        expected = CORE_FIELDS + ['notes'] + [f[0] for groups in (PROFILE_SECTIONS, MARKETING_SECTIONS) for group in groups.values() for f in group]
        self.assertCountEqual(names, expected)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual([f.name for f in sections[0]['fields']], ['occupancy_status', 'ownership_type', 'assigned_manager_name', 'listing_agent_name', 'co_listing_agent_name', 'office_notes'])
        markup = response.content.decode().split('id="section-0"', 1)[1].split('</section>', 1)[0]
        self.assertNotIn('property-field wide', markup)
        for title in SECTION_ORDER:
            self.assertContains(response, title.replace('&', '&amp;'))
        self.assertContains(response, 'Document Links')
        self.assertContains(response, 'Energy Certifications')

    def test_choices_are_exact_and_no_occupancy_is_assumed(self):
        response = self.client.get(reverse('portal:create_property'))
        form = response.context['profile_form']
        self.assertEqual([label for value, label in form.fields['occupancy_status'].choices if value], ['Vacant', 'Owner Occupied', 'Tenant Occupied', 'Other'])
        self.assertEqual([label for value, label in form.fields['ownership_type'].choices if value], ['Freehold', 'Condominium', 'Leasehold', 'Other'])
        self.client.post(reverse('portal:create_property'), self.values())
        self.assertEqual(Property.objects.get().profile.occupancy_status, '')

    def test_each_occupancy_saves_without_changing_management_or_units(self):
        self.client.post(reverse('portal:create_property'), self.values())
        prop = Property.objects.get()
        unit = prop.units.get()
        unit.status = 'occupied'
        unit.save()
        for value in ('vacant', 'owner_occupied', 'tenant_occupied', 'other'):
            response = self.client.post(reverse('portal:edit_property', args=[prop.pk]), self.values(**{'profile-occupancy_status': value, 'profile-ownership_type': 'leasehold'}))
            self.assertEqual(response.status_code, 302)
            prop.refresh_from_db(); unit.refresh_from_db()
            self.assertEqual(prop.profile.occupancy_status, value)
            self.assertEqual(prop.profile.ownership_type, 'leasehold')
            self.assertEqual(prop.management_status, 'prospect')
            self.assertEqual(unit.status, 'occupied')

    def test_invalid_occupancy_cannot_save(self):
        response = self.client.post(reverse('portal:create_property'), self.values(**{'profile-occupancy_status': 'invalid'}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Property.objects.exists())

    def test_free_text_names_and_notes_preserve_staff_links(self):
        self.client.post(reverse('portal:create_property'), self.values())
        prop = Property.objects.get()
        marketing = prop.marketing_defaults
        marketing.assigned_manager = self.staff
        marketing.save()
        data = self.values(**{'marketing-assigned_manager_name': 'Example Manager', 'marketing-listing_agent_name': 'External Listing Agent', 'marketing-co_listing_agent_name': 'Example Co-agent', 'marketing-office_notes': '<script>example</script>'})
        response = self.client.post(reverse('portal:edit_property', args=[prop.pk]), data)
        self.assertEqual(response.status_code, 302)
        marketing.refresh_from_db()
        self.assertEqual(marketing.assigned_manager_id, self.staff.pk)
        self.assertEqual(marketing.listing_agent_name, 'External Listing Agent')
        self.assertEqual(marketing.co_listing_agent_name, 'Example Co-agent')
        self.assertEqual(marketing.assigned_manager_name, 'Example Manager')
        response = self.client.get(reverse('portal:edit_property', args=[prop.pk]))
        self.assertContains(response, '&lt;script&gt;example&lt;/script&gt;')
        self.assertNotContains(response, '<script>example</script>')
        prop = Property.objects.get(pk=prop.pk)
        self.assertEqual(profile_sections(prop)[0]['title'], 'Ownership & Management')

    def test_migration_copies_names_once_and_preserves_links(self):
        self.client.post(reverse('portal:create_property'), self.values())
        marketing = PropertyMarketingDefaults.objects.get()
        self.staff.first_name = 'Example'; self.staff.last_name = 'Manager'; self.staff.save()
        marketing.assigned_manager = self.staff
        marketing.listing_agent = self.staff
        marketing.listing_agent_name = 'Previously Entered Agent'
        marketing.save()
        migration = import_module('properties.migrations.0016_ownership_management_fields')
        migration.copy_existing_staff_names(apps, connection.schema_editor())
        marketing.refresh_from_db()
        self.assertEqual(marketing.assigned_manager_name, 'Example Manager')
        self.assertEqual(marketing.assigned_manager_id, self.staff.pk)
        self.assertEqual(marketing.listing_agent_name, 'Previously Entered Agent')
