from .models import FormFieldSetting


def configure_form(form, form_key):
    settings = {item.field_key: item for item in FormFieldSetting.objects.filter(form_key=form_key)}
    missing = set(form.fields) - settings.keys()
    if missing:
        raise RuntimeError('Field settings are missing. Run seed_lease_agreement_fields after migrating common.')
    for name, field in form.fields.items():
        item = settings[name]
        field.label = item.label
        field.help_text = ''
        field.lease_information = [{'label': item.label, 'text': item.help_text}] if item.help_text else []
        field.error_messages.update(item.error_messages)
        if hasattr(field, 'choices'):
            field.choices = [(code, item.option_labels.get(str(code), label)) for code, label in field.choices]
    return settings
