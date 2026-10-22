from .models import FormFieldSetting


def document_type_setting():
    return FormFieldSetting.objects.get(form_key='lease_document', field_key='category')


def document_type_choices(setting, choices):
    return [(code, setting.option_labels.get(str(code), str(label))) for code, label in choices]
