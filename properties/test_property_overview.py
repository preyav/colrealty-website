"""Synthetic overview tests: school persistence, atomic validation and unit preservation."""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from common.audit.models import AuditEvent
from .models import Property, PropertyProfile, PropertyUnit
from .editor import occupancy_summary
from .editor_display import profile_sections


class PropertyOverviewTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(username='overview-staff', is_staff=True)
        self.client.force_login(self.staff)

    def values(self, **updates):
        data = dict(street_address='100 Synthetic Example Ln',city='Austin',state='TX',zip_code='78701',county='Travis',property_type='single_family_residential',management_status='prospect',bedrooms='3',bathrooms_full='2',bathrooms_half='0',sqft='1800')
        for prefix, maximum in [('documents',100),('certifications',30)]:
            data.update({prefix+'-TOTAL_FORMS':'0',prefix+'-INITIAL_FORMS':'0',prefix+'-MIN_NUM_FORMS':'0',prefix+'-MAX_NUM_FORMS':str(maximum)})
        data.update(updates)
        return data

    def test_create_allows_blank_schools_and_does_not_claim_occupancy(self):
        response = self.client.get(reverse('portal:create_property'))
        self.assertContains(response,'Property Overview')
        self.assertContains(response,'Not recorded')
        self.assertEqual(len(response.context['property_sections']),8)
        self.assertContains(response,'Location &amp; School Information')
        response = self.client.post(reverse('portal:create_property'),self.values())
        self.assertEqual(response.status_code,302)
        self.assertEqual(Property.objects.get().profile.school_district,'')

    def test_school_information_saves_displays_and_is_audited(self):
        data=self.values(**{'profile-school_district':'Synthetic District','profile-elementary_school':'Example Elementary','profile-middle_school':'Example Middle','profile-high_school':'Example High','profile-elementary_school_other':'Alternative Elementary','profile-middle_school_other':'Alternative Middle','profile-high_school_other':'Alternative High'})
        response=self.client.post(reverse('portal:create_property'),data)
        self.assertEqual(response.status_code,302)
        prop=Property.objects.get()
        self.assertEqual(prop.profile.high_school,'Example High')
        self.assertEqual(prop.profile.high_school_other,'Alternative High')
        fields=[f for section in profile_sections(prop) for f in section['fields']]
        self.assertIn('Synthetic District',[f['value'] for f in fields])
        self.assertTrue(AuditEvent.objects.filter(entity_type='PropertyProfile').exists())
        response=self.client.get(reverse('portal:edit_property',args=[prop.pk]))
        self.assertContains(response,'Synthetic District')

    def test_exact_school_fields_and_four_help_buttons(self):
        response = self.client.get(reverse('portal:create_property'))
        form = response.context['profile_form']
        names = [name for name in form.fields if 'school' in name]
        self.assertEqual(set(names), {'school_district','out_of_state_school_district','elementary_school','elementary_school_other','middle_school','middle_school_other','high_school','high_school_other'})
        self.assertContains(response,'class="school-help-button btn-primary"',count=4)
        self.assertContains(response,'Out of State School District Help')
        self.assertContains(response,'Other High School Help')
        self.assertContains(response,'18 Central Texas counties')
        self.assertNotContains(response,'School Information Verified On')
        self.assertNotContains(response,'School Information Source')

    def test_other_district_requires_manual_district_name(self):
        response=self.client.post(reverse('portal:create_property'),self.values(**{'profile-school_district':'Other'}))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Out of State School District is required when School District is Other.')
        self.assertFalse(Property.objects.exists())

    def test_other_school_requires_manual_school_name(self):
        for school in ('elementary_school','middle_school','high_school'):
            response=self.client.post(reverse('portal:create_property'),self.values(**{'profile-'+school:'Outside School District'}))
            self.assertEqual(response.status_code,200)
            self.assertTrue(response.context['profile_form'].has_error(school+'_other'))
            self.assertFalse(Property.objects.exists())

    def test_school_changes_preserve_unit_status(self):
        self.client.post(reverse('portal:create_property'),self.values())
        prop=Property.objects.get(); unit=prop.units.get()
        unit.status='occupied';unit.save()
        data=self.values(**{'profile-school_district':'Updated Synthetic District'})
        response=self.client.post(reverse('portal:edit_property',args=[prop.pk]),data)
        self.assertEqual(response.status_code,302)
        unit.refresh_from_db();self.assertEqual(unit.status,'occupied')
        self.assertEqual(occupancy_summary(prop),[{'label':'Occupied','count':1}])

    def test_multi_unit_summary_keeps_all_unit_states(self):
        prop=Property.objects.create(street_address='Synthetic Building',city='Austin',state='TX',zip_code='78701',county='Travis',property_type='other',is_multi_unit=True)
        for index,status in enumerate(['occupied','occupied','vacant','maintenance']):
            PropertyUnit.objects.create(property=prop,unit_number=str(index),status=status)
        self.assertEqual(occupancy_summary(prop),[{'label':'Vacant','count':1},{'label':'Occupied','count':2},{'label':'Maintenance','count':1}])

    def test_nonstaff_cannot_edit_property(self):
        user=get_user_model().objects.create_user(username='ordinary-user')
        self.client.force_login(user)
        response=self.client.post(reverse('portal:create_property'),self.values())
        self.assertEqual(response.status_code,302)
        self.assertFalse(Property.objects.exists())

    def test_school_text_is_escaped(self):
        self.client.post(reverse('portal:create_property'),self.values(**{'profile-elementary_school':'<script>alert(1)</script>'}))
        prop=Property.objects.get()
        response=self.client.get(reverse('portal:edit_property',args=[prop.pk]))
        self.assertContains(response,'&lt;script&gt;')
        self.assertNotContains(response,'<script>alert(1)</script>')
