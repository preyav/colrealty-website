"""Private Property 360 profile sections; access codes stay in the staff editor."""

from decimal import Decimal
from .models import FlooringOption, InteriorFeatureOption, ExteriorFeatureOption, ConstructionMaterialOption, FoundationOption, RoofOption
from django.conf import settings
from .equipment_choices import EQUIPMENT_CHOICES, PROPERTY_CONDITION_CHOICES
from .marketing_feature_choices import MARKETING_TEXT_FEATURE_CHOICES
from .text_feature_choices import TEXT_FEATURE_CHOICES, decode_features
from .editor_sections import PROFILE_SECTIONS, MARKETING_SECTIONS, SECTION_ORDER


def profile_sections(property_obj):
    result = []
    profile = getattr(property_obj, "profile", None)
    marketing = getattr(property_obj, "marketing_defaults", None)
    for title in SECTION_ORDER:
        fields = []
        for obj, schema in (
            (profile, PROFILE_SECTIONS),
            (marketing, MARKETING_SECTIONS),
        ):
            if obj is None:
                continue
            for name, kind, label in schema.get(title, []):
                if name == "access_code":
                    continue
                value = getattr(obj, name)
                if name == "flooring":
                    codes = obj.flooring_types or []
                    labels = dict(FlooringOption.objects.filter(code__in=codes).values_list("code", "label"))
                    selected = ", ".join(labels.get(code, code) for code in codes)
                    value = "; ".join(part for part in (selected, value) if part)

                if name == "interior_features":
                    codes = obj.interior_feature_types or []
                    labels = dict(InteriorFeatureOption.objects.filter(code__in=codes).values_list("code", "label"))
                    selected = ", ".join(labels.get(code, code) for code in codes)
                    value = "; ".join(part for part in (selected, value) if part)
                if name == "exterior_features":
                    codes = obj.exterior_feature_types or []
                    labels = dict(ExteriorFeatureOption.objects.filter(code__in=codes).values_list("code", "label"))
                    selected = ", ".join(labels.get(code, code) for code in codes)
                    value = "; ".join(part for part in (selected, value) if part)
                if name == "construction_materials":
                    codes = obj.construction_material_types or []
                    labels = dict(ConstructionMaterialOption.objects.filter(code__in=codes).values_list("code", "label"))
                    selected = ", ".join(labels.get(code, code) for code in codes)
                    value = "; ".join(part for part in (selected, value) if part)
                if name == "foundation":
                    codes = obj.foundation_types or []
                    labels = dict(FoundationOption.objects.filter(code__in=codes).values_list("code", "label"))
                    selected = ", ".join(labels.get(code, code) for code in codes)
                    value = "; ".join(part for part in (selected, value) if part)
                if name == "roof":
                    codes = obj.roof_types or []
                    labels = dict(RoofOption.objects.filter(code__in=codes).values_list("code", "label"))
                    selected = ", ".join(labels.get(code, code) for code in codes)
                    value = "; ".join(part for part in (selected, value) if part)
                if name in {**TEXT_FEATURE_CHOICES, **MARKETING_TEXT_FEATURE_CHOICES}:
                    labels = dict(getattr(settings, 'PROPERTY_' + name.upper() + '_CHOICES', {**TEXT_FEATURE_CHOICES, **MARKETING_TEXT_FEATURE_CHOICES}[name]['choices']))
                    value = ', '.join(labels.get(code, code) for code in decode_features(value))
                if name in {key + "_types" for key in EQUIPMENT_CHOICES}:
                    key = name.removesuffix("_types")
                    labels = dict(getattr(settings, "PROPERTY_" + key.upper() + "_CHOICES", EQUIPMENT_CHOICES[key]))
                    value = ", ".join(labels.get(code, code) for code in (value or []))
                if name == "property_condition":
                    value = dict(getattr(settings, "PROPERTY_CONDITION_CHOICES", PROPERTY_CONDITION_CHOICES)).get(value, value)
                if name == "fema_flood_plain_types":
                    labels = dict(getattr(settings, "PROPERTY_FEMA_FLOOD_PLAIN_CHOICES", (
                        ("see_remarks", "See Remarks"), ("partial", "Partial"),
                        ("yes_500_year", "Yes-500 yr"), ("no", "No"), ("yes_100_year", "Yes-100 yr"),
                    )))
                    value = ", ".join(labels.get(code, code) for code in (value or []))
                if name == "etj":
                    labels = dict(getattr(settings, "PROPERTY_ETJ_CHOICES", (("see_remarks", "See Remarks"), ("yes", "Yes"), ("no", "No"))))
                    value = labels.get(value, value)
                if name == "level_types":
                    value = ", ".join("Multi/Split" if code == "multi-split" else code for code in (value or []))
                if value is None or value == "":
                    continue
                if (
                    name in ("allow_public_display", "allow_address_display")
                    and value is False
                ):
                    continue
                if isinstance(value, bool):
                    value = "Yes" if value else "No"
                elif kind.startswith("choice"):
                    value = getattr(obj, "get_" + name + "_display")()
                elif kind == "user":
                    value = value.get_full_name() or value.get_username()
                elif isinstance(value, Decimal):
                    value = (
                        f"${value:,.2f}" if kind == "money" else f"{value.normalize()}%"
                    )
                fields.append(
                    {
                        "label": label,
                        "value": value,
                        "is_link": kind == "url",
                        "wide": kind == "notes",
                    }
                )
        documents = (
            list(property_obj.document_links.all())
            if title == "Documents, Financial Setup & Activity"
            else []
        )
        certifications = (
            list(property_obj.energy_certifications.all())
            if title == "Physical Features & Construction"
            else []
        )
        if fields or documents or certifications:
            result.append(
                {
                    "title": title,
                    "fields": fields,
                    "documents": documents,
                    "certifications": certifications,
                }
            )
    return result
