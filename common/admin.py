from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from .models import FormFieldSetting


class FieldSettingAdminForm(forms.ModelForm):
    class Meta:
        model = FormFieldSetting
        fields = '__all__'

    def clean(self):
        data = super().clean()
        for key in ('option_labels', 'error_messages'):
            value = data.get(key)
            if value is not None and (not isinstance(value, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in value.items())):
                self.add_error(key, ValidationError('Use a JSON object containing text keys and text values.'))
        return data


@admin.register(FormFieldSetting)
class FormFieldSettingAdmin(admin.ModelAdmin):
    form = FieldSettingAdminForm
    list_display = ['form_key', 'field_key', 'label']
    list_filter = ['form_key']
    search_fields = ['form_key', 'field_key', 'label', 'help_text']
    readonly_fields = ['form_key', 'field_key']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
