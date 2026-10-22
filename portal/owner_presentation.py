"""Database-driven owner form labels and owner-type presentation."""
from common.models import FormFieldSetting


class OwnerPresentationMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rows = {row.field_key: row for row in FormFieldSetting.objects.filter(form_key="owner_profile")}
        missing = (set(self.fields) | {"actions"}) - rows.keys()
        if missing:
            raise RuntimeError("Run python manage.py seed_owner_profile_fields before opening owner forms.")
        self.owner_labels = {}
        owner_type = self.data.get(self.add_prefix("owner_type")) if self.is_bound else self.initial.get("owner_type", "individual")
        for name, field in self.fields.items():
            row = rows[name]
            variants = row.option_labels
            labels = {"individual": variants.get("individual_label", row.label), "entity": variants.get("entity_label", row.label)}
            self.owner_labels[name] = labels
            field.label = labels.get(owner_type, row.label)
            field.help_text = row.help_text
            field.error_messages.update(row.error_messages)
            if name == "owner_type":
                field.choices = [(code, variants.get(str(code), label)) for code, label in field.choices]
        from django import forms
        options = rows["preferred_contact_method"].option_labels
        current = self.data.get(self.add_prefix("preferred_contact_method")) if self.is_bound else self.initial.get("preferred_contact_method", "")
        choices = list(options.items())
        if current and current not in options:
            choices.append((current, current))
        original = self.fields["preferred_contact_method"]
        self.fields["preferred_contact_method"] = forms.ChoiceField(required=False, choices=choices, label=original.label, help_text=original.help_text)
        for name in ("phone", "alternate_contact_phone", "representative_phone"):
            self.fields[name].widget.attrs.update({"type":"tel", "placeholder":"(XXX) XXX-XXXX", "autocomplete":"tel-national"})
        self.owner_ui = rows["actions"].option_labels

    def clean(self):
        cleaned = super().clean()
        from portal.vendor_contact_validation import VendorContactValidationMixin
        from django import forms
        for name in ("phone", "alternate_contact_phone", "representative_phone"):
            if name in cleaned:
                try:
                    cleaned[name] = VendorContactValidationMixin.normalize_phone(cleaned[name])
                except forms.ValidationError as exc:
                    self.add_error(name, exc)
        return cleaned
