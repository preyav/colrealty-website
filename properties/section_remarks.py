"""Section-specific validation for See Remarks selections."""
import re
from .feature_dependencies import dependent_visible
from .editor_sections import PROFILE_SECTIONS, MARKETING_SECTIONS
from .marketing_feature_choices import MARKETING_TEXT_FEATURE_CHOICES
from .text_feature_choices import decode_features

SECTION_REMARKS = {'Ownership & Management': 'ownership_management_remarks', 'Property Overview': 'property_overview_remarks', 'Physical Features & Construction': 'physical_features_remarks', 'Utilities, Access & Services': 'utilities_services_remarks', 'Rules, Associations & Compliance': 'rules_compliance_remarks'}
GREEN_FIELDS = {'energy_features', 'sustainability_features', 'solar', 'solar_ownership', 'green_energy_remarks'}
FEATURE_ALIASES = {
    'flooring_types': 'flooring', 'interior_feature_types': 'interior_features',
    'exterior_feature_types': 'exterior_features', 'construction_material_types': 'construction_materials',
    'foundation_types': 'foundation', 'roof_types': 'roof',
}

def remarks_for_field(name):
    if name.startswith('application_'):
        return 'rules_compliance_remarks'
    if name == 'lockbox_type':
        return 'showing_instructions'
    if name in GREEN_FIELDS:
        return 'green_energy_remarks'
    name = FEATURE_ALIASES.get(name, name)
    for title, fields in {title: fields + MARKETING_SECTIONS.get(title, []) for title, fields in PROFILE_SECTIONS.items()}.items():
        if any(item[0] == name for item in fields):
            return SECTION_REMARKS.get(title)
    return None

def is_see_remarks(value):
    return re.sub(r'[^a-z]', '', str(value).lower()) == 'seeremarks'

def validate_section_remarks(form, data):
    needed = set()
    for name, field in form.fields.items():
        target = remarks_for_field(name)
        if not dependent_visible(name, data):
            continue
        if not target or name == target or not hasattr(field, 'choices'):
            continue
        value = data.get(name)
        if isinstance(value, str) and value.startswith('['):
            value = decode_features(value)
        selected = value if isinstance(value, (list, tuple)) else [value]
        labels = dict(field.choices)
        if any(is_see_remarks(code) or is_see_remarks(labels.get(code, '')) for code in selected):
            needed.add(target)
    for target in sorted(needed):
        if not (data.get(target) or '').strip():
            form.add_error(target, 'Enter remarks because See Remarks is selected in this section.')
