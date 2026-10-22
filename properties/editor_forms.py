"""Validated staff property editor; public marketing never exposes private notes."""

import math
from .address_fields import ADDRESS_FIELDS, ADDRESS_LABELS, ADDRESS_REQUIRED, ADDRESS_ORDER, ADDRESS_HELP, DIRECTION_CHOICES, STREET_SUFFIX_CHOICES, compose_address
import json
from .ownership_choices import OWNERSHIP_CHOICES, LEGACY_OWNERSHIP_CHOICES, PROPERTY_OWNERSHIP_DEFAULTS
import re
from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils import timezone
from portal.forms import PropertyForm
from .models import (
    Property,
    PropertyProfile,
    FlooringOption,
    InteriorFeatureOption,
    ExteriorFeatureOption,
    ConstructionMaterialOption,
    FoundationOption,
    RoofOption,
    PropertyMarketingDefaults,
    PropertyDocumentLink,
    PropertyEnergyCertification,
)
from .equipment_choices import EQUIPMENT_CHOICES, SELECTION_LIMITS, PROPERTY_CONDITION_CHOICES
from .feature_dependencies import FEATURE_PAIRS, dependent_visible
from .section_remarks import validate_section_remarks, remarks_for_field
from .marketing_feature_choices import MARKETING_TEXT_FEATURE_CHOICES
from .showing_requirement_choices import SHOWING_REQUIREMENT_CHOICES

# Reuse existing stored codes for matching labels; retain legacy values in the
# form's existing saved-selection handling. Settings overrides remain supported.
_showing_existing = {
    label.casefold(): code
    for code, label in MARKETING_TEXT_FEATURE_CHOICES.get('showing_requirements', {}).get('choices', [])
}
MARKETING_TEXT_FEATURE_CHOICES['showing_requirements'] = {
    'label': 'Showing Requirements (max 25)',
    'limit': 25,
    'choices': [
        (_showing_existing.get(label.casefold(), code), label)
        for code, label in SHOWING_REQUIREMENT_CHOICES
    ],
}
from .water_choices import WATER_BODY_NAMES
from .text_feature_choices import TEXT_FEATURE_CHOICES, APPLICATION_SINGLE_CHOICES, TextFeatureChoiceField, decode_features
from .editor_sections import (
    PROFILE_SECTIONS,
    MARKETING_SECTIONS,
    CORE_FIELDS,
    CORE_SECTIONS,
    SECTION_ORDER,
)


def validate_year(value):
    if value is not None and not 1000 <= value <= timezone.localdate().year + 1:
        raise ValidationError("Enter a year between 1000 and next year.")


def set_dropdown_prompts(form):
    """Replace empty single-select labels without changing their stored values."""
    for name, field in form.fields.items():
        if not isinstance(field.widget, forms.Select) or isinstance(field.widget, forms.SelectMultiple):
            continue
        prompt = "Select One"
        if isinstance(field, forms.ModelChoiceField):
            if field.empty_label is not None:
                field.empty_label = prompt
            continue
        null_boolean = isinstance(field.widget, forms.NullBooleanSelect)
        choices = [
            (value, prompt if value in ("", None) or (null_boolean and value == "unknown") else text)
            for value, text in field.widget.choices
        ]
        if null_boolean:
            field.widget.choices = choices
        elif hasattr(field, "choices"):
            field.choices = choices
        else:
            field.widget.choices = choices


class PropertyRecordForm(PropertyForm):
    class Meta(PropertyForm.Meta):
        fields = list(PropertyForm.Meta.fields) + ["main_level_bedrooms", "other_level_beds"] + [name for name, _, _ in ADDRESS_FIELDS]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "street_address": "Street Address",
            "unit_number": "Unit / Suite Number",
            "city": "City",
            "state": "State",
            "zip_code": "ZIP Code",
            "county": "County",
            "subdivision": "Subdivision",
            "property_type": "Property Sub Type",
            "property_type_other": "Other Property Sub Type Details",
            "management_status": "Management Lifecycle",
            "is_multi_unit": "Multi-Unit Property",
            "year_built": "Year Built",
            "bedrooms": "Bedrooms",
            "main_level_bedrooms": "Main Level Bedrooms",
            "other_level_beds": "Other Level Beds",
            "bathrooms_full": "Full Bathrooms",
            "bathrooms_half": "Half Bathrooms",
            "sqft": "Living Area (sq ft)",
            "lot_size_sqft": "Lot Area (sq ft)",
            "latitude": "Latitude",
            "longitude": "Longitude",
            "notes": "Internal Property Notes/Remarks",
        }
        for name, label in labels.items():
            self.fields[name].label = label
        self.property_map_config = {
            "apiKey": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
            "mapId": getattr(settings, "GOOGLE_MAPS_MAP_ID", "DEMO_MAP_ID"),
        }
        self.fields["management_status"].required = True
        self.fields["management_status"].choices = [
            ("", "Select One"),
            *Property.MANAGEMENT_STATUS_CHOICES,
        ]
        if not self.is_bound and not self.instance.pk:
            self.initial["management_status"] = ""
        self.fields['property_type'].choices = [('', 'Select One')] + Property.PROPERTY_TYPE_CHOICES
        self.fields['property_type_other'].widget = forms.Textarea(attrs={
            'class': 'form-control', 'rows': 1, 'maxlength': 100,
            'placeholder': 'Describe the property sub type (up to 100 characters)',
        })
        self.fields['property_type_other'].required = self.is_bound and self.data.get('property_type') == 'other'
        county_choices = list(self.fields['county'].widget.choices)
        if 'other' not in dict(county_choices):
            county_choices.append(('other', 'Other / Outside Texas'))
        self.fields['county'].widget.choices = county_choices
        self.fields['street_address'].required = False
        self.fields['street_address'].widget = forms.HiddenInput()
        for name, label in ADDRESS_LABELS.items():
            if name in self.fields:
                self.fields[name].label = label
        for name in ADDRESS_REQUIRED:
            self.fields[name].required = True
        self.fields['street_dir_prefix'].widget = forms.Select(choices=DIRECTION_CHOICES, attrs={'class': 'form-control'})
        self.fields['street_dir_suffix'].widget = forms.Select(choices=DIRECTION_CHOICES, attrs={'class': 'form-control'})
        suffixes = list(STREET_SUFFIX_CHOICES)
        saved_suffix = self.instance.street_suffix
        if saved_suffix and saved_suffix not in dict(suffixes):
            suffixes.append((saved_suffix, saved_suffix))
        self.fields['street_suffix'].widget = forms.Select(choices=suffixes, attrs={'class': 'form-control'})
        if not self.is_bound and not self.instance.street_name and self.instance.street_address:
            legacy = self.instance.street_address.strip().split(' ', 1)
            if len(legacy) == 2 and any(char.isdigit() for char in legacy[0]):
                self.initial['street_number'], self.initial['street_name'] = legacy
            else:
                self.initial['street_name'] = self.instance.street_address
            self.initial['street_suffix'] = 'none'
        if not self.is_bound and '-' in (self.instance.zip_code or ''):
            self.initial['zip_code'], self.initial['zip_plus_four'] = self.instance.zip_code.split('-', 1)
        self.fields['zip_plus_four'].widget.attrs.update(inputmode='numeric', maxlength=4)
        multi = self.instance.is_multi_unit
        if self.is_bound:
            multi = self.data.get("is_multi_unit") in ("on", "true", "True", "1")
            if self.data.get("property_type") == "single_family_residential":
                multi = False
        self.fields["bedrooms"].required = False
        self.fields["bedrooms"].widget = forms.HiddenInput()
        for name in ("main_level_bedrooms", "other_level_beds", "bathrooms_full", "bathrooms_half", "sqft"):
            self.fields[name].required = not multi
            self.fields[name].widget.attrs.pop("required", None)
        for name in ("sqft", "lot_size_sqft"):
            self.fields[name].min_value = 1
            self.fields[name].widget.attrs["min"] = 1
        self.fields["year_built"].widget.attrs.update(
            min=1000, max=timezone.localdate().year + 1
        )
        self.fields["latitude"].widget.attrs.update(min=-90, max=90)
        self.fields["longitude"].widget.attrs.update(min=-180, max=180)

    def clean(self):
        data = super().clean()
        address = compose_address(data)
        if len(address) > 255:
            self.add_error('street_name', 'The combined street address cannot exceed 255 characters.')
        else:
            data['street_address'] = address
        plus_four = data.get('zip_plus_four', '')
        if plus_four and not re.fullmatch(r'\d{4}', plus_four):
            self.add_error('zip_plus_four', 'Enter exactly four digits.')
        if data.get('zip_code') and re.fullmatch(r'\d{5}', data['zip_code']) and plus_four and re.fullmatch(r'\d{4}', plus_four):
            data['zip_code'] += '-' + plus_four
        if data.get("state") not in dict(self.fields["state"].widget.choices):
            self.add_error("state", "Select a valid state.")
        if data.get("zip_code") and not re.fullmatch(
            r"\d{5}(?:-\d{4})?", data["zip_code"]
        ):
            self.add_error("zip_code", "Enter a five-digit ZIP or ZIP+4.")
        try:
            validate_year(data.get("year_built"))
        except ValidationError as error:
            self.add_error("year_built", error)
        for name in ("sqft", "lot_size_sqft"):
            if data.get(name) is not None and data[name] <= 0:
                self.add_error(name, "Enter a positive area.")
        for name, limit in (("latitude", 90), ("longitude", 180)):
            value = data.get(name)
            if value is not None and (
                not math.isfinite(value) or not -limit <= value <= limit
            ):
                self.add_error(
                    name, f"Enter a coordinate between {-limit} and {limit}."
                )
        if (data.get("latitude") is None) != (data.get("longitude") is None):
            self.add_error(
                None, "Enter both latitude and longitude, or leave both blank."
            )
        if (
            self.instance.pk
            and not data.get("is_multi_unit")
            and self.instance.units.count() > 1
        ):
            self.add_error(
                "is_multi_unit",
                "This property has multiple units. Keep Multi-Unit enabled; manage units individually.",
            )
        if data.get("is_multi_unit"):
            # Property-level facts do not overwrite individual rentable units.
            for name in (
                "unit_number",
                "bedrooms",
                "main_level_bedrooms",
                "other_level_beds",
                "bathrooms_full",
                "bathrooms_half",
                "sqft",
            ):
                data[name] = (
                    getattr(self.instance, name)
                    if self.instance.pk
                    else ("" if name == "unit_number" else None)
                )
        else:
            main = data.get("main_level_bedrooms")
            other = data.get("other_level_beds")
            if main is not None and other is not None:
                total = main + other
                if total > 32767:
                    self.add_error("other_level_beds", "The combined bedroom count cannot exceed 32,767.")
                else:
                    data["bedrooms"] = total
            else:
                data["bedrooms"] = self.instance.bedrooms
        return data


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "form-control")
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["rows"] = 3
            if isinstance(field, forms.URLField):
                field.assume_scheme = "https"
            if isinstance(field, forms.DecimalField):
                field.min_value = 0
                field.widget.attrs["min"] = 0
            if name.endswith("phone"):
                field.widget.attrs["type"] = "tel"
        set_dropdown_prompts(self)

    def clean(self):
        data = super().clean()
        for name, field in self.fields.items():
            value = data.get(name)
            if (
                name.endswith("phone")
                and value
                and (
                    not re.fullmatch(r"[+\d\s().\-xX]{7,40}", value)
                    or not 7 <= len(re.sub(r"\D", "", value)) <= 22
                )
            ):
                self.add_error(
                    name, "Enter a valid phone number, with an optional extension."
                )
            if (
                isinstance(field, forms.URLField)
                and value
                and not value.lower().startswith(("https://", "http://"))
            ):
                self.add_error(name, "Use an HTTPS or HTTP link.")
        return data


def application_section_enabled(form):
    if form.is_bound:
        status = form.data.get('management_status', '')
    else:
        property_obj = getattr(form.instance, 'property', None)
        status = getattr(property_obj, 'management_status', '')
    return str(status).lower() in {'prospect', 'onboarding'}


def conditional_application_requirements(form, names):
    enabled = application_section_enabled(form)
    for name in names:
        field = form.fields.get(name)
        if field is not None and field.required:
            field.widget.attrs['data-lifecycle-required'] = 'true'
            field.required = enabled


class PropertyProfileForm(StyledModelForm):
    heating_types = forms.MultipleChoiceField(required=False, label='Heating', widget=forms.CheckboxSelectMultiple)
    cooling_types = forms.MultipleChoiceField(required=False, label='Cooling', widget=forms.CheckboxSelectMultiple)
    utility_services_types = forms.MultipleChoiceField(required=False, label='Available Utility Services', widget=forms.CheckboxSelectMultiple)
    window_features_types = forms.MultipleChoiceField(required=False, label="Window Features", widget=forms.CheckboxSelectMultiple)
    lot_features_types = forms.MultipleChoiceField(required=False, label='Lot Features', widget=forms.CheckboxSelectMultiple)
    accessibility_features_types = forms.MultipleChoiceField(required=False, label='Accessibility Features', widget=forms.CheckboxSelectMultiple)
    pool_features_types = forms.MultipleChoiceField(required=False, label='Pool Features', widget=forms.CheckboxSelectMultiple)
    spa_features_types = forms.MultipleChoiceField(required=False, label='Spa Features', widget=forms.CheckboxSelectMultiple)
    security_features_types = forms.MultipleChoiceField(required=False, label='Security Features', widget=forms.CheckboxSelectMultiple)
    fireplace_features_types = forms.MultipleChoiceField(required=False, label='Fireplace Features', widget=forms.CheckboxSelectMultiple)
    appliances_types = forms.MultipleChoiceField(required=False, label='Appliances', widget=forms.CheckboxSelectMultiple)

    fema_flood_plain_types = forms.MultipleChoiceField(
        required=True, label="FEMA Flood Plain", widget=forms.CheckboxSelectMultiple,
    )
    level_types = forms.MultipleChoiceField(required=False, label="Levels", widget=forms.CheckboxSelectMultiple)

    roof_types = forms.MultipleChoiceField(
        required=False, label="Roof", widget=forms.CheckboxSelectMultiple,
    )
    foundation_types = forms.MultipleChoiceField(
        required=False, label="Foundation", widget=forms.CheckboxSelectMultiple,
    )
    construction_material_types = forms.MultipleChoiceField(
        required=False, label="Construction Materials", widget=forms.CheckboxSelectMultiple,
        help_text="Select all construction materials that apply. None cannot be combined with another material.",
    )
    exterior_feature_types = forms.MultipleChoiceField(
        required=False, label="Exterior Features", widget=forms.CheckboxSelectMultiple,
        help_text="Select all exterior features that apply. None cannot be combined with another feature.",
    )
    interior_feature_types = forms.MultipleChoiceField(
        required=False, label="Interior Features", widget=forms.CheckboxSelectMultiple,
        help_text="Select all interior features that apply. None cannot be combined with another feature.",
    )
    flooring_types = forms.MultipleChoiceField(
        required=False, label="Flooring", widget=forms.CheckboxSelectMultiple,
        help_text="Select all flooring types that apply.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ownership = self.fields['ownership_type']
        ownership.choices = [('', 'Select One')] + OWNERSHIP_CHOICES
        saved_ownership = self.instance.ownership_type
        if saved_ownership in dict(LEGACY_OWNERSHIP_CHOICES):
            ownership.choices = list(ownership.choices) + [(saved_ownership, dict(LEGACY_OWNERSHIP_CHOICES)[saved_ownership] + ' (previously saved)')]
        ownership.widget.attrs['data-property-ownership-defaults'] = json.dumps(PROPERTY_OWNERSHIP_DEFAULTS)

        water_names = list(getattr(settings, 'PROPERTY_WATER_BODY_NAME_CHOICES', [(name, name) for name in WATER_BODY_NAMES]))
        saved_water = self.initial.get('water_body_name', self.instance.water_body_name) or ''
        if saved_water and saved_water not in {code for code, _ in water_names}:
            water_names.append((saved_water, saved_water + ' (previously saved)'))
        self.fields['water_body_name'] = forms.ChoiceField(
            required=False, label='Water Body Name (Only valid if the property is Waterfront)',
            choices=[('', 'Select One')] + water_names,
            widget=forms.Select(attrs={'class': 'form-control'}),
        )

        self.fields['utility_services_types'].label = 'Utility Services Available'
        for name in ['application_association_yn', 'application_fee', 'application_fee_per_person', 'application_fee_payable_to', 'application_managed_by', 'application_security_deposit', 'application_security_deposit_payable_to', 'application_required', 'application_administration_fee', 'application_administration_fee_payable_to', 'application_first_month_rent_payable_to', 'application_renters_insurance_required', 'application_short_term_premium', 'application_short_term_premium_amount', 'application_on_site_compliance', 'application_certified_funds', 'application_minimum_lease_months', 'application_maximum_lease_months', 'application_available_date', 'application_lease_term', 'application_lease_guarantor_yn', 'application_policy', 'application_max_number_of_pets', 'application_pet_deposit', 'application_pet_deposit_per_pet', 'application_monthly_pet_rent', 'application_monthly_pet_rent_per_pet', 'application_additional_pet_fee', 'application_additional_pet_fee_description', 'application_pets_allowed', 'application_one_time_expenses', 'application_recurring_expenses', 'application_deliver_address', 'application_public_link', 'application_agent_link', 'application_rentspree_online_yn', 'application_owner_contributions_yn', 'application_intermediary_yn']:
            field = self.fields[name]
            if name.endswith('_yn') or name in ['application_association_yn', 'application_fee_per_person', 'application_renters_insurance_required', 'application_short_term_premium', 'application_on_site_compliance', 'application_certified_funds', 'application_lease_guarantor_yn', 'application_pet_deposit_per_pet', 'application_monthly_pet_rent_per_pet', 'application_rentspree_online_yn', 'application_owner_contributions_yn', 'application_intermediary_yn']:
                field.widget = forms.Select(choices=[('', 'Select One'), ('yes', 'Yes'), ('no', 'No')], attrs={'class': 'form-control'})
            if name == 'application_available_date':
                field.widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
            if name in ['application_minimum_lease_months', 'application_maximum_lease_months', 'application_max_number_of_pets']:
                field.min_value = 0
                field.widget.attrs['min'] = 0
        for name, labels in APPLICATION_SINGLE_CHOICES.items():
            choices = [(label, label) for label in labels]
            saved = self.initial.get(name, getattr(self.instance, name, '')) or ''
            if saved and saved not in labels:
                choices.append((saved, saved + ' (previously saved)'))
            self.fields[name] = forms.ChoiceField(
                required=False, label=self.fields[name].label,
                choices=[('', 'Select One')] + choices,
                widget=forms.Select(attrs={'class': 'form-control'}),
            )
        for name, config in TEXT_FEATURE_CHOICES.items():
            choices = list(getattr(settings, 'PROPERTY_' + name.upper() + '_CHOICES', config['choices']))
            saved = decode_features(self.initial.get(name, getattr(self.instance, name, '')))
            known = {code for code, _ in choices}
            choices.extend((code, code + ' (previously saved)') for code in saved if code not in known)
            self.fields[name] = TextFeatureChoiceField(required=False, label=config['label'], choices=choices, limit=config['limit'])
            self.initial[name] = saved
        for name, defaults in EQUIPMENT_CHOICES.items():
            choices = list(getattr(settings, "PROPERTY_" + name.upper() + "_CHOICES", defaults))
            known = {code for code, _ in choices}
            saved = getattr(self.instance, name + "_types", None) or []
            choices.extend((code, code + " (previously saved)") for code in saved if code not in known)
            self.fields[name + "_types"].choices = choices
        # Required application fields marked with an asterisk in the reference.
        # Apply after constructing the choice fields so their flags are retained.
        for name in (
            'application_fee',
            'application_managed_by',
            'application_security_deposit',
            'application_security_deposit_payable_to',
            'application_required',
            'application_first_month_rent_payable_to',
            'application_renters_insurance_required',
            'application_on_site_compliance',
            'application_certified_funds',
            'application_available_date',
            'application_lease_term',
            'application_policy',
            'application_max_number_of_pets',
            'application_pet_deposit',
            'application_monthly_pet_rent',
            'application_pets_allowed',
            'application_one_time_expenses',
            'application_rentspree_online_yn',
            'application_intermediary_yn',
        ):
            self.fields[name].required = True
        condition_choices = list(getattr(settings, "PROPERTY_CONDITION_CHOICES", PROPERTY_CONDITION_CHOICES))
        saved_condition = self.instance.property_condition or ""
        if saved_condition and saved_condition not in {code for code, _ in condition_choices}:
            condition_choices.append((saved_condition, saved_condition + " (previously saved)"))
        self.fields["property_condition"] = forms.ChoiceField(required=False, label="Property Condition (max 1)",
            choices=[("", "Select One"), *condition_choices], widget=forms.Select(attrs={"class": "form-control"}))
        self.fields["move_in_special_yn"].choices = [("", "Select One"), ("yes", "Yes"), ("no", "No")]
        self.fields["move_in_special_description"].widget = forms.Textarea(attrs={"class": "form-control", "rows": 3, "maxlength": 1000})
        fema_choices = list(getattr(settings, "PROPERTY_FEMA_FLOOD_PLAIN_CHOICES", (
            ("see_remarks", "See Remarks"), ("partial", "Partial"),
            ("yes_500_year", "Yes-500 yr"), ("no", "No"), ("yes_100_year", "Yes-100 yr"),
        )))
        saved_fema = self.instance.fema_flood_plain_types or []
        known_fema = {code for code, _ in fema_choices}
        fema_choices.extend((code, code + " (previously saved)") for code in saved_fema if code not in known_fema)
        self.fields["fema_flood_plain_types"].choices = fema_choices
        etj_choices = list(getattr(settings, "PROPERTY_ETJ_CHOICES", (
            ("see_remarks", "See Remarks"), ("yes", "Yes"), ("no", "No"),
        )))
        saved_etj = self.instance.etj or ""
        if saved_etj and saved_etj not in {code for code, _ in etj_choices}:
            etj_choices.append((saved_etj, saved_etj + " (previously saved)"))
        self.fields["etj"] = forms.ChoiceField(label="ETJ", required=False,
            choices=[("", "Select One"), *etj_choices], widget=forms.Select(attrs={"class": "form-control"}))
        self.fields["housing_vouchers"].required = True
        self.fields["housing_vouchers"].choices = [("", "Select One"), ("yes", "Yes"), ("no", "No")]
        level_choices = list(getattr(settings, "PROPERTY_LEVEL_CHOICES", (
            ("1", "1"), ("1.5", "1.5"), ("2", "2"), ("3+", "3+"), ("multi-split", "Multi/Split"),
        )))
        saved_levels = self.instance.level_types or []
        known_levels = {code for code, _ in level_choices}
        level_choices.extend((code, code + " (previously saved)") for code in saved_levels if code not in known_levels)
        self.fields["level_types"].choices = level_choices
        for name in ("living_areas", "dining_areas"):
            self.fields[name].required = True
            self.fields[name].min_value = 0
            self.fields[name].widget.attrs.update(min=0, step=1)
        self.fields["tax_legal_description"].required = True
        self.fields["tax_legal_description"].widget = forms.Textarea(attrs={
            "class": "form-control", "rows": 3, "maxlength": 255,
            "aria-describedby": "tax-legal-remaining",
        })
        direction_choices = list(getattr(settings, "PROPERTY_DIRECTION_FACES_CHOICES", (
            ("E", "East"), ("N", "North"), ("NE", "North-East"), ("NW", "North-West"),
            ("S", "South"), ("SE", "South-East"), ("SW", "South-West"), ("W", "West"),
        )))
        source_choices = list(getattr(settings, 'PROPERTY_LIVING_AREA_SOURCE_CHOICES', (
            ('See Remarks', 'See Remarks'), ('Appraiser', 'Appraiser'),
            ('Builder', 'Builder'), ('Estimated', 'Estimated'),
            ('Multiple Dwelling', 'Multiple Dwelling'), ('Owner', 'Owner'),
            ('Plans', 'Plans'), ('Public Records', 'Public Records'),
        )))
        saved_source = self.instance.living_area_source or ''
        if saved_source and saved_source not in {code for code, _ in source_choices}:
            source_choices.append((saved_source, saved_source + ' (previously saved)'))
        self.fields['living_area_source'] = forms.ChoiceField(required=False, label='Living Area Source', choices=[('', 'Select One'), *source_choices], widget=forms.Select(attrs={'class': 'form-control'}))
        saved_direction = self.instance.direction_faces or ""
        if saved_direction and saved_direction not in {code for code, _ in direction_choices}:
            direction_choices.append((saved_direction, saved_direction + " (previously saved)"))
        self.fields["direction_faces"] = forms.ChoiceField(
            required=False, label="Direction Faces",
            choices=[("", "Select One")] + direction_choices,
            widget=forms.Select(attrs={"class": "form-control"}),
        )
        saved = self.instance.flooring_types or []
        options = FlooringOption.objects.filter(Q(is_active=True) | Q(code__in=saved))
        choices = [(option.code, option.label) for option in options]
        known = {code for code, _ in choices}
        # Even removed vocabulary must not silently erase existing selections.
        choices.extend((code, code + " (previously saved)") for code in saved if code not in known)
        self.fields["flooring_types"].choices = choices
        saved_features = self.instance.interior_feature_types or []
        feature_options = InteriorFeatureOption.objects.filter(Q(is_active=True) | Q(code__in=saved_features))
        feature_choices = [(option.code, option.label) for option in feature_options]
        known_features = {code for code, _ in feature_choices}
        feature_choices.extend((code, code + " (previously saved)") for code in saved_features if code not in known_features)
        self.fields["interior_feature_types"].choices = feature_choices
        self.fields["interior_features"].label = "Other / Interior Feature Details"
        self.fields["interior_features"].help_text = "Add details for Other or See Remarks, or room-specific notes. Existing interior feature notes are preserved here."
        saved_features = self.instance.exterior_feature_types or []
        feature_options = ExteriorFeatureOption.objects.filter(Q(is_active=True) | Q(code__in=saved_features))
        feature_choices = [(option.code, option.label) for option in feature_options]
        known_features = {code for code, _ in feature_choices}
        feature_choices.extend((code, code + " (previously saved)") for code in saved_features if code not in known_features)
        self.fields["exterior_feature_types"].choices = feature_choices
        self.fields["exterior_features"].label = "Other / Exterior Feature Details"
        self.fields["exterior_features"].help_text = "Add details for Other or See Remarks, or room-specific notes. Existing exterior feature notes are preserved here."
        saved_features = self.instance.construction_material_types or []
        feature_options = ConstructionMaterialOption.objects.filter(Q(is_active=True) | Q(code__in=saved_features))
        feature_choices = [(option.code, option.label) for option in feature_options]
        known_features = {code for code, _ in feature_choices}
        feature_choices.extend((code, code + " (previously saved)") for code in saved_features if code not in known_features)
        self.fields["construction_material_types"].choices = feature_choices
        self.fields["construction_materials"].label = "Other / Construction Material Details"
        self.fields["construction_materials"].help_text = "Add details for Other or See Remarks, or room-specific notes. Existing construction material notes are preserved here."
        saved_features = self.instance.foundation_types or []
        feature_options = FoundationOption.objects.filter(Q(is_active=True) | Q(code__in=saved_features))
        feature_choices = [(option.code, option.label) for option in feature_options]
        known_features = {code for code, _ in feature_choices}
        feature_choices.extend((code, code + " (previously saved)") for code in saved_features if code not in known_features)
        self.fields["foundation_types"].choices = feature_choices
        self.fields["foundation"].label = "Other / Foundation Details"
        self.fields["foundation"].help_text = "Add details for Other or See Remarks, or room-specific notes. Existing foundation notes are preserved here."
        self.foundation_selection_limit = getattr(settings, "PROPERTY_FOUNDATION_MAX_SELECTIONS", 13)
        self.fields["foundation_types"].help_text = f"Select all foundation types that apply (maximum {self.foundation_selection_limit}). None must be selected by itself."
        saved_features = self.instance.roof_types or []
        feature_options = RoofOption.objects.filter(Q(is_active=True) | Q(code__in=saved_features))
        feature_choices = [(option.code, option.label) for option in feature_options]
        known_features = {code for code, _ in feature_choices}
        feature_choices.extend((code, code + " (previously saved)") for code in saved_features if code not in known_features)
        self.fields["roof_types"].choices = feature_choices
        self.fields["roof"].label = "Other / Roof Details"
        self.fields["roof"].help_text = "Add details for Other or See Remarks, or room-specific notes. Existing roof notes are preserved here."
        self.roof_selection_limit = getattr(settings, "PROPERTY_ROOF_MAX_SELECTIONS", 10)
        self.fields["roof_types"].help_text = f"Select all roof types that apply (maximum {self.roof_selection_limit}). None must be selected by itself."
        self.fields["flooring"].label = "Other / Flooring Details"
        self.fields["flooring"].help_text = "Describe other flooring or room-specific details. Existing flooring notes are preserved here."

        conditional_application_requirements(self, [name for name in self.fields if name.startswith('application_')])

    def clean_interior_feature_types(self):
        codes = list(dict.fromkeys(self.cleaned_data["interior_feature_types"]))
        if "none" in codes and len(codes) > 1:
            raise ValidationError("Select None by itself, or remove None and choose the applicable features.")
        if {"interior-steps", "no-interior-steps"}.issubset(codes):
            raise ValidationError("Choose either Interior Steps or No Interior Steps, not both.")
        return codes

    def clean_exterior_feature_types(self):
        codes = list(dict.fromkeys(self.cleaned_data["exterior_feature_types"]))
        if "none" in codes and len(codes) > 1:
            raise ValidationError("Select None by itself, or remove None and choose the applicable features.")
        if {"exterior-steps", "no-exterior-steps"}.issubset(codes):
            raise ValidationError("Choose either Exterior Steps or No Exterior Steps, not both.")
        return codes

    def clean_construction_material_types(self):
        codes = list(dict.fromkeys(self.cleaned_data["construction_material_types"]))
        if "none" in codes and len(codes) > 1:
            raise ValidationError("Select None by itself, or remove None and choose the applicable materials.")
        return codes

    def clean_foundation_types(self):
        codes = list(dict.fromkeys(self.cleaned_data["foundation_types"]))
        if len(codes) > self.foundation_selection_limit:
            raise ValidationError(f"Select no more than {self.foundation_selection_limit} foundation types.")
        if "none" in codes and len(codes) > 1:
            raise ValidationError("Select None by itself, or remove None and choose the applicable foundation types.")
        return codes

    def clean_roof_types(self):
        codes = list(dict.fromkeys(self.cleaned_data["roof_types"]))
        if len(codes) > self.roof_selection_limit:
            raise ValidationError(f"Select no more than {self.roof_selection_limit} roof types.")
        if "none" in codes and len(codes) > 1:
            raise ValidationError("Select None by itself, or remove None and choose the applicable roof types.")
        return codes

    def clean_fema_flood_plain_types(self):
        return list(dict.fromkeys(self.cleaned_data["fema_flood_plain_types"]))

    def clean_level_types(self):
        levels = list(dict.fromkeys(self.cleaned_data["level_types"]))
        if len(levels) > 1:
            raise ValidationError("Select only one level.")
        return levels

    def clean_flooring_types(self):
        return list(dict.fromkeys(self.cleaned_data["flooring_types"]))

    class Meta:
        model = PropertyProfile
        fields = [item[0] for group in PROFILE_SECTIONS.values() for item in group] + ["flooring_types", "interior_feature_types", "exterior_feature_types", "construction_material_types", "foundation_types", "roof_types"]
        labels = {
            n: label for group in PROFILE_SECTIONS.values() for n, _, label in group
        }

    def clean(self):
        data = super().clean()
        if 'ownership_type' in data and not data['ownership_type']:
            property_type = self.data.get('property_type', '')
            data['ownership_type'] = PROPERTY_OWNERSHIP_DEFAULTS.get(property_type, '')

        for name in EQUIPMENT_CHOICES:
            field_name = name + "_types"
            codes = list(dict.fromkeys(data.get(field_name) or []))
            data[field_name] = codes
            if "none" in codes and len(codes) > 1:
                self.add_error(field_name, "None cannot be combined with another feature.")
            limit = SELECTION_LIMITS.get(name)
            if limit and len(codes) > limit:
                self.add_error(field_name, f"Select no more than {limit} options.")
        if (data.get("school_district") or "").strip().lower() == "other":
            if not data.get("out_of_state_school_district"):
                self.add_error("out_of_state_school_district", "Out of State School District is required when School District is Other.")
        for school, other in (
            ("elementary_school", "elementary_school_other"),
            ("middle_school", "middle_school_other"),
            ("high_school", "high_school_other"),
        ):
            if (data.get(school) or "").strip().lower() in ("other", "outside school district"):
                if not data.get(other):
                    self.add_error(other, "Enter the school name when Other or Outside School District is selected.")
        if data.get("has_hoa") is True:
            for name in ("hoa_management_company",):
                if not data.get(name):
                    self.add_error(name, "Enter the HOA management company.")

        elif data.get("has_hoa") is False:
            for name in (
                "hoa_management_company",
                "association_fee",
                "association_fee_frequency",
                "association_requirements",
                "association_fees_include",
                "special_assessment",
            ):
                if data.get(name) not in (None, ""):
                    self.add_error(
                        name, "Clear association details or select Yes for HOA."
                    )
        if data.get("association_fee") is not None and not data.get(
            "association_fee_frequency"
        ):
            self.add_error(
                "association_fee_frequency", "Choose how often this fee is charged."
            )
        if data.get("annual_tax_amount") is not None and not data.get("tax_year"):
            self.add_error("tax_year", "Enter the year for this tax amount.")
        try:
            validate_year(data.get("tax_year"))
        except ValidationError as error:
            self.add_error("tax_year", error)
        if data.get("tax_rate") is not None and data["tax_rate"] > 100:
            self.add_error("tax_rate", "Enter a percentage between 0 and 100.")
        minimum, maximum = data.get('application_minimum_lease_months'), data.get('application_maximum_lease_months')
        if application_section_enabled(self) and minimum is not None and maximum is not None and maximum < minimum:
            self.add_error('application_maximum_lease_months', 'Maximum lease months must be at least the minimum.')
        validate_section_remarks(self, data)
        return data


class PropertyMarketingForm(StyledModelForm):
    class Meta:
        model = PropertyMarketingDefaults
        fields = [item[0] for group in MARKETING_SECTIONS.values() for item in group]
        labels = {
            n: label for group in MARKETING_SECTIONS.values() for n, _, label in group
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, config in MARKETING_TEXT_FEATURE_CHOICES.items():
            choices = list(getattr(settings, 'PROPERTY_' + name.upper() + '_CHOICES', config['choices']))
            saved = decode_features(self.initial.get(name, getattr(self.instance, name, '')))
            known = {code for code, _ in choices}
            choices.extend((code, code + ' (previously saved)') for code in saved if code not in known)
            self.fields[name] = TextFeatureChoiceField(required=True, label=config['label'], choices=choices, limit=config['limit'])
            self.initial[name] = saved
        for name, placeholder in (
            ("assigned_manager_name", "Enter property manager’s name"),
            ("listing_agent_name", "Enter listing agent’s name"),
            ("co_listing_agent_name", "Enter co-listing agent’s name"),
        ):
            self.fields[name].widget.attrs["placeholder"] = placeholder
        self.fields["access_code"].widget = forms.PasswordInput(
            render_value=True,
            attrs={"class": "form-control", "autocomplete": "new-password"},
        )
        for name in ("showing_requirements", "lockbox_type"):
            self.fields[name].required = True
        conditional_application_requirements(self, ['showing_requirements', 'lockbox_type'])

    def clean(self):
        data = super().clean()
        if data.get("allow_address_display") and not data.get("allow_public_display"):
            self.add_error(
                "allow_address_display",
                "Enable public property display before allowing the address to be displayed.",
            )
        if application_section_enabled(self) and 'see_remarks' in decode_features(data.get('lockbox_type')) and not (data.get('showing_instructions') or '').strip():
            self.add_error('showing_instructions', 'Enter showing instructions because See Remarks is selected for Lockbox Type.')
        return data


class DocumentLinkForm(StyledModelForm):
    def __init__(self, *args, **kwargs):
        self.upload_user = kwargs.pop('upload_user', None)
        super().__init__(*args, **kwargs)
        for name in ('title', 'category', 'url', 'notes'):
            self.fields[name].required = False
            self.fields[name].widget.attrs.pop('required', None)
        help_texts = {'title': 'A short, descriptive name for the linked document, such as Lease Agreement or Inspection Report.', 'category': 'The category used to organize this document. Choose the category that best describes its purpose.', 'url': 'The URL of the document in Google Drive or another document service. Adding a link does not change sharing permissions or grant access.', 'notes': 'Internal notes describing the document, its purpose or any follow-up needed.'}
        for name, text in help_texts.items():
            field = self[name]
            field.feature_help_text = text
            field.feature_help_template = 'portal/property_general_information.html'


    def clean_url(self):
        from urllib.parse import urlsplit
        from django.urls import resolve, Resolver404
        from .models import PropertyDocumentUpload
        value = self.cleaned_data.get('url', '')
        self.document_upload = None
        try:
            match = resolve(urlsplit(value).path)
        except Resolver404:
            return value
        if match.view_name != 'portal:property_document_download':
            return value
        upload = PropertyDocumentUpload.objects.filter(pk=match.kwargs['upload_id']).first()
        property_id = self.instance.property_id
        if upload is None or (upload.property_id is not None and upload.property_id != property_id):
            raise ValidationError('This document belongs to another property or is unavailable.')
        if upload.property_id is None and (self.upload_user is None or upload.uploaded_by_id != self.upload_user.pk):
            raise ValidationError('This document upload is not available to this user.')
        self.document_upload = upload
        return value

    def clean(self):
        data = super().clean()
        data['category'] = data.get('category') or 'other'
        title = (data.get('title') or '').strip()
        url = (data.get('url') or '').strip()
        notes = (data.get('notes') or '').strip()
        if not title and not url and not notes:
            # Empty document rows are not property requirements or records.
            data['DELETE'] = True
        elif not title:
            from urllib.parse import urlsplit, unquote
            parsed = urlsplit(url)
            data['title'] = (unquote(parsed.path.rstrip('/').rsplit('/', 1)[-1]) or parsed.hostname or 'Document')[:255]
        return data

    class Meta:
        model = PropertyDocumentLink
        fields = ["title", "category", "url", "notes"]
        labels = {"url": "Google Drive / Document Link"}


class EnergyCertificationForm(StyledModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = ["Austin Energy's Green Building", 'LEED For Homes', 'ENERGY STAR Certified Homes', 'Home Performance with ENERGY STAR', 'HERS Index Score', 'Building America', 'Certified Passive House', 'PHIUS+', 'EnerPHit', 'Environments for Living', 'Home Energy Upgrade Certificate of Energy Efficiency Improvements', 'Home Energy Upgrade Certificate of Energy Efficiency Performance', 'Home Energy Score']
        choices = [("", "Select One")] + [(label, label) for label in labels]
        saved = self.instance.verification_type if self.instance.pk else ""
        if saved and saved not in labels:
            choices.append((saved, saved + " (previously saved)"))
        self.fields["verification_type"] = forms.ChoiceField(choices=choices, label="Green Building Verification Type", widget=forms.Select(attrs={"class": "form-control"}))
        for name in ("verification_type", "metric", "status", "rating", "year"):
            if name != "verification_type":
                self.fields[name].label = "Verification " + name.title()

            field = self[name]
            field.feature_help_template = (
                "portal/property_verification"
                + ("" if name == "verification_type" else "_" + name)
                + "_information.html"
            )

    class Meta:
        model = PropertyEnergyCertification
        fields = ["verification_type", "metric", "status", "rating", "year"]

    def clean_year(self):
        year = self.cleaned_data.get("year")
        validate_year(year)
        return year


class OwnedInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        # A tampered form id must never move another property's record.
        for form in self.forms:
            if form.cleaned_data:
                obj = form.cleaned_data.get("id")
                if obj is not None and obj.property_id != self.instance.pk:
                    raise ValidationError(
                        "One of these records does not belong to this property."
                    )


DocumentLinkFormSet = inlineformset_factory(
    Property,
    PropertyDocumentLink,
    form=DocumentLinkForm,
    formset=OwnedInlineFormSet,
    extra=1,
    can_delete=True,
    max_num=100,
    absolute_max=100,
    validate_max=True,
)
EnergyCertificationFormSet = inlineformset_factory(
    Property,
    PropertyEnergyCertification,
    form=EnergyCertificationForm,
    formset=OwnedInlineFormSet,
    extra=1,
    can_delete=True,
    max_num=30,
    absolute_max=30,
    validate_max=True,
)


def build_sections(core, profile, marketing):
    for form in (core, profile, marketing):
        set_dropdown_prompts(form)
    result = []
    for name in SECTION_ORDER:
        fields = []
        fields.extend(core[n] for n in CORE_SECTIONS.get(name, []))
        fields.extend(profile[n] for n, _, _ in PROFILE_SECTIONS.get(name, []))
        fields.extend(marketing[n] for n, _, _ in MARKETING_SECTIONS.get(name, []))
        if name == "Ownership & Management":
            ownership_order = (
                "management_status", "occupancy_status", "property_type", "ownership_type",
                "property_type_other", "assigned_manager_name",
            )
            fields_by_name = {field.name: field for field in fields}
            fields = [fields_by_name[n] for n in ownership_order]
        if name == 'Ownership & Management':
            property_type_field = next(field for field in fields if field.name == 'property_type')
            property_type_field.field_help = ''
        if name == "Property Overview":
            # Keep the two-column overview grouped by address, space, construction,
            # schools and marketing while retaining the existing bound fields.
            overview_order = (
                list(ADDRESS_ORDER) + ["is_multi_unit", "level_types",
                 "main_level_bedrooms", "other_level_beds", "bathrooms_full", "bathrooms_half",
                 "sqft", "living_area_source", "living_areas", "dining_areas", "garage_spaces", "laundry_location",
                 "parking_total", "parking_features", "year_built", "direction_faces",
                 "lot_size_sqft", "lot_dimensions", "builder_name"]
                + [n for n, _, _ in PROFILE_SECTIONS[name]
                   if n not in {"tax_legal_description", "level_types", "living_area_source", "living_areas", "dining_areas", "garage_spaces",
                                "parking_total", "parking_features", "laundry_location",
                                "year_built_source", "direction_faces", "property_condition",
                                "lot_dimensions", "builder_name"}]
                + ["latitude", "longitude"]
                + [n for n, _, _ in MARKETING_SECTIONS[name]]
            )
            fields_by_name = {field.name: field for field in fields}
            fields = [fields_by_name[n] for n in overview_order]
            headings = {
                "street_number": "Property Identity & Address",
                "level_types": "Space & Parking",
                "year_built": "Building & Lot Details",
                "school_district": "Location & School Information",
                "latitude": "Map",
                "listing_agent_name": "Marketing Defaults",
            }
            for field in fields:
                field.overview_heading = headings.get(field.name, "")
                field.field_help = {
                    'street_address': 'The property’s street number and street name. Enter the unit or suite separately.',
                    'city': 'The city shown in the property’s address.',
                    'state': 'The state where the property is located.',
                    'zip_code': 'The postal ZIP code for the property.',
                    'county': 'The county where the property is located.',
                    'subdivision': 'The subdivision or community name shown in the property records.',
                    'property_type': 'Select the category that best describes the property.',
                    'tax_legal_description': 'The legal description shown in the property’s tax or recorded documents. Maximum 255 characters.',
                    'unit_number': 'Text containing the number or portion of a larger building or complex. In the street address, the unit number follows the street suffix or street suffix direction, if present. Examples: APT G, 55, Suite B.',
                    'year_built': 'The year when the home was built or construction of the property improvements was completed. Remodels do not count unless the home was torn down completely.',
                    'lot_size_sqft': 'The total area of the lot in square feet.',
                    'direction_faces': "The compass direction that the main entrance to the building faces. For example, North, South, East, West or South-West.",
                    'lot_dimensions': 'The dimensions of the lot represented as frontage and depth, for example 250 × 180.',
                    'builder_name': "Name of the builder of the property or builder's tract.",
                    'school_district': 'The name of the school district the property is zoned to attend and pay taxes to.',
                    'elementary_school': 'The name of the primary school having a catchment area that includes the associated property.',
                    'middle_school': 'The name of the junior or middle school having a catchment area that includes the associated property.',
                    'high_school': 'The name of the high school having a catchment area that includes the associated property.',
                    "garage_spaces": "The number of spaces in the garage(s).",
                    "laundry_location": "The location in the dwelling where clothing can be washed and/or dried.",
                    "main_level_bedrooms": "The number of bedrooms located on the main or entry level of the property.",
                    "other_level_beds": "The number of bedrooms on any level of the dwelling other than the main level.",
                    "bathrooms_full": "The number of bathrooms consisting of a toilet, sink and bathing area, either tub and/or shower.",
                    "bathrooms_half": "The number of bathrooms consisting of only a toilet and sink.",
                    "parking_total": "The total number of parking spaces available for this property.",
                    "parking_features": "A list of features or description of the parking included in the sale/lease.",
                    "level_types": "Select the number of levels in the home. Use 1.5 for a partial upper level, 3+ for three or more levels, or Multi/Split for split-level layouts. Select one option.",
                    "sqft": "Enter the interior living area in square feet. Exclude garages and unfinished areas.",
                    "living_area_source": "Identify where the living-area measurement came from, such as tax records, builder plans or an appraisal.",
                    "living_areas": "Enter the number of separate living areas, such as living rooms, family rooms or dens. Enter 0 if there are none.",
                    "dining_areas": "Enter the number of separate dining areas, including a dining room or breakfast area. Enter 0 if there are none.",
                }.get(field.name, "")
                if field.name == "out_of_state_school_district":
                    field.school_help_title = "Out of State School District Help"
                    field.school_help_rule = "Out of State School District is required when School District is Other."
                    field.school_help_text = "The name of the School District, if it falls outside of Texas."
                elif field.name in ("elementary_school_other", "middle_school_other", "high_school_other"):
                    level = {"elementary_school_other": "Elementary School", "middle_school_other": "Middle or Junior School", "high_school_other": "High School"}[field.name]
                    field.school_help_title = "Other " + level + " Help"
                    field.school_help_rule = "Other " + level + " is required when Other or Outside School District is selected."
                    field.school_help_text = 'If the listing is in Texas, but outside of the 18 Central Texas counties, select the School District (ISD) of the school, select "Outside School District" as the school, and then use this field to manually type in the name of the ' + level + ' the property is associated with.'
                    field.school_help_text_extra = 'If the listing is not in the state of Texas, select "Other" for School District and ' + level + ', then use this field to manually type in the name of the ' + level + ' the property is associated with.'

        if name == "Rules, Associations & Compliance":
            help_texts = {
                "fema_flood_plain_types": "Select the applicable FEMA flood plain designations using the property documentation. Select See Remarks when additional explanation is recorded in Internal Property Notes/Remarks.",
                "housing_vouchers": "Select Yes or No to record whether housing vouchers are accepted for this property. Confirm the applicable program requirements before completing this field.",
                "etj": "ETJ means Extraterritorial Jurisdiction. Select Yes, No or See Remarks based on the property documentation. Record additional explanation in Internal Property Notes/Remarks.",
            }
            for field in fields:
                field.field_help = help_texts.get(field.name, "")

        if name == "Documents, Financial Setup & Activity":
            fields = [field for field in fields if field.name != "notes"] + [core["notes"]]

        for field in fields:
            if name == 'How to Apply, Agent Access & Services' and field.name.startswith('application_'):
                field.feature_help_text = 'Property application instructions: ' + field.label + '. Enter the applicable property policy or amount. Yes/No fields allow Select One when not yet known.'
            field.feature_help_template = {
                "appliances_types": "portal/property_appliances_information.html",
                "interior_features": "portal/property_interior_information.html",
                "exterior_features": "portal/property_exterior_information.html",
                "fencing": "portal/property_fencing_information.html",
                "accessibility_features_types": "portal/property_accessibility_information.html",
                "fireplaces": "portal/property_fireplaces_information.html",
                "fireplace_features_types": "portal/property_fireplace_features_information.html",
                "patio_porch_features": "portal/property_patio_porch_information.html",
                "window_features_types": "portal/property_window_information.html",
                "pool_features_types": "portal/property_pool_information.html",
                "spa_features_types": "portal/property_spa_information.html",
                "waterfront_features": "portal/property_waterfront_information.html",
                "water_body_name": "portal/property_water_body_information.html",
                "energy_features": "portal/property_energy_information.html",
                "sustainability_features": "portal/property_sustainability_information.html",
            }.get(field.name, "")
            if name == "Physical Features & Construction":
                field.field_help = {
                    "property_condition": "Select the single condition that best describes the property.",
                    "move_in_special_yn": "Indicate whether a move-in special is offered for this property.",
                    "move_in_special_description": "Describe the move-in special and its terms, up to 1,000 characters.",
                }.get(field.name, "")
            section_help = {'flooring': 'The floor coverings installed in the property, such as carpet, tile, wood or vinyl. Identify each material present. Select None only when applicable; use Other details for materials not listed.', 'construction_materials': 'The materials used in the exterior walls and structure, such as brick, stone, wood or concrete. Record documented materials; use Other details for unlisted materials.', 'foundation': 'The foundation supporting the structure, such as slab, pier and beam, or basement. Record the type shown in building or inspection documentation.', 'roof': 'The installed roof covering, such as composition shingles, metal or tile. Record all applicable materials and use Other details for unlisted coverings.', 'cooling_types': 'The cooling systems installed at the property, such as central air, ductless systems or window units. Select the systems present; select None if no cooling system is installed.', 'heating_types': 'The heating systems and fuel sources installed at the property, such as central heat, electric heat or a heat pump. Select the systems present; select None if no heating system is installed.', 'water_source': 'The source supplying water to the property, such as public water, a private well or a shared well. Confirm the source using service or property records.', 'sewer': 'The wastewater disposal system serving the property, such as public sewer or an onsite septic system. Confirm the system using utility or property records.', 'utility_services_types': 'Utility services available to the property, such as electricity, gas, water, sewer or internet. Availability does not necessarily mean a service is connected or included in rent.', 'utility_providers': 'The names and contact details of utility providers serving the property. Include the service type and useful customer-service contact information.', 'utility_responsibilities': 'Who is responsible for arranging and paying for each utility service, such as the owner, tenant or association. Follow the applicable lease or management agreement.', 'security_features_types': 'Security features installed at the property, such as alarms, cameras, controlled entry or security lighting. Describe installed features without putting access codes in this field.', 'showing_requirements': 'Conditions that must be met before a showing, such as an appointment, advance notice, occupant approval or agent accompaniment.', 'showing_contact_name': 'The name of the person responsible for coordinating or approving property showings.', 'showing_contact_phone': 'The telephone number for the showing contact. Include an extension if needed.', 'showing_contact_email': 'The email address for the person coordinating property showings.', 'lockbox_type': 'The type or brand of lockbox used to provide authorized access to the property.', 'lockbox_serial_number': 'The identifying serial number printed on the lockbox. Record it accurately so staff can identify the correct device.', 'lockbox_location': 'Where the lockbox is physically located, such as the front door, railing or designated gate.', 'access_code': 'The code used by authorized staff to access the property or lockbox. This field is staff-only and is omitted from the Property 360 profile display.', 'showing_instructions': 'Practical instructions for authorized showings, including appointment procedures, entry directions, pets, parking and securing the property afterward. Put access codes in Access Code (Staff Only).', 'has_hoa': 'Indicate whether the property belongs to a homeowners association or other property association.', 'hoa_management_company': 'The name of the company or organization managing the homeowners or property association.', 'association_fee': 'The recurring association fee amount for the selected Fee Frequency. Record the amount shown in current association documents.', 'association_fee_frequency': 'How often the association fee is charged, such as monthly, quarterly, semiannually or annually.', 'association_fees_include': 'Services or expenses covered by the association fee, such as common-area maintenance, amenities, insurance or specified utilities.', 'association_requirements': 'Association requirements affecting ownership, leasing, occupancy or use, such as registration, approval procedures or lease restrictions.', 'community_website': 'The official website for the community or association. Enter the complete website address.', 'community_features': 'Shared community amenities and features, such as a community pool, clubhouse, trails or playground. Record a community pool here; use Pool Features for a private pool.', 'restrictions': 'Documented restrictions affecting the property, including leasing, pets, parking, use or alterations. Identify the source and relevant details.', 'special_assessment': 'The amount of a special assessment imposed on the property in addition to recurring association fees. Describe payment timing or other details in Internal Property Notes/Remarks.', 'disclosures': 'Known property conditions and applicable disclosures identified in property records or by the owner. Link supporting disclosure documents in Document Links.', 'annual_tax_amount': 'The annual property tax amount for the specified Tax Year, based on the tax statement or other documented source.', 'tax_year': 'The year to which the recorded property tax information applies.', 'tax_assessed_value': 'The property value assessed by the taxing authority for the specified Tax Year. This may differ from market value or the taxable value after exemptions.', 'tax_rate': 'The property tax rate expressed as a percentage. Enter 2.15 for 2.15%, rather than 0.0215, and identify the applicable rate using tax records.', 'tax_exemptions': 'Exemptions reflected in the property tax records, such as homestead or other approved exemptions. Confirm their applicability for the recorded Tax Year.', 'notes': 'Internal property notes and remarks for staff, including operational context, follow-up items and explanations that should not appear in public marketing.'}
            if field.name in section_help and name != 'Property Overview':
                field.feature_help_text = section_help[field.name]
                field.feature_help_template = 'portal/property_general_information.html'
                field.field_help = ''
            if field.name in ADDRESS_HELP:
                field.feature_help_text = ADDRESS_HELP[field.name]
                field.feature_help_template = 'portal/property_general_information.html'
                field.field_help = ''
            if field.name in ('property_type', 'ownership_type'):
                field.feature_help_template = 'portal/property_subtype_ownership_information.html'
                field.field_help = ''
            if field.name in {**TEXT_FEATURE_CHOICES, **MARKETING_TEXT_FEATURE_CHOICES}:
                field.equipment_picker = True
                field.selection_limit = {**TEXT_FEATURE_CHOICES, **MARKETING_TEXT_FEATURE_CHOICES}[field.name]['limit'] or ''
                field.field_help = ''
                if field.name == 'laundry_location':
                    field.feature_help_template = 'portal/property_laundry_information.html'
                elif field.name == 'parking_features':
                    field.feature_help_template = 'portal/property_parking_information.html'
            if field.name in {name + "_types" for name in EQUIPMENT_CHOICES}:
                if field.name == "lot_features_types":
                    field.lot_features_help = True
                field.equipment_picker = True
                field.selection_limit = SELECTION_LIMITS.get(field.name.removesuffix("_types"), "")

        if name == 'Physical Features & Construction':
            paired_names = {n for pair in FEATURE_PAIRS for n in pair}
            pairs = [profile[n] for pair in FEATURE_PAIRS for n in pair]
            fields = [field for field in fields if field.name not in paired_names]
            # Keep the paired amenity rows before Green Energy and section remarks.
            position = next((i for i, field in enumerate(fields) if field.name in ('energy_features', 'sustainability_features', 'physical_features_remarks')), len(fields))
            fields[position:position] = pairs
            if core.is_bound:
                visibility_data = {n: profile[n].value() for pair in FEATURE_PAIRS for n in pair}
            else:
                visibility_data = {n: profile[n].value() for pair in FEATURE_PAIRS for n in pair}
            for left, right in FEATURE_PAIRS:
                next(field for field in fields if field.name == left).pair_start = True
                next(field for field in fields if field.name == right).pair_end = True
                next(field for field in fields if field.name == right).dependent_hidden = not dependent_visible(right, visibility_data)

        if name == 'How to Apply, Agent Access & Services':
            for field in fields:
                if field.name == 'showing_requirements':
                    field.overview_heading = 'Showing Instructions and Lockbox Details'
                elif field.name == 'listing_agent_name':
                    field.overview_heading = 'Marketing Defaults'

        remarks_fields = [field for field in fields if field.name.endswith('_remarks') and field.name in profile.fields and field.name != 'private_remarks']
        fields = [field for field in fields if field not in remarks_fields] + remarks_fields
        if name == 'How to Apply, Agent Access & Services':
            remarks = next((field for field in fields if field.name == 'rules_compliance_remarks'), None)
            if remarks is not None:
                fields.remove(remarks)
                association_index = next(i for i, field in enumerate(fields) if field.name == 'application_association_yn')
                fields.insert(association_index + 1, remarks)
        for field in fields:
            if field.name == 'move_in_special_description':
                field.dependent_hidden = not dependent_visible(field.name, {'move_in_special_yn': profile['move_in_special_yn'].value()})
            if name == 'How to Apply, Agent Access & Services' and field.name.startswith('application_'):
                field.feature_help_template = 'portal/property_general_information.html'
                field.field_help = ''
            field.application_default_field = field.name in ['application_required', 'application_association_yn']
            field.section_remarks_target = remarks_for_field(field.name) or ''
            field.section_remarks_field = field.name in ['ownership_management_remarks', 'property_overview_remarks', 'physical_features_remarks', 'utilities_services_remarks', 'rules_compliance_remarks', 'green_energy_remarks']

        result.append(
            {"title": name, "id": "section-" + str(len(result)), "fields": fields, "application_expanded": str(core["management_status"].value() or "").lower() in {"prospect", "onboarding"}}
        )
    return result
