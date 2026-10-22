from common.models import FormFieldSetting


def configure_ownership_fields(form):
    for row in FormFieldSetting.objects.filter(form_key="property_ownership"):
        if row.field_key in form.fields:
            field = form.fields[row.field_key]
            field.label = row.label
            field.help_text = row.help_text
            field.error_messages.update(row.error_messages)
    form.fields["maintenance_approval_limit"].widget.attrs.update({"min":"0", "step":"0.01"})

    # Fold legacy distribution text into Notes when an existing record is opened.
    legacy = (getattr(form.instance, "distribution_instructions", "") or "").strip()
    if not form.is_bound:
        notes = form.initial.get("notes", "") or ""
        if legacy and legacy not in notes:
            form.initial["notes"] = "\n\n".join(part for part in (notes, legacy) if part)
    else:
        # Submitted Notes is now authoritative, including deliberate deletions.
        # ModelForm only persists this change after the entire form validates.
        form.instance.distribution_instructions = ""
    form.fields.pop("distribution_instructions", None)
    form.fields["notes"].widget.attrs["rows"] = 3
